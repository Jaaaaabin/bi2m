// ======== Inspector Panel Bootstrap (lazy-loads React) ========
// InspectorPanel.jsx (React + ReactDOM + the panel itself) previously loaded
// eagerly via a static <script> tag in index.html, even though it renders
// nothing until the user actually clicks an element.
//
// This tiny, dependency-free stub is what loads eagerly instead: it listens
// for the FIRST "element-selected" CustomEvent (dispatched by
// ThatOpenCompanyLoader.js on click-to-inspect), dynamically imports the real
// panel module only then, and removes itself. CustomEvents aren't queued -
// by the time the dynamic import resolves, the event that triggered it is
// already gone. Re-dispatching a second "element-selected" event doesn't fix
// this either: InspectorPanel.jsx's own listener is registered inside a
// useEffect, which React only runs asynchronously after its first paint -
// well after the dynamic import's promise resolves and this module's
// re-dispatch would fire, so the replayed event is lost to the same race.
// Instead, the pending detail is stashed here where InspectorPanel.jsx reads
// it synchronously as its initial React state (a useState initializer runs
// during the first render itself, not after), sidestepping the effect-timing
// race entirely rather than trying to win it.
let loaded = false;

async function onFirstSelection(event) {
  if (loaded) return;
  loaded = true;
  window.removeEventListener("element-selected", onFirstSelection);

  window.__pendingElementSelection = event.detail;
  await import("./InspectorPanel.jsx");
}

window.addEventListener("element-selected", onFirstSelection);
