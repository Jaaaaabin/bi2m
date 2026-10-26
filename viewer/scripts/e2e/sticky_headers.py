import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT
from playwright.sync_api import sync_playwright
V="#viewerContainer1"; res=[]
def check(n,ok,d=""): res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}"+(f" - {d}" if d else ""))
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader"]); pg=b.new_page(viewport={"width":1400,"height":900})
    errs=[]; pg.on("pageerror",lambda e:errs.append(str(e))); pg.on("console",lambda m: m.type=="error" and errs.append(m.text))
    pg.goto(BASE_URL,wait_until="networkidle"); pg.click("#example-models-btn")
    pg.wait_for_selector('.example-models-item[data-file-name="example_autcon.ifc"]',timeout=20000); pg.click('.example-models-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row",timeout=180000,state="attached"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    panel=pg.locator(f"{V} .viewer-intent-panel")
    # open the biggest category via its header: Vertical Placement Continuity (47 rows) since
    # 2026-10-07, when alignment's 45 rows folded into its 12 row claims
    sec=pg.locator(f'{V} .intent-category-section').filter(has=pg.locator('.intent-row[data-intent-id*="-colsupport-"]')).first
    hdr=sec.locator(".intent-category-header"); dom=sec.locator("xpath=ancestor::details[contains(@class,'intent-domain-section')]").locator(".intent-domain-header")
    hdr.click(); pg.wait_for_timeout(300)
    rows=sec.locator(".intent-row").count(); check("a large category opened", rows>=30, f"{rows} rows")
    # scroll the panel so the section's last rows are in view (header would normally be gone)
    sec.locator(".intent-row").nth(rows-3).scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    pr=panel.bounding_box(); hb=hdr.bounding_box(); db=dom.bounding_box(); last=sec.locator(".intent-row").nth(rows-3).bounding_box()
    check("deep in the list, the domain header is stuck at the panel top", abs(db["y"]-pr["y"])<=1, f"domain header y={db['y']:.0f}, panel top {pr['y']:.0f}")
    check("the category header is stuck right below it", abs(hb["y"]-(db["y"]+db["height"]))<=1 and hb["y"]<last["y"], f"category header y={hb['y']:.0f} (domain bottom {db['y']+db['height']:.0f}); rows visible below at y={last['y']:.0f}")
    check("category header height stays one line", hb["height"]<40 and db["height"]<=27, f"{hb['height']:.0f}px / domain {db['height']:.0f}px")
    scroll_before=panel.evaluate("el => el.scrollTop")
    hdr.click(); pg.wait_for_timeout(400)
    is_open=sec.evaluate("el => el.open"); hb2=hdr.bounding_box(); pr2=panel.bounding_box()
    check("clicking the stuck header folds the section", is_open is False)
    check("after folding, that header is still on screen", pr2["y"]-1<=hb2["y"]<=pr2["y"]+pr2["height"]-hb2["height"]+1, f"header y={hb2['y']:.0f} within panel [{pr2['y']:.0f}, {pr2['y']+pr2['height']:.0f}]; scrollTop {scroll_before:.0f} -> {panel.evaluate('el => el.scrollTop'):.0f}")
    hdr.click(); pg.wait_for_timeout(300); sec.locator(".intent-row").nth(rows-3).scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    pg.screenshot(path=f"{OUT}/sticky.png")
    check("no console or page errors", not errs, "; ".join(errs[:2]))
    print(f"\n{sum(res)}/{len(res)} checks passed"); b.close()
