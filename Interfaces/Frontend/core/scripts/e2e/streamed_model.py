import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT, STREAMED_MODEL, skip_streamed
from playwright.sync_api import sync_playwright
V="#viewerContainer1"
if skip_streamed("streamed-model smoke"):
    sys.exit(0)
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader"]); pg=b.new_page(viewport={"width":1400,"height":900})
    errs=[]; pg.on("pageerror",lambda e:errs.append(str(e))); pg.on("console",lambda m: m.type=="error" and errs.append(m.text))
    pg.goto(BASE_URL,wait_until="networkidle")
    pg.wait_for_selector(f"{V} .viewer-empty-examples .viewer-empty-example-item", timeout=15000)
    pg.click(f'{V} .viewer-empty-examples .viewer-empty-example-item[data-file-name="{STREAMED_MODEL}"]')
    pg.wait_for_selector(f"{V} .intent-row",timeout=180000,state="attached"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    print("rows", pg.locator(f"{V} .intent-row").count())
    print("progress:", pg.locator(f"{V} .intent-progress-text").inner_text())
    pg.locator(f"{V} .viewer-intent-panel-inner").click(position={"x":5,"y":5}); pg.keyboard.press("]"); pg.wait_for_timeout(200)
    print("] on streamed model -> current row:", pg.locator(f"{V} .intent-row.is-current").get_attribute("data-intent-id"))
    shader=[e for e in errs if "Shader" in e]; other=[e for e in errs if "Shader" not in e]
    print("errors: shader(known F12)=%d other=%d" % (len(shader), len(other)), other[:2])
    b.close()
