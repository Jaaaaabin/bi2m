#!/usr/bin/env python3
"""Autocamera: batch snapshots of every model in the IFC library.

The simplest form of the batch pipeline: no Refer, no
per-intent scoping - walk the corpus, load each model into the viewer, apply
the camera panel's two whole-building presets ("Top" and "Side 45°") and
capture one PNG per view.

Usage (the dev server must be running: `npm run dev` in viewer):
    # BI2M_VIS_DIR (output folder) comes from .env or the environment
    uv run python scripts/autocamera.py                 # every model in the library
    uv run python scripts/autocamera.py --limit 3       # a sample
    uv run python scripts/autocamera.py --keys aead491da195f61a
    uv run python scripts/autocamera.py --dry-run
    uv run python scripts/autocamera.py --json /tmp/autocamera.json

REVIEW PACKETS (2026-10-01, the per-intent half the first version left open).
Every view is a VIEW SPEC now (viewer/views/viewSpec.js,
docs/architecture.md "Viewer"): the two whole-model views are the specs behind the "Top"
and "Side 45" buttons, applied through the app's own applyView (reached via
the viewerRegistry.js import hook), and `--spec FILE` replaces them with any list of
named specs. `--intents` adds,
per model and per recognized intent (the intent panel is kept open for it):
Refer by `data-intent-id`, then one offscreen fixed-size render per view - the type's rule views
(views/rules.js) unless `--spec` names others - saved as
<key>/packets/<key>-<intent id>-<view>.png with the full view record (and,
with `--score`, the visibility score) in meta.json under `packets`.

    uv run python scripts/autocamera.py --keys <key> --intents --score --out /tmp/vis
    uv run python scripts/autocamera.py --intents --intent-types alignment_column_group --intent-limit 5
    uv run python scripts/autocamera.py --spec my_views.json      # {"views": [{"name": ..., "spec": {...}}]}

WHY A BROWSER. The presets, the fit, the site/terrain exclusion and the unit
handling all live in the app (cameraViews.js, panels/filterPanel.js). A second
implementation in Python would produce pictures that are not what a reviewer
sees, and would fork the app's camera semantics. So this
drives the real viewer through the same DOM a person uses, and changes no app
source. It sits here rather than beside the e2e harnesses because it is a
batch tool, not a test: it asserts nothing, it renders - the same reason
build_vis_index.py and library_annotations.py live in this directory.

WHAT IT WRITES, AND WHERE. One folder per model under the vis directory, named
by the model's CONTENT key, which is the layout build_vis_index.py's docstring
mandates for renderer output:

    $BI2M_VIS_DIR/<content_key>/meta.json
    $BI2M_VIS_DIR/<content_key>/snapshots/top.png
    $BI2M_VIS_DIR/<content_key>/snapshots/side45.png

The names inside that tree come from paths.yaml's `vis_outputs` block (the same
on every machine); the ROOT is machine-specific, so it comes from --out or
BI2M_VIS_DIR, never from paths.yaml - see that file's own rule. Nothing here
touches index.json or annotations.json: those are owned by build_vis_index.py
and library_annotations.py, which rewrite them wholesale.

`meta.json` holds only facts that are true of the bytes - content key, size,
unit scale, storey list, mesh/vertex counts, and `complete` - plus a `render`
record of how the pictures were taken. No name and no number: the corpus is
renumbered after every screening pass, so a number in a file beside the bytes
stops describing them. The number lives in the vis index alone.

The model list comes from the dev server's /api/library-models route, so it is
content-keyed and already excludes the keys the index flags `absent`.

RESUMABLE. A model whose meta.json says `complete` and whose PNGs are all
present is skipped unless --force; a model that fails is retried, then recorded
and stepped over. meta.json is written LAST, so a run killed mid-capture leaves
no folder that looks finished. Re-running finishes what a crash, a timeout or
an HMR page reload interrupted.

READ-ONLY TOWARDS THE APP AND THE CORPUS. It loads models, moves the camera and
unloads. It never clicks Accept/Reject, never triggers Compute/Run, writes no
verdicts, and never writes into the corpus directory - only into the vis
directory. The one piece of browser state it sets is `bi2m:panelsOpenByDefault`
in its own throwaway browser profile, so the capture gets a full-width canvas;
nothing reaches the browser the user is looking at.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.append(str(REPO_ROOT / "src"))

from local_env import load_local_env  # noqa: E402

load_local_env()

try:
    from load_paths import load_vis_layout  # reads paths.yaml's `vis_outputs` block
except ImportError as err:  # PyYAML missing, or run from a copy outside the repo
    sys.exit(f"Could not read the output layout from paths.yaml ({err}). "
             "Run this with `uv run python scripts/autocamera.py`.")

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Playwright is required: `uv run python scripts/autocamera.py` "
             "(it is a project dependency), or `pip install playwright && "
             "playwright install chromium`")

# The viewer to drive. Defaults to the server the e2e harnesses read
# (viewer/scripts/e2e/_common.py), with its own override so a
# long run can be pointed at a private port and leave :3000 to whoever is
# working in it.
BASE_URL = os.environ.get(
    "BI2M_AUTOCAM_URL", os.environ.get("BI2M_E2E_URL", "http://localhost:3000/")
)
# Headless chromium renders through SwiftShader (software GL), exactly as the
# harnesses do. Fine for a still capture; frame times here are not evidence.
CHROMIUM_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]

V = "#viewerContainer1"  # the tile that exists at page load; every selector is scoped to it
# createViewerMenu builds this button, and unloadModelFromViewer empties the
# panel again - so its presence is a per-load signal, see wait_for_load().
READY_SELECTOR = f"{V} .viewer-fit-max-btn"

# The two whole-model views, as the VIEW SPECS behind the "Top" and "Side 45°"
# buttons (cameraViews.js VIEW_PRESETS, derived from the offset constants:
# "Top" is azimuth 0 / elevation 90, "Side 45°" is 45 / 45). Applied through
# the camera panel's View-JSON box they land on exactly the poses the buttons
# produce (scripts/e2e/views.py pins both to the pre-spec baseline), so the
# snapshots stay comparable with earlier runs. `expect_elevation` catches
# "the view did nothing" - a model whose building box could not be measured -
# not the fit's quality. `--spec FILE` replaces this list.
DEFAULT_VIEWS = [
    {"name": "top", "spec": {"scope": {"kind": "building"}, "direction": {"azimuthDeg": 0, "elevationDeg": 90}},
     "expect_elevation": 90.0},
    {"name": "side45", "spec": {"scope": {"kind": "building"}, "direction": {"azimuthDeg": 45, "elevationDeg": 45}},
     "expect_elevation": 45.0},
]
ELEVATION_TOLERANCE_DEG = 2.0


def load_views(path):
    """`--spec FILE`: {"views": [{"name", "spec", "expect_elevation"?}]} or a plain list."""
    try:
        data = json.loads(Path(path).expanduser().read_text())
    except (OSError, ValueError) as err:
        sys.exit(f"--spec {path}: {err}")
    views = data.get("views") if isinstance(data, dict) else data
    if not isinstance(views, list) or not views:
        sys.exit(f"--spec {path}: expected a non-empty list of {{name, spec}} views")
    out = []
    for i, view in enumerate(views):
        if not isinstance(view, dict) or not isinstance(view.get("spec"), dict):
            sys.exit(f"--spec {path}: view {i} needs a 'spec' object")
        name = str(view.get("name") or f"view{i + 1}")
        if not name.replace("-", "").replace("_", "").isalnum():
            sys.exit(f"--spec {path}: view name {name!r} must be letters, digits, '-' or '_' (it becomes a file name)")
        out.append({"name": name, "spec": view["spec"], "expect_elevation": view.get("expect_elevation")})
    return out

# ---- live state, read through the viewerRegistry.js import hook -----------
# Resolve the URL the app ACTUALLY loaded: after any edit Vite rewrites
# importers to /viewerRegistry.js?t=<ts>, and a bare path would import a
# SECOND module instance whose viewerData is empty. Returns plain numbers and
# strings only - THREE objects do not survive the CDP boundary.
STATE_JS = """async () => {
  const url = performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => /\\/viewerRegistry\\.js(\\?|$)/.test(n)).pop() || '/viewerRegistry.js';
  const { viewerData } = await import(url);
  const v = viewerData[0];
  if (!v) return null;
  let meshes = 0, verts = 0;
  v.world.scene.three.traverse((o) => {
    if (o.isMesh || o.isInstancedMesh) {
      meshes++;
      const pos = o.geometry && o.geometry.attributes && o.geometry.attributes.position;
      if (pos) verts += pos.count;
    }
  });
  const c = v.world.camera.controls;
  const V3 = v.world.camera.three.position.constructor;
  const p = c.getPosition(new V3()), t = c.getTarget(new V3());
  const d = [p.x - t.x, p.y - t.y, p.z - t.z];
  const n = Math.hypot(...d) || 1;
  return {
    meshes, verts,
    // Storey names for THIS model only. The tile's Classifier is created once
    // and reused for every load, and @thatopen's disposal handler empties a
    // group's fragment map without deleting the group - so the plain key list
    // is the UNION of every model this page has seen (proven on this corpus:
    // 0081.ifc came back carrying 0001.ifc's "Level -2"). A group whose map
    // still holds fragments belongs to the model on screen; an emptied one is
    // a ghost of a model already unloaded.
    storeys: Object.entries((v.classifier && v.classifier.list.spatialStructures) || {})
      .filter(([, g]) => g && g.map && Object.keys(g.map).length > 0)
      .map(([name]) => name).sort(),
    distance: +c.distance.toFixed(3),
    // Degrees above horizontal, the convention the panel's own readout uses.
    elevation: +(90 - (Math.atan2(Math.hypot(d[0], d[2]), d[1]) * 180) / Math.PI).toFixed(2),
    direction: d.map((x) => +(x / n).toFixed(4)),
    projection: v.world.camera.projection.current,
  };
}"""

# ---- the view record, the fixed-size image, the rules and the score --------
# All read through the same resolved-URL import as STATE_JS: the app's own
# modules, never a second implementation.
_MODS_JS = """
  const pick = (re, fallback) => performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => re.test(n)).pop() || fallback;
  const { viewerData } = await import(pick(/\\/viewerRegistry\\.js(\\?|$)/, '/viewerRegistry.js'));
  const v = viewerData[0];
  if (!v) return null;
"""
RECORD_JS = "async () => {" + _MODS_JS + """
  return v.lastViewRecord ?? null;
}"""
IMAGE_JS = "async () => {" + _MODS_JS + """
  const i = v.lastViewImage; return i ? { dataUrl: i.dataUrl, width: i.width, height: i.height } : null;
}"""
RULES_JS = "async (intent) => {" + _MODS_JS + """
  const rules = await import(pick(/\\/views\\/rules\\.js(\\?|$)/, '/views/rules.js'));
  return rules.viewsForIntent(intent);
}"""
SCORE_JS = "async (guids) => {" + _MODS_JS + """
  const vis = await import(pick(/\\/views\\/visibility\\.js(\\?|$)/, '/views/visibility.js'));
  return vis.measureVisibility(v.world, { guids });
}"""
# A spec is applied by calling the app's own applyView (views/applyView.js)
# on the live world - the View-JSON box left the camera panel on 2026-10-01.
# It sets data-view-status on the tile and emits view-applied like any other
# apply, and resolves with the view record.
APPLY_JS = "async ([spec, options]) => {" + _MODS_JS + """
  const m = await import(pick(/\\/views\\/applyView\\.js(\\?|$)/, '/views/applyView.js'));
  try { return { ok: true, record: await m.applyView(v.world, spec, options) }; }
  catch (e) { return { ok: false, error: String(e?.message ?? e) }; }
}"""

# ---- clean capture -------------------------------------------------------
# Hide everything that paints over the rectangle about to be captured, with
# `visibility` and never `display`: visibility keeps the layout, so the canvas
# is not resized and the framing already computed stays exactly as it is.
#
# Deliberately geometric rather than a list of selectors. The tile's chrome
# moved twice on 2026-09-23 and a stale selector list silently puts a button in
# the picture; and some overlays (the element inspector, the ?hud panel) are
# position: fixed OUTSIDE the tile, so a tile-scoped walk would miss them.
# Anything whose box intersects the capture rectangle, and which is not the
# canvas or one of its ancestors, is hidden.
MASK_JS = """() => {
  const canvas = document.querySelector('#viewerContainer1 canvas');
  const area = document.querySelector('#viewerContainer1 .viewer-canvas-area');
  if (!canvas || !area) return -1;
  const clip = area.getBoundingClientRect();
  const hits = (r) => r.width > 0 && r.height > 0 &&
    r.right > clip.left && r.left < clip.right && r.bottom > clip.top && r.top < clip.bottom;
  const hidden = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (el === canvas || el.contains(canvas)) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    if (!hits(el.getBoundingClientRect())) continue;
    hidden.push(el);
    el.style.visibility = 'hidden';
  }
  window.__autocamMask = hidden;
  return hidden.length;
}"""
UNMASK_JS = """() => {
  const hidden = window.__autocamMask || [];
  hidden.forEach((el) => { el.style.visibility = ''; });
  window.__autocamMask = null;
  return hidden.length;
}"""

# The tile's error overlay is created once and toggled, so its presence proves
# nothing - only its visibility does (ThatOpenCompanyLoader.js).
ERROR_JS = """() => {
  const el = document.querySelector('#viewerContainer1 .viewer-error');
  if (el) {
    const style = getComputedStyle(el);
    if (style.display !== 'none' && style.visibility !== 'hidden') {
      return (el.textContent || 'viewer error').trim().slice(0, 200);
    }
  }
  // The flyout reports a failed byte fetch in its own status line - a stale
  // index answers 409 and the model never reaches the tile at all, so without
  // this the run would wait out the whole per-model budget for nothing.
  const status = document.querySelector('#library-models-flyout .library-models-status');
  if (status && status.offsetParent !== null) return (status.textContent || '').trim().slice(0, 200);
  return null;
}"""


def fetch_models(base_url, timeout=120):
    """The library as the dev server sees it: content key -> name, size, annotation.

    The route re-reads the corpus vis index on every request and drops the keys
    it flags `absent`, so this is the models that are on disk right now.
    """
    url = base_url.rstrip("/") + "/api/library-models"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type") or ""
            body = response.read()
    except urllib.error.HTTPError as err:
        payload = err.read()
        try:
            message = json.loads(payload).get("error", "")
        except (ValueError, TypeError):
            message = payload[:200].decode("utf-8", "replace")
        sys.exit(f"{url} answered {err.code}: {message}")
    except OSError as err:
        sys.exit(f"Could not reach the dev server at {base_url} ({err}). "
                 "Start it with `npm run dev` in viewer.")
    if "json" not in content_type:
        # The SPA fallback answered: this server predates the route, or it is a
        # production build, which has no dev-only API at all.
        sys.exit(f"{url} did not answer with JSON - this server has no library "
                 "route (restart `npm run dev`; a production build has none).")
    payload = json.loads(body)
    if not payload.get("ok") or not payload.get("files"):
        sys.exit(f"{url} lists no models: {payload.get('error', payload)}")
    return payload["corpus"], payload["files"]


def view_file_name(layout, name):
    """paths.yaml names the two classic views; any other spec is <name>.png."""
    return layout["views"].get(name, f"{name}.png")


def outputs_for(out_dir, layout, key, view_names):
    """Where this model's meta.json, snapshots and packets live."""
    model_dir = Path(out_dir) / key
    snapshots = model_dir / layout["snapshots_dir"]
    return {
        "dir": model_dir,
        "meta": model_dir / layout["meta_file"],
        "views": {name: snapshots / view_file_name(layout, name) for name in view_names},
        "packets": model_dir / layout.get("packets_dir", "packets"),
    }


def packet_path(paths, layout, key, intent_id, view_name):
    pattern = layout.get("packet_file", "{content_key}-{intent_id}-{view}.png")
    return paths["packets"] / pattern.format(content_key=key, intent_id=intent_id, view=view_name)


def already_rendered(paths, view_names, want_packets):
    """True only for a folder a previous run FINISHED: meta.json is written
    last and carries `complete`, so a half-written folder is re-rendered. A
    packets run also needs the packets to have been finished."""
    if not paths["meta"].exists():
        return False
    try:
        meta = json.loads(paths["meta"].read_text())
    except (ValueError, OSError):
        return False
    if not meta.get("complete") or not all(v in (meta.get("snapshots") or {}) for v in view_names):
        return False
    if want_packets and not meta.get("packets_complete"):
        return False
    return all(p.exists() and p.stat().st_size > 0 for p in paths["views"].values())


def fetch_shard(base_url, key, timeout=60):
    """This model's recognized intents, as the viewer loads them (res/intents/<key>.json)."""
    url = base_url.rstrip("/") + f"/res/intents/{key}.json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if "json" not in (response.headers.get("Content-Type") or ""):
                return []
            shard = json.loads(response.read())
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return []
        raise
    return shard.get("intents") or [] if isinstance(shard, dict) else []


class Viewer:
    """One page, one tile, reused for every model in the run."""

    def __init__(self, context, settle_polls, settle_interval_ms, timeout_s, model_timeout_s):
        self.context = context
        self.page = None
        self.errors = []
        self.settle_polls = settle_polls
        self.settle_interval_ms = settle_interval_ms
        self.timeout_s = timeout_s
        self.model_timeout_s = model_timeout_s
        self.model_deadline = None

    def begin_model(self):
        """One wall-clock budget for a whole model. --timeout bounds each
        individual wait and there are half a dozen per attempt, so without this
        a single pathological model could eat an hour of the run."""
        self.model_deadline = time.time() + self.model_timeout_s

    def _deadline(self, seconds=None):
        limit = time.time() + (self.timeout_s if seconds is None else seconds)
        return min(limit, self.model_deadline) if self.model_deadline else limit

    def _wire(self, page):
        page.on("pageerror", lambda e: self.errors.append(str(e)[:200]))
        page.on("console", lambda m: m.type == "error" and self.errors.append(m.text[:200]))

    # -- page lifecycle ----------------------------------------------------
    def open(self, base_url):
        """Open, or re-open, the viewer. A page whose renderer crashed cannot
        be navigated, so a closed one is replaced rather than reused -
        otherwise one crash ends the whole run."""
        if self.page is None or self.page.is_closed():
            self.page = self.context.new_page()
            self._wire(self.page)
        self.page.goto(base_url, wait_until="networkidle")
        # The flyout fetches its list once per page; warm it here so the first
        # model of a page does not pay for it inside its own timing.
        self.page.click("#library-models-btn")
        self.page.wait_for_selector("#library-models-flyout .library-models-item", timeout=120000)
        self.page.keyboard.press("Escape")  # page/popover.js closes it on Escape

    # -- per model ---------------------------------------------------------
    def load(self, key):
        """Pick one model out of the library flyout by content key."""
        page = self.page
        page.click("#library-models-btn")
        page.wait_for_selector("#library-models-flyout .library-models-item", timeout=120000)
        # Filter by the key's first hex digits so one row is left; the flyout
        # matches a key by prefix. The exact key is still what gets clicked.
        page.fill("#library-models-flyout .library-models-search", key[:8])
        page.wait_for_timeout(250)
        item = page.locator(f'#library-models-flyout .library-models-item[data-file-key="{key}"]')
        if item.count() == 0:
            raise RuntimeError(f"{key} is not in the flyout's list")
        item.first.click()
        self.wait_for_load()

    def wait_for_load(self):
        """Wait until the load pipeline has finished, not merely started.

        `.has-model` is set early (loader Step 2) and the camera is fitted
        twice after it: once immediately, and again at Step 6.5 once
        classification can tell site/terrain apart. Step 7 then builds the
        camera panel. So the FIRST moment the preset buttons exist is also the
        first moment no further automatic re-fit is coming - which is why the
        gate is the button, not the class. Waiting on `.has-model` alone would
        let a preset click race the Step 6.5 snap and silently capture the
        aerial load pose labelled "top".
        """
        deadline = self._deadline()
        while time.time() < deadline:
            error = self.page.evaluate(ERROR_JS)
            if error:
                raise RuntimeError(f"the viewer reported: {error}")
            if self.page.locator(READY_SELECTOR).count() > 0:
                return
            self.page.wait_for_timeout(self.settle_interval_ms)
        raise TimeoutError("no camera panel before the deadline (the model did not finish loading)")

    def open_camera_panel(self):
        """The presets live in the camera panel, which is position: absolute
        and a child of the canvas area - opening it re-frames nothing, it only
        makes the buttons clickable, since the closed panel is visibility:
        hidden; pointer-events: none."""
        if not self.page.locator(V).evaluate("el => el.classList.contains('camera-open')"):
            self.page.click(f"{V} .viewer-camera-toggle-btn")
            self.page.wait_for_timeout(250)  # --transition-fast is 0.2s

    def settle(self, label):
        """Wait until the scene and the camera both stop changing.

        Geometry: a parsed .ifc is fully in the scene before `.has-model` is
        set (measured on the corpus's largest file, 21.8 MiB: all 8606 meshes
        at t+1.5s, never growing), but five library models have a pre-built
        tile set and stream their fragments in batches - so mesh and vertex
        counts are polled too, not just the pose.
        Pose: a preset's fit is instant (camera-controls with
        enableTransition=false resolves synchronously and copies the end state
        into the live state), so this is normally satisfied on the first poll -
        it is insurance against a late re-fit, not the mechanism.
        """
        page, previous, stable = self.page, None, 0
        deadline = self._deadline()
        while time.time() < deadline:
            state = page.evaluate(STATE_JS)
            if state is not None and state == previous:
                stable += 1
                if stable >= self.settle_polls:
                    return state
            else:
                stable = 0
            previous = state
            page.wait_for_timeout(self.settle_interval_ms)
        raise TimeoutError(f"{label}: still moving at the deadline (last {previous})")

    def apply_spec(self, spec, label, score=False):
        """Apply a view spec through the app's own applyView (views/applyView.js)
        and return the view record it measured, after
        the pose has settled - the fit is instant, so the settle is insurance.
        `score` attaches the visibility score to the record."""
        result = self.page.evaluate(APPLY_JS, [spec, {"chosenBy": "batch", "score": bool(score)}])
        if result is None:
            raise RuntimeError(f"{label}: no viewer on the page")
        if not result.get("ok"):
            raise RuntimeError(f"{label}: the view was refused - {result.get('error', '')[:200]}")
        self.settle(label)
        return result["record"]

    def refer(self, intent_id):
        """Refer one intent by id: open its category section first, select by
        identity, wait on the signal."""
        page = self.page
        page.evaluate("""(id) => {
          const row = document.querySelector(`#viewerContainer1 [data-intent-id="${id}"]`);
          if (!row) return false;
          for (let el = row; el; el = el.parentElement) if (el.tagName === 'DETAILS') el.open = true;
          return true;
        }""", intent_id)
        row = page.locator(f'{V} [data-intent-id="{intent_id}"]')
        if row.count() == 0:
            raise RuntimeError(f"intent {intent_id} has no row in the panel")
        row.locator(".intent-refer-btn").click()
        page.wait_for_selector(f'{V} [data-intent-id="{intent_id}"][data-refer-status="done"]',
                               timeout=int(self.timeout_s * 1000))

    def rule_views(self, intent):
        """The type's starting views, from the app's own rules table."""
        return self.page.evaluate(RULES_JS, intent) or []

    def score(self, guids):
        """The visibility score of the current camera for these members."""
        return self.page.evaluate(SCORE_JS, guids)

    def save_image(self, path):
        """Write the fixed-size offscreen render the last spec produced."""
        image = self.page.evaluate(IMAGE_JS)
        if not image:
            raise RuntimeError("the spec produced no image (did it carry an `image` field?)")
        header, _, payload = image["dataUrl"].partition(",")
        if "image/png" not in header:
            raise RuntimeError("the image is not a PNG data URL")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(payload))
        return {"image_pixels": [image["width"], image["height"]], "bytes": path.stat().st_size}

    def capture(self, path, scale):
        """Screenshot the canvas rectangle with everything over it hidden.

        A CLIPPED PAGE screenshot, not locator.screenshot(): the latter first
        waits for the element to be stable across animation frames, and under
        SwiftShader a 20 MiB model paints slowly enough that the wait times out
        (measured: 0081.ifc failed at 18.8 s). Playwright crops the composited
        page either way - which is why the mask, not the choice of element, is
        what removes the chrome.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        box = self.page.locator(f"{V} .viewer-canvas-area").bounding_box()
        if not box or box["width"] < 1 or box["height"] < 1:
            raise RuntimeError("the canvas area has no size")
        viewport = self.page.viewport_size or {"width": 0, "height": 0}
        clip = {
            "x": max(0.0, box["x"]),
            "y": max(0.0, box["y"]),
            "width": min(box["width"], viewport["width"] - max(0.0, box["x"])),
            "height": min(box["height"], viewport["height"] - max(0.0, box["y"])),
        }
        if clip["width"] < 1 or clip["height"] < 1:
            raise RuntimeError("the canvas area is outside the viewport - widen it with --width/--height")
        masked = self.page.evaluate(MASK_JS)
        if masked < 0:
            raise RuntimeError("no canvas in the tile")
        if masked == 0:
            raise RuntimeError("the mask hid nothing - this page is not the viewer we expect")
        try:
            self.page.screenshot(path=str(path), clip=clip, timeout=int(self.timeout_s * 1000))
        finally:
            restored = self.page.evaluate(UNMASK_JS)
        if restored != masked:
            # window.__autocamMask did not survive: the page navigated between
            # the mask and the shot - an HMR full reload from someone editing
            # public/res/ mid-run - so the PNG is of a blank, reloading page.
            path.unlink(missing_ok=True)
            raise RuntimeError("the page reloaded during the capture")
        return {
            "css_pixels": [round(clip["width"]), round(clip["height"])],
            "image_pixels": [round(clip["width"] * scale), round(clip["height"] * scale)],
            "bytes": path.stat().st_size,
        }

    def unload(self):
        """Release the model but keep the tile, so the next model reuses it.
        Also empties the camera panel (which is what resets the readiness gate)
        and puts the camera back on the tile's opening pose."""
        self.page.click(f"{V} .viewer-unload-btn")
        deadline = self._deadline(min(self.timeout_s, 60))
        while time.time() < deadline:
            if (self.page.locator(f"{V}.has-model").count() == 0
                    and self.page.locator(READY_SELECTOR).count() == 0):
                return True
            self.page.wait_for_timeout(250)
        return False

    def heap_mb(self):
        return self.page.evaluate(
            "() => performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null"
        )


def render_model(viewer, model, paths, views, args, layout, intents=None):
    """Load one model, apply each view, capture, then the packets; write meta.json last."""
    started = time.time()
    key = model["fileKey"]
    viewer.load(key)
    loaded = viewer.settle("after load")
    viewer.open_camera_panel()

    snapshots, warnings = {}, []
    for view in views:
        record = viewer.apply_spec(view["spec"], f"view {view['name']}")
        resolved = record["resolved"]
        expected = view.get("expect_elevation")
        if expected is not None and abs(resolved["worldElevationDeg"] - expected) > ELEVATION_TOLERANCE_DEG:
            # The view did not land: almost always a model whose building
            # bounding box could not be measured, so there was nothing to fit.
            # Capture anyway and say so, rather than writing a confident-looking
            # picture of the wrong view.
            warnings.append(f"{view['name']}: elevation {resolved['worldElevationDeg']:.2f}°, expected {expected}° "
                            "(the fit did not apply)")
        if resolved.get("scope", {}) and resolved["scope"].get("unmeasurable"):
            warnings.append(f"{view['name']}: {resolved['scope']['unmeasurable']}")
        image = viewer.capture(paths["views"][view["name"]], args.scale)
        snapshots[view["name"]] = {
            "file": str(paths["views"][view["name"]].relative_to(paths["dir"])),
            # The classic fields, for anything that read schema 1 ...
            "elevation_deg": round(resolved["worldElevationDeg"], 2),
            "distance_m": round(resolved["distance"], 3),
            "direction": [round(x, 4) for x in resolved["worldDirection"]],
            "projection": resolved["projection"],
            # ... and the whole view record.
            "record": record,
            **image,
        }

    packets, packets_done = {}, False
    if intents is not None:
        width, height = args.image
        for intent in intents:
            intent_id = intent["id"]
            try:
                viewer.refer(intent_id)
                intent_views = (
                    [{"name": v["name"], "spec": v["spec"], "rule": None} for v in args.packet_views]
                    if args.packet_views else
                    [{"name": v["name"], "spec": v["spec"], "rule": v.get("rule")} for v in viewer.rule_views(intent)]
                )
                members = [m["guid"] for m in intent.get("members", []) if m.get("role") != "context"]
                entry = {"type": intent.get("type"), "label": intent.get("label"), "views": {}}
                for view in intent_views:
                    spec = {**view["spec"], "scope": {"kind": "intent", "intentId": intent_id},
                            "image": {"width": width, "height": height}}
                    label = f"{intent_id[:40]} {view['name']}"
                    record = viewer.apply_spec(spec, label, score=bool(args.score and members))
                    if record["resolved"].get("scope", {}).get("unmeasurable"):
                        warnings.append(f"{label}: {record['resolved']['scope']['unmeasurable']}")
                    target = packet_path(paths, layout, key, intent_id, view["name"])
                    image = viewer.save_image(target)
                    entry["views"][view["name"]] = {
                        "file": str(target.relative_to(paths["dir"])),
                        "rule": view.get("rule"),
                        "record": record,
                        **image,
                    }
                packets[intent_id] = entry
            except (PlaywrightError, TimeoutError, RuntimeError) as err:
                message = f"{type(err).__name__}: {err}".splitlines()[0][:200]
                warnings.append(f"{intent_id[:40]}: {message}")
                packets[intent_id] = {"type": intent.get("type"), "error": message, "views": {}}
        packets_done = True
        # Leave the tile as a whole-model view for the unload that follows.
        try:
            viewer.page.click(f"{V} .intent-clear-btn")
        except PlaywrightError:
            pass

    annotation = model.get("annotation") or {}
    meta = {
        # Facts about the bytes. Deliberately no name and no number: those are
        # rewritten by every screening pass and live in the vis index alone
        # (scripts/build_vis_index.py's docstring).
        "content_key": key,
        "size_bytes": model["sizeBytes"],
        # From the vis annotations (byte-level, scripts/library_annotations.py);
        # absent when the corpus has not been annotated.
        "unit_scale": annotation.get("unit_scale"),
        "storeys": loaded["storeys"],
        "meshes": loaded["meshes"],
        "vertices": loaded["verts"],
        "snapshots": snapshots,
        "render": {
            "tool": "scripts/autocamera.py",
            # 2 since 2026-10-01: every snapshot carries its view record, and
            # `packets` holds the per-intent views.
            "schema": 2,
            "app_url": args.url,
            "viewport": [args.width, args.height],
            "device_scale_factor": args.scale,
            "intent_panel_open": bool(args.panels),
            "views": [v["name"] for v in views],
            "packets": None if intents is None else {
                "image": list(args.image), "scored": bool(args.score), "count": len(intents),
                "views": "spec" if args.packet_views else "rules",
            },
            "rendered_at": datetime.now().isoformat(timespec="seconds"),
            "seconds": round(time.time() - started, 1),
        },
        # Written last, inside the file that is itself written last: together
        # they are what makes a resumed run able to tell finished from
        # interrupted.
        "complete": True,
    }
    if intents is not None:
        meta["packets"] = packets
        meta["packets_complete"] = packets_done
    if warnings:
        meta["render"]["warnings"] = warnings
    paths["meta"].parent.mkdir(parents=True, exist_ok=True)
    paths["meta"].write_text(json.dumps(meta, indent=2) + "\n")
    return meta, warnings


def build_parser(layout):
    parser = argparse.ArgumentParser(
        description="Batch snapshots of the IFC library, and review packets per intent.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--url", default=BASE_URL,
                        help="the running viewer (env: BI2M_AUTOCAM_URL, then BI2M_E2E_URL)")
    parser.add_argument("--out", default=os.environ.get("BI2M_VIS_DIR"),
                        help="vis directory to write into (env: BI2M_VIS_DIR)")
    parser.add_argument("--views", default=",".join(v["name"] for v in DEFAULT_VIEWS),
                        help="comma-separated subset of the view names (the defaults, or --spec's)")
    parser.add_argument("--spec", help="JSON file of named view specs replacing the two defaults "
                                       "({\"views\": [{\"name\": ..., \"spec\": {...}}]})")
    parser.add_argument("--intents", action="store_true",
                        help="also render review packets: per recognized intent, Refer and one offscreen "
                             "render per view (the type's rule views, or --spec's)")
    parser.add_argument("--intent-types", help="comma-separated intent types to pack (default: all)")
    parser.add_argument("--intent-limit", type=int, help="at most N intents per model")
    parser.add_argument("--image", default="1280x800", help="packet image size, WIDTHxHEIGHT (offscreen render)")
    parser.add_argument("--score", action="store_true",
                        help="attach the visibility score (views/visibility.js) to every packet record")
    parser.add_argument("--limit", type=int, help="only the first N models of the selection")
    parser.add_argument("--keys", help="comma-separated content keys, instead of the whole library")
    parser.add_argument("--force", action="store_true", help="re-render models that already have output")
    parser.add_argument("--dry-run", action="store_true", help="list what would be rendered, write nothing")
    parser.add_argument("--width", type=int, default=1600, help="browser viewport width")
    parser.add_argument("--height", type=int, default=1000, help="browser viewport height")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="device scale factor; 2 doubles the PNG's pixels at the same framing")
    parser.add_argument("--panels", action="store_true",
                        help="capture with the intent panel open, the review-packet framing; "
                             "the default closes it, which is a wider canvas for a whole-model view")
    parser.add_argument("--retries", type=int, default=1,
                        help="extra attempts per model after a failure (the page is reloaded between them)")
    parser.add_argument("--reload-every", type=int, default=25,
                        help="reload the page every N models (0 = never)")
    parser.add_argument("--settle-polls", type=int, default=4,
                        help="consecutive identical polls that count as settled")
    parser.add_argument("--settle-interval", type=int, default=250, help="ms between polls")
    parser.add_argument("--timeout", type=float, default=300.0, help="seconds per wait before giving up")
    parser.add_argument("--model-timeout", type=float, default=600.0,
                        help="seconds for one whole model, across all of its waits")
    parser.add_argument("--json", help="write a run report to this path")
    parser.epilog = ("Output layout comes from paths.yaml's vis_outputs block: "
                     f"<key>/{layout['meta_file']}, <key>/{layout['snapshots_dir']}/"
                     f"{{{', '.join(layout['views'].values())}}} and, with --intents, "
                     f"<key>/{layout.get('packets_dir', 'packets')}/{layout.get('packet_file', '{content_key}-{intent_id}-{view}.png')}")
    return parser


def main():
    layout = load_vis_layout()
    args = build_parser(layout).parse_args()

    for name, value, floor in (("--limit", args.limit, 1), ("--retries", args.retries, 0),
                               ("--reload-every", args.reload_every, 0),
                               ("--settle-polls", args.settle_polls, 1)):
        if value is not None and value < floor:
            hint = " (omit --limit entirely to render everything)" if name == "--limit" else ""
            sys.exit(f"{name} must be {floor} or more, got {value}{hint}")
    if args.scale <= 0:
        sys.exit(f"--scale must be positive (got {args.scale})")

    all_views = load_views(args.spec) if args.spec else DEFAULT_VIEWS
    # With --spec the named specs serve both the whole-model snapshots and the
    # packets (scope overridden to the intent); without it the packets use
    # the type's rule views and the snapshots the two classic ones.
    args.packet_views = all_views if args.spec else None
    names = [v.strip() for v in args.views.split(",") if v.strip()]
    by_name = {v["name"]: v for v in all_views}
    unknown = [v for v in names if v not in by_name]
    if unknown:
        sys.exit(f"Unknown view(s): {', '.join(unknown)}. Known: {', '.join(by_name)}")
    views = [by_name[n] for n in names]
    if not views:
        sys.exit("No views selected.")
    try:
        w, h = (int(x) for x in args.image.lower().split("x"))
        if not (64 <= w <= 8192 and 64 <= h <= 8192):
            raise ValueError
        args.image = (w, h)
    except ValueError:
        sys.exit(f"--image must be WIDTHxHEIGHT with both in [64, 8192], got {args.image!r}")
    intent_types = {t.strip() for t in (args.intent_types or "").split(",") if t.strip()} or None
    if args.intents and not args.panels:
        # Refer lives in the intent panel, which the default framing closes
        # (a wider canvas for the whole-model views). Packets are rendered
        # offscreen at their own size, so the narrower canvas costs nothing;
        # measured 2026-10-01: with the panel closed every Refer click timed out.
        args.panels = True
    if args.intent_limit is not None and args.intent_limit < 1:
        sys.exit("--intent-limit must be 1 or more")

    if not args.out:
        sys.exit("No output folder: pass --out or set BI2M_VIS_DIR (in .env at the repository root, see .env.example)")
    out_dir = Path(args.out).expanduser()
    corpus, models = fetch_models(args.url)
    if args.keys:
        wanted = {k.strip() for k in args.keys.split(",") if k.strip()}
        by_key = {m["fileKey"]: m for m in models}
        absent = sorted(wanted - by_key.keys())
        if absent:
            sys.exit(f"Not in the library: {', '.join(absent)}")
        models = [by_key[k] for k in sorted(wanted)]
    if args.limit is not None:
        models = models[: args.limit]

    view_names = [v["name"] for v in views]
    todo, skipped = [], []
    for model in models:
        paths = outputs_for(out_dir, layout, model["fileKey"], view_names)
        finished = already_rendered(paths, view_names, args.intents) and not args.force
        (skipped if finished else todo).append((model, paths))

    print(f"autocamera: {corpus} via {args.url}")
    print(f"  {len(models)} model(s) selected, {len(skipped)} already rendered, {len(todo)} to render")
    print(f"  views: {', '.join(view_names)}" + (f"   spec: {args.spec}" if args.spec else "") + f"   out: {out_dir}")
    if args.intents:
        print(f"  packets: {'--spec views' if args.spec else 'rule views'} at {args.image[0]}x{args.image[1]}"
              + (f", types {', '.join(sorted(intent_types))}" if intent_types else "")
              + (f", at most {args.intent_limit} per model" if args.intent_limit else "")
              + (", scored" if args.score else ""))
    if args.dry_run:
        for model, paths in todo:
            print(f"  would render {model['fileKey']} ({model['fileName']}) -> {paths['dir']}")
        return 0
    if not todo:
        print("  nothing to do (use --force to re-render)")
        return 0

    # Probe the destination BEFORE a model is rendered: an unwritable --out
    # would otherwise surface only after two full loads.
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        probe = out_dir / ".autocamera-write-test"
        probe.write_text("")
        probe.unlink()
    except OSError as err:
        sys.exit(f"Cannot write to {out_dir}: {err}")
    if args.json:
        report_path = Path(args.json).expanduser()
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            sys.exit(f"Cannot write the report to {report_path}: {err}")

    done, failed, warned = [], [], []
    started = time.time()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=CHROMIUM_ARGS)
        context = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=args.scale,
        )
        # Playwright's own default action timeout is 30s and is NOT governed by
        # --timeout: a slow SwiftShader frame made one click miss it in the
        # first full run (0156.ifc). Give clicks the same budget as the waits.
        context.set_default_timeout(int(args.timeout * 1000))

        # A throwaway profile: this never reaches the browser the user is in.
        # Panels open by default (ThatOpenCompanyLoader.js), and the intent
        # panel is a flex sibling that narrows the canvas, so closing it before
        # the first load is what buys the wider frame - toggling it afterwards
        # would leave the fit stale.
        if not args.panels:
            context.add_init_script(
                "try { localStorage.setItem('bi2m:panelsOpenByDefault', '0'); } catch {}"
            )
        viewer = Viewer(context, args.settle_polls, args.settle_interval,
                        args.timeout, args.model_timeout)
        errors = viewer.errors
        try:
            viewer.open(args.url)

            for index, (model, paths) in enumerate(todo, start=1):
                key = model["fileKey"]
                label = (f"[{index}/{len(todo)}] {key} ({model['fileName']}, "
                         f"{model['sizeBytes'] / 1048576:.1f} MiB)")
                outcome = None
                for attempt in range(args.retries + 1):
                    del errors[:]
                    viewer.begin_model()
                    try:
                        intents = None
                        if args.intents:
                            intents = fetch_shard(args.url, key)
                            if intent_types:
                                intents = [i for i in intents if i.get("type") in intent_types]
                            if args.intent_limit:
                                intents = intents[: args.intent_limit]
                        meta, warnings = render_model(viewer, model, paths, views, args, layout, intents)
                        took = meta["render"]["seconds"]
                        sizes = " ".join(f"{v}={meta['snapshots'][v]['bytes'] // 1024}KB" for v in view_names)
                        packets_note = ""
                        if intents is not None:
                            n_ok = sum(1 for p in meta["packets"].values() if not p.get("error"))
                            n_png = sum(len(p["views"]) for p in meta["packets"].values())
                            packets_note = f"  packets: {n_ok}/{len(intents)} intents, {n_png} png"
                        print(f"{label} ok in {took}s  {sizes}{packets_note}", flush=True)
                        for warning in warnings:
                            print(f"    warning: {warning}", flush=True)
                            warned.append({"key": key, "warning": warning})
                        done.append({"key": key, "seconds": took, "attempts": attempt + 1})
                        outcome = "ok"
                        break
                    except (PlaywrightError, TimeoutError, RuntimeError, OSError) as err:
                        message = f"{type(err).__name__}: {err}".splitlines()[0][:300]
                        last = attempt >= args.retries
                        print(f"{label} {'FAILED' if last else 'retrying after'}  {message}", flush=True)
                        record = {"key": key, "name": model["fileName"], "error": message,
                                  "console": errors[:3]}
                        # A reload is the cheapest way back to a known-good page
                        # after a timeout, a mid-capture HMR reload or a dead tile.
                        try:
                            viewer.open(args.url)
                        except (PlaywrightError, TimeoutError) as reopen_err:
                            print(f"    could not reopen the page: {reopen_err}", flush=True)
                            failed.append(record)
                            outcome = "dead"
                            break
                        if last:
                            failed.append(record)
                            outcome = "failed"
                if outcome == "dead":
                    print("    stopping: the page could not be recovered", flush=True)
                    break
                if outcome != "ok":
                    continue

                # Bookkeeping is guarded too: this model's output is already on
                # disk, so a crash here must not cost the run or the report.
                viewer.model_deadline = None
                try:
                    if not viewer.unload():
                        print("    unload did not clear the tile; reloading the page", flush=True)
                        viewer.open(args.url)
                    elif args.reload_every and index % args.reload_every == 0:
                        print(f"    reloading the page after {index} models "
                              f"(JS heap {viewer.heap_mb()} MB)", flush=True)
                        viewer.open(args.url)
                except (PlaywrightError, TimeoutError, RuntimeError) as err:
                    print(f"    recovering the page after {type(err).__name__}: "
                          f"{str(err).splitlines()[0][:160]}", flush=True)
                    try:
                        viewer.open(args.url)
                    except (PlaywrightError, TimeoutError) as reopen_err:
                        print(f"    could not reopen the page: {reopen_err}", flush=True)
                        print("    stopping: the page could not be recovered", flush=True)
                        break
        except KeyboardInterrupt:
            print("\ninterrupted - finished models keep their output, the rest re-run", flush=True)
        finally:
            browser.close()

    elapsed = time.time() - started
    per_model = elapsed / max(len(done), 1)
    print(f"\n{len(done)}/{len(todo)} rendered in {elapsed / 60:.1f} min ({per_model:.1f}s each), "
          f"{len(failed)} failed, {len(warned)} warning(s)")
    for failure in failed:
        print(f"  FAILED {failure['key']} ({failure['name']}): {failure['error']}")

    if args.json:
        report = {
            "corpus": corpus,
            "app_url": args.url,
            "out": str(out_dir),
            "views": view_names,
            "spec": args.spec,
            "intents": bool(args.intents),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "seconds": round(elapsed, 1),
            "selected": len(models),
            "skipped": len(skipped),
            "rendered": done,
            "warnings": warned,
            "failed": failed,
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"  report: {report_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
