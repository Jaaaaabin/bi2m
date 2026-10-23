"""Model library (2026-09-23): the database button in the sidebar's second
group opens a flyout listing the IFC library the dev server exposes through
/api/library-models (content-keyed, read from the corpus vis index), with a
search box; picking an entry loads that model exactly like an example model.
Read-only: the button never uploads, tiles or runs recognition.

Skips its list/load checks (still exits 0) when the server has no library
index, so the suite stays green on a machine without a library corpus.
"""
import os, re, sys, time, json, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, CHROMIUM_ARGS

API = BASE_URL.rstrip("/")  # BASE_URL ends with "/", and "//api/..." would miss the middleware
from playwright.sync_api import sync_playwright

V = "#viewerContainer1"
LIB_MODEL = os.environ.get("BI2M_E2E_LIBRARY_MODEL", "0001.ifc")  # renumbered after every screening pass (last: 2026-09-23, 0001-0370) - override when it moves; falls back to the first entry
res = []
def check(n, ok, d=""):
    res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

def get(url):
    # Headers come back as a case-insensitive mapping (Node may send them lower-case).
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()

status, hdrs, body = get(f"{API}/api/library-models")
if "json" not in (hdrs.get("Content-Type") or ""):
    # The SPA fallback answered: this dev server predates the route (restart `npm run dev`).
    print("  [SKIP] /api/library-models is not served by this dev server (restart needed?) - route/list/load checks skipped")
    print(f"\n{sum(res)}/{len(res)} checks passed"); sys.exit(0)
if status == 404:
    print("  [SKIP] library index not present on this server - list/load checks skipped")
    print(f"\n{sum(res)}/{len(res)} checks passed"); sys.exit(0)
payload = json.loads(body)
check("route lists the library", status == 200 and payload.get("ok") and len(payload.get("files", [])) > 0, f"{len(payload.get('files', []))} models from {payload.get('corpus')}")
check("every entry is content-keyed (16 hex) with a name and a size",
      all(re.fullmatch(r"[0-9a-f]{16}", f["fileKey"]) and f["fileName"].endswith(".ifc") and f["sizeBytes"] > 0 for f in payload["files"]))
target = next((f for f in payload["files"] if f["fileName"] == LIB_MODEL), payload["files"][0])
status, headers, data = get(f"{API}/api/library-models?fileKey={target['fileKey']}")
check("route streams a model by content key and confirms the key it served",
      status == 200 and len(data) == target["sizeBytes"] and headers.get("X-Content-Key") == target["fileKey"],
      f"{target['fileName']} {len(data)} bytes, X-Content-Key {headers.get('X-Content-Key')}")
check("route refuses a malformed key", get(f"{API}/api/library-models?fileKey=../../etc/passwd")[0] == 400)
check("route refuses a key that is not in the index", get(f"{API}/api/library-models?fileKey=0000000000000000")[0] == 404)

with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(BASE_URL, wait_until="networkidle")

    # Three GROUPS down the one column since 2026-09-24 (they were rows while
    # the sidebar still had a wide mode): the display/upload cluster, the two
    # server-model buttons, then viewer management at the foot of the panel.
    grp = lambda i: [el.get_attribute("id") for el in pg.locator(".sidebar-buttons-group").nth(i).locator("button").all()]
    check("Examples then Library form the second group, Library on a database glyph (2026-09-24)",
          pg.locator(".sidebar-buttons-group").count() == 4 and grp(1) == ["example-models-btn", "library-models-btn"]
          and pg.locator("#library-models-btn use[href='#icon-database']").count() == 1, str(grp(1)))
    check("Theme heads the first group, Auto-open closes the upper part, viewer controls the last",
          grp(0) == ["theme-toggle-btn", "bulk-upload-btn"] and grp(2) == ["panels-default-btn"]
          and grp(3) == ["add-viewer-btn", "remove-viewer-btn", "sync-cam-btn", "match-sizes-btn"],
          f"{grp(0)} {grp(2)} {grp(3)}")
    check("flyout hidden until clicked", pg.locator("#library-models-flyout").is_hidden())

    pg.click("#library-models-btn")
    pg.wait_for_selector("#library-models-flyout .library-models-item", timeout=20000)
    items = pg.locator("#library-models-flyout .library-models-item")
    check("flyout lists the whole library", items.count() >= len(payload["files"]), f"{items.count()} items")
    check("flyout header names the corpus and the count",
          payload["corpus"] in pg.inner_text("#library-models-flyout .library-models-hint")
          and str(len(payload["files"])) in pg.inner_text("#library-models-flyout .library-models-hint"))
    if payload.get("summary"):
        # Annotations present (scripts/library_annotations.py). A cluster renders
        # only when it has files and a lone cluster is not folded: since 2026-09-23
        # the corpus is metre-only with no residual model, so the list is flat today.
        summ = payload["summary"]
        nonmetre_expected = sum(v for u, v in summ["units"].items() if u != "m")
        metre_expected = summ["units"].get("m", 0)
        clusters = pg.locator("#library-models-flyout .library-models-cluster")
        names = [c.get_attribute("data-cluster") for c in clusters.all()]
        hint = pg.inner_text("#library-models-flyout .library-models-hint")
        if summ["residual"] == 0 and nonmetre_expected == 0:
            check("no clusters when every model is metre and none is residual", names == [], str(names))
            check("the flat list holds every model exactly once", items.count() == len(payload["files"]), f"{items.count()} items")
            check("no residual badge on the flat list", pg.locator("#library-models-flyout .library-models-badge.is-residual").count() == 0)
            check("hint carries no annotation date when nothing is clustered", "annotation" not in hint.lower(), hint)
        else:
            def cluster_items(name):
                return pg.locator(f'#library-models-flyout .library-models-cluster[data-cluster="{name}"] .library-models-item')
            expected = [n for n, k in (("residual", summ["residual"]), ("nonmetre", nonmetre_expected), ("metre", metre_expected)) if k]
            check("only clusters with files are rendered, in the designed order", names == expected, f"{names} vs {expected}")
            check("residual cluster holds exactly the annotated residual models", cluster_items("residual").count() == summ["residual"], f"{cluster_items('residual').count()} vs {summ['residual']}")
            check("non-metre cluster holds every mm/cm/ft model", cluster_items("nonmetre").count() == nonmetre_expected, f"{cluster_items('nonmetre').count()} vs {nonmetre_expected}")
            check("metre cluster holds the rest", cluster_items("metre").count() == metre_expected)
            check("every residual entry carries its verdict badge",
                  cluster_items("residual").count() == pg.locator('#library-models-flyout .library-models-cluster[data-cluster="residual"] .library-models-badge.is-residual').count())
            is_open = lambda name: pg.locator(f'#library-models-flyout .library-models-cluster[data-cluster="{name}"]').evaluate("el => el.open")
            check("residual and non-metre clusters open, metre (the rest) folded",
                  all(is_open(n) == (n != "metre") for n in names), str({n: is_open(n) for n in names}))
            check("hint names the annotation date when clusters show", "annotations" in hint.lower(), hint)
            items = pg.locator("#library-models-flyout .library-models-item")  # now includes duplicates across clusters
            check("flyout lists the whole library across clusters", cluster_items("nonmetre").count() + cluster_items("metre").count() == len(payload["files"]))
    pg.fill("#library-models-flyout .library-models-search", target["fileName"][:4])
    pg.wait_for_timeout(300)
    visible = {el.get_attribute("data-file-key") for el in items.all() if el.is_visible()}
    check("search narrows the list by number", 1 <= len(visible) <= 3 and target["fileKey"] in visible, f"{len(visible)} visible")
    pg.fill("#library-models-flyout .library-models-search", target["fileKey"][:6]); pg.wait_for_timeout(300)
    visible = {el.get_attribute("data-file-key") for el in items.all() if el.is_visible()}
    check("search also matches the content key", visible == {target["fileKey"]})

    # ---- outside-click dismissal (2026-09-23, page/popover.js): a popover closes
    # when the pointer goes down anywhere outside it and its own button, and on
    # Escape; opening the other sidebar popover therefore closes this one. ----
    pg.click("#library-models-flyout .library-models-search")
    check("a click inside the flyout keeps it open", pg.locator("#library-models-flyout").is_visible())
    # The page's own <h1>, not the sidebar heading - that heading went with the
    # collapse toggle on 2026-09-24. Any inert element outside the flyout and
    # its button does; this one is stable and carries no handler.
    pg.click(".app-main h1")
    check("a click outside the flyout closes it", pg.locator("#library-models-flyout").is_hidden())
    pg.click("#library-models-btn"); pg.wait_for_selector("#library-models-flyout .library-models-item", timeout=20000)
    pg.keyboard.press("Escape")
    check("Escape closes the flyout", pg.locator("#library-models-flyout").is_hidden())
    pg.click("#example-models-btn"); pg.wait_for_selector("#example-models-flyout:not([hidden])", timeout=20000)
    pg.click(".app-main h1")
    check("the example-models flyout closes on an outside click too", pg.locator("#example-models-flyout").is_hidden())
    pg.click("#example-models-btn"); pg.wait_for_selector("#example-models-flyout:not([hidden])", timeout=20000)
    pg.click("#library-models-btn"); pg.wait_for_selector("#library-models-flyout .library-models-item", timeout=20000)
    check("opening the library closes the example-models flyout",
          pg.locator("#example-models-flyout").is_hidden() and pg.locator("#library-models-flyout").is_visible())
    pg.click("#library-models-btn")
    check("the library button still toggles its own flyout closed", pg.locator("#library-models-flyout").is_hidden())
    pg.click("#library-models-btn"); pg.wait_for_selector("#library-models-flyout .library-models-item", timeout=20000)

    errs.clear()
    # ---- transfer progress (2026-09-24) ----
    # The clicked row counts real bytes while the model downloads. Throttled
    # on purpose: over localhost a 2 MB model arrives in one chunk and the
    # readout would jump straight to 100%, which proves nothing. This is the
    # only phase of a load where a progress readout can honestly move - the
    # parse that follows blocks the main thread hard enough to freeze the CSS
    # spinner (page/fetchFile.js).
    cdp = pg.context.new_cdp_session(pg)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {
        "offline": False, "latency": 20,
        "downloadThroughput": 400 * 1024, "uploadThroughput": 400 * 1024,
    })
    row = pg.locator(f'#library-models-flyout .library-models-item[data-file-key="{target["fileKey"]}"]').first
    name_el = row.locator(".library-models-item-name")
    row.click()
    seen, deadline = [], time.time() + 30
    while time.time() < deadline:
        try:
            txt = name_el.inner_text(timeout=400)
        except Exception:
            break                      # flyout gone: the transfer finished
        if not seen or seen[-1] != txt:
            seen.append(txt)
        if "100%" in txt:
            break
        time.sleep(0.2)
    steps = [t for t in seen if re.match(r"^[\d.]+ [KM]B / [\d.]+ [KM]B · \d+%$", t)]
    check("the clicked row counts real bytes while the model downloads",
          len(steps) >= 3, f"{len(steps)} readouts, e.g. {steps[:3]}")
    cdp.send("Network.emulateNetworkConditions", {
        "offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1,
    })
    pg.wait_for_selector(f"{V}.has-model", timeout=240000)
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    check("flyout closed after picking a model", pg.locator("#library-models-flyout").is_hidden())
    check("the model loaded into the empty tile under its library name",
          pg.locator(f"{V}.has-model").count() == 1 and target["fileName"] in pg.inner_text(f"{V} .ifc-name-label"),
          pg.inner_text(f"{V} .ifc-name-label"))
    # A shard keyed by this model's content key may or may not exist; the panel
    # must render either way (rows, or the placeholder/Run affordance).
    check("intent panel rendered for the library model",
          pg.locator(f"{V} .intent-row").count() > 0 or pg.locator(f"{V} .intent-progress-text, {V} .intent-compute-flyout, {V} [class*='intent-']").count() > 0,
          f"{pg.locator(f'{V} .intent-row').count()} rows")
    known = lambda e: "shader" in e.lower() or "GL_INVALID" in e or "removeEntry" in e
    check("no console or page errors while loading from the library", not [e for e in errs if not known(e)], "; ".join(errs[:2]))

    print(f"\n{sum(res)}/{len(res)} checks passed"); b.close()
sys.exit(0 if all(res) else 1)
