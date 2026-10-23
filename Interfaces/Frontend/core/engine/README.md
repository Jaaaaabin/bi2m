# engine/ — standalone element preview

This directory holds a small, self-contained IFC parsing + rendering stack used
by exactly one feature: the "Preview in 3D" button in `InspectorPanel.jsx`,
which shows a close-up of the currently-selected element in its own embedded
canvas.

## Why a second engine

The main viewer (`ThatOpenCompanyLoader.js`) loads whole models through
ThatOpen's Fragments pipeline (`OBC.IfcLoader`), which is what floor/category
filtering (`OBC.Classifier`, `OBC.IfcRelationsIndexer`), visibility
(`OBC.Hider`) and highlighting (`OBCF.Highlighter`) all depend on. That
pipeline is the right tool for a whole model, but it's overkill for previewing
one element - it round-trips through a Fragments worker and expects a full
model, not a tiny snippet.

Everything in this directory bypasses that pipeline entirely: it indexes the
raw IFC bytes directly, extracts just the reference-graph closure around one
element (a few dozen to a few hundred instances, regardless of how large the
source file is), and renders it by streaming meshes straight out of `web-ifc`
into a plain ThatOpen world - the classic web-ifc-three approach. **None of
this code is a replacement for the main viewer's loading path** - it has no
classifier, no indexer, no hider. It only ever handles one element at a time.

## Files

- `stepIndex.js` - a byte-level index over the STEP/IFC text format
  (`#id=KEYWORD(...);`), giving O(1) lookup from express id to its instance
  text, references, type, and a few relationship-type buckets. Built once per
  loaded file. Pure JS/Node-testable - no browser-only APIs - which is why
  the worker wrapper below lives in its own file instead of here.
- `stepIndexClient.js` / `stepIndex.worker.js` - `buildStepIndexAsync(buf)`
  runs `StepFileIndex.build()` in a `Worker` instead of on the main thread
  (the synchronous byte scan measured 76-126ms on 5-20MB files - long enough
  to be worth moving off-thread). A fresh worker is spawned per call and
  terminated once it resolves; `buf` is transferred (zero-copy), not cloned,
  so callers must not read it again after calling. `stepIndex.worker.js` is
  the worker-side script; `stepIndexClient.js` is the main-thread wrapper
  that spawns it and reconstructs a real `StepFileIndex` instance from the
  plain, structured-cloneable data it posts back (a worker can't hand back
  a class instance directly - that would drop the prototype and
  `StepFileIndex`'s private field). `ThatOpenCompanyLoader.js` calls this,
  not `StepFileIndex.build()` directly.
- `subModel.js` - `extractSubModel(index, rootId, options)` walks the forward
  reference closure around one element (placement, representation, profiles,
  project/units/context, decomposition children, openings, styles) and
  assembles a minimal, self-contained STEP file from the original bytes.
- `thatopenPreviewEngine.js` - `ThatOpenPreviewEngine`, a small ThatOpen
  world (scene/camera/renderer) that opens that snippet through `web-ifc`
  directly and streams its meshes into the scene. Exposes
  `load()`/`fit()`/`pick()`/`resize()`/`dispose()`.
- `geometryInfo.js` - a separate, DISPLAY-only concern from the preview
  above: `describeGeometry(index, expressId)` walks one level into the
  selected element's chosen `IfcShapeRepresentation` to name the actual
  geometry classes involved (e.g. a Faceted Brep vs. an Advanced Brep, or
  resolving a mapped/instanced item to what it's an instance of), and
  `friendlyTypeLabel()` maps a `RepresentationType` to a human label for
  `InspectorPanel.jsx`. Pure and synchronous - reuses `StepFileIndex`'s
  already-built id->offset map, no new file scan, no worker round-trip, and
  no dependency on whether the element is even previewable (that's
  `stepIndex.js`'s `isPreviewable`, a separate check).

## Provenance

Ported from [`NepomukWolf/vscode-ifc`](https://github.com/NepomukWolf/vscode-ifc)
(`src/viewer/stepIndex.ts`, `src/viewer/subModel.ts`,
`media/viewer/thatopen-engine.ts`), MIT licensed:

```
MIT License

Copyright (c) NepomukWolf

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

Ported to plain JS for this project (TypeScript types dropped, Node `Buffer`
usage replaced with `Uint8Array`/manual byte handling, WASM path resolution
switched to Vite's `?url` asset import, VS Code-specific theme/window globals
replaced with this app's own CSS design tokens). Parsing/extraction logic is
otherwise unchanged from the original.
