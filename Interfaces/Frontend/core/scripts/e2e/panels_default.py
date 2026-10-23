import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT
from playwright.sync_api import sync_playwright
import re
V="#viewerContainer1"
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader"]); pg=b.new_page(viewport={"width":1400,"height":900})
    errs=[]; pg.on("pageerror",lambda e:errs.append(str(e))); pg.on("console",lambda m: m.type=="error" and errs.append(m.text))
    pg.goto(BASE_URL,wait_until="networkidle")
    btn=pg.locator("#panels-default-btn"); upper=pg.locator(".sidebar-buttons").first.locator("button")
    print(f"  button exists: {btn.count()==1} | last in the sidebar's upper part: {upper.nth(upper.count()-1).get_attribute('id')=='panels-default-btn'} | active by default: {'active' in (btn.get_attribute('class') or '')}")
    pg.click("#example-models-btn"); pg.wait_for_selector('.example-models-item[data-file-name="example_autcon.ifc"]',timeout=20000); pg.click('.example-models-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row",timeout=180000,state="attached"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2500)
    cls=pg.locator(V).get_attribute("class") or ""
    print(f"  after load: intent-open {'intent-open' in cls} camera-open {'camera-open' in cls} | distance {pg.input_value(f'{V} .viewer-camera-distance-value')} (ref 94.6 m)")
    idx=pg.evaluate("[...document.querySelectorAll(\"#viewerContainer1 .intent-index\")].map(e => e.textContent.trim())")
    print(f"  index spans: {len(idx)} rows, well-formed {sum(bool(re.fullmatch(r'[a-z_]+-\d{3}',t)) for t in idx)}, unique {len(set(idx))==len(idx)} e.g. {idx[:2]}")
    btn.click(); pg.wait_for_timeout(300); cls=pg.locator(V).get_attribute("class") or ""
    print(f"  toggle OFF closes both: {('intent-open' not in cls) and ('camera-open' not in cls)} | stored: {pg.evaluate('localStorage.getItem(\"bi2m:panelsOpenByDefault\")')}")
    btn.click(); pg.wait_for_timeout(300); cls=pg.locator(V).get_attribute("class") or ""
    print(f"  toggle ON reopens both: {('intent-open' in cls) and ('camera-open' in cls)} | errors: {errs or 'none'}")
    b.close()
