// React itself is not imported: @vitejs/plugin-react uses the automatic JSX runtime.
import { Component, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { createRoot } from "react-dom/client";

// ======== Element Inspector (React island) ========
// The only React code in the project. It never touches OBC/BUI: the loader
// (ThatOpenCompanyLoader.js) talks to it through three CustomEvents on
// `window`, and everything it shows arrives ready-made from
// inspector/describeElement.js:
//   "element-selected"          -> { detail: { container, fragmentID, expressID,
//                                   fileName, guid, name, ifcClass, attributes,
//                                   geometry } }
//   "element-deselected"        -> { detail: { container } } - that tile's 3D
//                                   selection was cleared
//   "element-deselect-request"  -> { detail: { container } } - dispatched BY
//                                   this panel when the user closes it, so that
//                                   tile's 3D highlight clears too
// `container` is the viewer tile the element was clicked in. React is mounted
// on #inspector-root (index.html), but the panel renders through a portal
// into that tile's .viewer-inspector-slot - a fixed place inside the tile's
// 3D viewport (style.css) - so it never covers another tile, and closing it
// touches only its own tile.

const slotOf = (container) => container?.querySelector(".viewer-inspector-slot") ?? null;

// The tile of the latest selection, for the error boundary below, which
// cannot read the selection out of the subtree that just failed.
let lastContainer = window.__pendingElementSelection?.container ?? null;
window.addEventListener("element-selected", (event) => {
  lastContainer = event.detail?.container ?? null;
});

function requestDeselect(container) {
  window.dispatchEvent(new CustomEvent("element-deselect-request", { detail: { container } }));
}

function formatKey(key) {
  return key.replace(/([a-z])([A-Z])/g, "$1 $2");
}

function InspectorCard({ selection, onClose }) {
  const { fileName, guid, name, ifcClass, attributes = [], geometry } = selection;
  return (
    <div className="inspector-panel">
      <div className="inspector-header">
        <strong className="inspector-title" title={guid ?? undefined}>
          {guid || "(no GUID)"}
        </strong>
        <button
          className="inspector-close"
          onClick={onClose}
          title="Close inspector"
          aria-label="Close inspector"
        >
          ×
        </button>
      </div>
      <div className="inspector-meta">
        {fileName && <div className="inspector-file">File: {fileName}</div>}
        <div className="inspector-class">Class: {ifcClass || "(unknown)"}</div>
        <div className="inspector-type">Name: {name || "(unnamed element)"}</div>
        <div className="inspector-repr" title={geometry?.detail || undefined}>
          Geometry: {geometry ? geometry.label : "(none)"}
        </div>
      </div>
      <div className="inspector-body">
        {attributes.length === 0 ? (
          <div className="inspector-empty">No further properties available.</div>
        ) : (
          attributes.map(([key, value]) => (
            <div className="inspector-row" key={key}>
              <span className="inspector-key">{formatKey(key)}</span>
              <span className="inspector-value">{String(value)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function ElementInspector() {
  // On first mount (lazy-loaded via bootstrap.js), pick up the selection that
  // triggered the load - see bootstrap.js for why this can't just be a
  // re-dispatched "element-selected" event.
  const [selection, setSelection] = useState(() => {
    const pending = window.__pendingElementSelection;
    window.__pendingElementSelection = null;
    return pending ?? null;
  });

  useEffect(() => {
    const onSelect = (event) => setSelection(event.detail);
    // A clear in one tile must not close a panel that shows another tile's
    // element (each tile has its own selection).
    const onClear = (event) => {
      const tile = event.detail?.container;
      setSelection((current) => (!tile || current?.container === tile ? null : current));
    };
    window.addEventListener("element-selected", onSelect);
    window.addEventListener("element-deselected", onClear);
    return () => {
      window.removeEventListener("element-selected", onSelect);
      window.removeEventListener("element-deselected", onClear);
    };
  }, []);

  const slot = slotOf(selection?.container);
  if (!selection || !slot?.isConnected) return null;

  const handleClose = () => {
    requestDeselect(selection.container);
    setSelection(null);
  };
  return createPortal(<InspectorCard selection={selection} onClose={handleClose} />, slot);
}

// ======== Error boundary (2026-10-01) ========
// One element whose properties made the panel throw used to unmount the whole
// island for the rest of the session (React unmounts the root on an uncaught
// render error). The boundary keeps the root alive, says what happened in the
// same tile slot, clears that tile's 3D highlight on dismiss, and resets itself
// on the next "element-selected" - stashing that event's detail the same way
// bootstrap.js does, so the remounted inspector shows it.
class InspectorErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null, container: null };
    this.onSelect = (event) => {
      if (!this.state.error) return;
      window.__pendingElementSelection = event.detail;
      this.setState({ error: null, container: null });
    };
    this.dismiss = () => {
      requestDeselect(this.state.container);
      this.setState({ error: null, container: null });
    };
  }

  static getDerivedStateFromError(error) {
    return { error, container: lastContainer };
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
    const slot = slotOf(this.state.container);
    if (!slot?.isConnected) return null;
    const reason = String(this.state.error?.message ?? this.state.error);
    return createPortal(
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
      </div>,
      slot,
    );
  }
}

const root = document.getElementById("inspector-root");
if (root) {
  createRoot(root).render(
    <InspectorErrorBoundary>
      <ElementInspector />
    </InspectorErrorBoundary>,
  );
} else {
  console.warn("⚠️ #inspector-root not found - element inspector not mounted.");
}
