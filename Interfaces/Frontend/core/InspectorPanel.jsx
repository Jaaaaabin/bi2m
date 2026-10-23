// React itself is not imported: @vitejs/plugin-react uses the automatic JSX runtime.
import { Component, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { friendlyTypeLabel } from "./engine/geometryInfo.js";
// ThatOpenPreviewEngine is intentionally NOT statically imported here - it (and
// the web-ifc WASM it pulls in) is only needed if the user actually clicks
// "Preview in 3D". A static import bundled it into the main chunk regardless,
// even for users who never open a preview. See the dynamic import() in
// ElementPreview3D's effect below - Vite code-splits it into its own chunk,
// fetched on first open instead of on initial page load.

// ======== Element Inspector (React island) ========
// Proof-of-concept for integrating React into this otherwise-vanilla-JS +
// @thatopen/ui (web components) app. Deliberately additive and isolated:
// this is the ONLY React code in the project, mounted into its own DOM node
// (#inspector-root, see index.html), and it never imports or touches OBC/BUI
// directly. The bridge to the imperative 3D/highlighting code in
// ThatOpenCompanyLoader.js is a plain CustomEvent pair on `window`:
//   "element-selected"          -> { detail: { fragmentID, expressID, fileName, properties, ifcClass } }
//   "element-deselected"        -> fired when the 3D selection is cleared elsewhere
//   "element-deselect-request"  -> dispatched BY this component when the user
//                                  closes the panel, so the 3D highlight clears too
// Either side could be swapped out independently (e.g. migrating more of the
// UI to React later) without touching this contract.
//
// "Preview in 3D" additionally reads two fields off that same detail object:
//   isPreviewable  -> whether ThatOpenCompanyLoader.js's STEP index found
//                      renderable geometry for this element
//   getPreviewData -> () => { ifcBytes, rootId, renderIds }, a closure over
//                      engine/subModel.js's extractSubModel - deferred so
//                      extraction only runs if the user opens the preview.
// The preview itself renders through engine/thatopenPreviewEngine.js, a small
// standalone web-ifc + ThatOpen renderer that is NOT the main Fragments-based
// viewer (see engine/README.md) - it exists solely for this isolated element
// close-up, fed a tiny self-contained IFC snippet rather than the full model.

const HIDDEN_KEYS = new Set([
  "expressID",
  "type",
  "Name",
  "GlobalId",
  "RepresentationIdentifier",
  "RepresentationType",
]);

function unwrap(value) {
  if (value && typeof value === "object" && "value" in value) return value.value;
  return value;
}

function formatKey(key) {
  return key.replace(/([a-z])([A-Z])/g, "$1 $2");
}

function ElementPreview3D({ selection }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | loading | ready | error
  const [errorMessage, setErrorMessage] = useState("");
  const containerRef = useRef(null);
  const engineRef = useRef(null);

  // Load (or reload) whenever the panel is opened. containerRef is only attached
  // to the DOM while `open`, so the engine (and its canvas) is created lazily on
  // first open rather than for every inspected element.
  useEffect(() => {
    if (!open || !containerRef.current) return;
    let cancelled = false;
    setStatus("loading");
    setErrorMessage("");

    (async () => {
      try {
        const data = selection.getPreviewData();
        const { ThatOpenPreviewEngine } = await import("./engine/thatopenPreviewEngine.js");
        if (cancelled) return;
        const engine = new ThatOpenPreviewEngine(containerRef.current);
        engineRef.current = engine;
        await engine.load({
          bytes: new Uint8Array(data.ifcBytes),
          rootId: data.rootId,
          renderIds: data.renderIds,
        });
        if (!cancelled) setStatus("ready");
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setErrorMessage(err.message);
        }
        console.error("⚠️ 3D preview failed:", err);
      }
    })();

    return () => {
      cancelled = true;
      engineRef.current?.dispose();
      engineRef.current = null;
    };
  }, [open]);

  // Keep the renderer's canvas in step with its container's actual size.
  useEffect(() => {
    if (!open || !containerRef.current) return;
    const el = containerRef.current;
    const observer = new ResizeObserver(() => {
      engineRef.current?.resize(el.clientWidth, el.clientHeight);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [open]);

  return (
    <div className="inspector-preview">
      <button
        type="button"
        className="inspector-preview-toggle"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? "Hide 3D preview" : "Preview in 3D"}
      </button>
      {open && (
        <div className="inspector-preview-viewport" ref={containerRef}>
          {status === "loading" && <div className="inspector-preview-status">Loading…</div>}
          {status === "error" && (
            <div className="inspector-preview-status inspector-preview-error">{errorMessage}</div>
          )}
        </div>
      )}
    </div>
  );
}

function ElementInspector() {
  // On first mount (lazy-loaded via inspectorBootstrap.js), pick up the
  // selection that triggered the load - see inspectorBootstrap.js for why
  // this can't just be a re-dispatched "element-selected" event.
  const [selection, setSelection] = useState(() => {
    const pending = window.__pendingElementSelection;
    window.__pendingElementSelection = null;
    return pending ?? null;
  });

  useEffect(() => {
    const onSelect = (event) => setSelection(event.detail);
    const onClear = () => setSelection(null);

    window.addEventListener("element-selected", onSelect);
    window.addEventListener("element-deselected", onClear);
    return () => {
      window.removeEventListener("element-selected", onSelect);
      window.removeEventListener("element-deselected", onClear);
    };
  }, []);

  if (!selection) return null;

  const { properties = {}, fileName, geometryInfo } = selection;
  const name = unwrap(properties.Name) || "(unnamed element)";
  const globalId = unwrap(properties.GlobalId);
  // ifcClass arrives resolved from the loader (OBC.IfcCategoryMap); the raw
  // numeric type code is only the fallback for an older event shape.
  const ifcClass = selection.ifcClass || unwrap(properties.type) || "(unknown)";
  // geometryInfo (engine/geometryInfo.js, computed in ThatOpenCompanyLoader.js's
  // selection handler) resolves the actual IfcShapeRepresentation.RepresentationType
  // and item entity classes - properties.RepresentationType is NOT a real flat
  // attribute (Representation is a reference to a nested entity), so this can't be
  // read directly off `properties`.
  const geometryLabel = geometryInfo
    ? friendlyTypeLabel(geometryInfo.type) || "(unspecified)"
    : "(none)";
  const geometryDetail = geometryInfo?.itemClasses?.filter(Boolean).join(", ");

  const rows = Object.entries(properties)
    .filter(([key]) => !HIDDEN_KEYS.has(key))
    .map(([key, value]) => [key, unwrap(value)])
    .filter(([, value]) => value !== null && value !== undefined && typeof value !== "object");

  const handleClose = () => {
    window.dispatchEvent(new CustomEvent("element-deselect-request"));
    setSelection(null);
  };

  return (
    <div className="inspector-panel">
      <div className="inspector-header">
        <strong className="inspector-title" title={globalId}>
          {globalId || "(no GUID)"}
        </strong>
        <button
          className="inspector-close"
          onClick={handleClose}
          title="Close inspector"
          aria-label="Close inspector"
        >
          ×
        </button>
      </div>
      <div className="inspector-meta">
        {fileName && <div className="inspector-file">File: {fileName}</div>}
        {ifcClass && <div className="inspector-class">Class: {ifcClass}</div>}
        {name && <div className="inspector-type">Type: {name}</div>}
        <div className="inspector-repr" title={geometryDetail || undefined}>
          Geometry: {geometryLabel}
        </div>
      </div>
      <div className="inspector-body">
        {rows.length === 0 ? (
          <div className="inspector-empty">No further properties available.</div>
        ) : (
          rows.map(([key, value]) => (
            <div className="inspector-row" key={key}>
              <span className="inspector-key">{formatKey(key)}</span>
              <span className="inspector-value">{String(value)}</span>
            </div>
          ))
        )}
      </div>
      {selection.isPreviewable && (
        <ElementPreview3D key={`${fileName}-${selection.expressID}`} selection={selection} />
      )}
    </div>
  );
}

// ======== Error boundary (2026-10-01) ========
// One element whose properties made the panel throw used to unmount the whole
// island for the rest of the session (React unmounts the root on an uncaught
// render error). The boundary keeps the root alive, says what happened,
// clears the 3D highlight on dismiss (the contract above), and resets itself
// on the next "element-selected" - stashing that event's detail the same way
// inspectorBootstrap.js does, so the remounted inspector shows it.
class InspectorErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
    this.onSelect = (event) => {
      if (!this.state.error) return;
      window.__pendingElementSelection = event.detail;
      this.setState({ error: null });
    };
    this.dismiss = () => {
      window.dispatchEvent(new CustomEvent("element-deselect-request"));
      this.setState({ error: null });
    };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Inspector render failed:", error, info?.componentStack);
  }

  componentDidMount() {
    window.addEventListener("element-selected", this.onSelect);
  }

  componentWillUnmount() {
    window.removeEventListener("element-selected", this.onSelect);
  }

  render() {
    if (!this.state.error) return this.props.children;
    const reason = String(this.state.error?.message ?? this.state.error);
    return (
      <div className="inspector-panel inspector-panel-error" role="alert">
        <div className="inspector-header">
          <strong className="inspector-title">Inspector unavailable</strong>
          <button
            className="inspector-close"
            onClick={this.dismiss}
            title="Close inspector"
            aria-label="Close inspector"
          >
            ×
          </button>
        </div>
        <div className="inspector-meta">
          <div className="inspector-file">This element could not be displayed: {reason}</div>
          <div className="inspector-type">Click another element to try again.</div>
        </div>
      </div>
    );
  }
}

const container = document.getElementById("inspector-root");
if (container) {
  createRoot(container).render(
    <InspectorErrorBoundary>
      <ElementInspector />
    </InspectorErrorBoundary>,
  );
} else {
  console.warn("⚠️ #inspector-root not found - element inspector not mounted.");
}
