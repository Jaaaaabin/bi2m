import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT
from playwright.sync_api import sync_playwright
def size(pg, sel):
    return pg.evaluate(f"(() => {{ const r=document.querySelector('{sel}').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }})()")
def avail(pg):
    return pg.evaluate("""(() => { const w=document.getElementById('viewer-wrapper'); const cs=getComputedStyle(w);
      const px=parseFloat(cs.paddingLeft)+parseFloat(cs.paddingRight), py=parseFloat(cs.paddingTop)+parseFloat(cs.paddingBottom);
      return [w.clientWidth-px, window.innerHeight-w.getBoundingClientRect().top-py]; })()""")
res=[]
def check(n,ok,d=""): res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}"+(f" - {d}" if d else ""))
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader"]); pg=b.new_page(viewport={"width":1400,"height":900})
    errs=[]; pg.on("pageerror",lambda e:errs.append(str(e))); pg.on("console",lambda m: m.type=="error" and errs.append(m.text))
    pg.goto(BASE_URL,wait_until="networkidle"); pg.wait_for_timeout(800)
    w,h=size(pg,"#viewerContainer1"); aw,ah=avail(pg)
    check("single viewer ≈ 95% of available width", abs(w-0.95*aw)<=2, f"{w}px of {aw:.0f}px available = {w/aw*100:.1f}%")
    check("single viewer ≈ 95% of available height", abs(h-0.95*ah)<=2, f"{h}px of {ah:.0f}px available = {h/ah*100:.1f}%")
    pg.set_viewport_size({"width":1000,"height":700}); pg.wait_for_timeout(500)
    w2,h2=size(pg,"#viewerContainer1"); aw2,ah2=avail(pg)
    check("follows a window resize", abs(w2-0.95*aw2)<=2 and abs(h2-0.95*ah2)<=2, f"{w2}x{h2} for {aw2:.0f}x{ah2:.0f} available")
    # "follows the sidebar collapsing" lived here until 2026-09-24. The sidebar
    # has one fixed 44px width now, so there is no fold to follow; the window
    # resize above already exercises the same re-fit on a changed available
    # width, which was the point of the check.
    pg.click("#add-viewer-btn"); pg.wait_for_timeout(1500)
    w4,_=size(pg,"#viewerContainer1"); w5,_=size(pg,"#viewerContainer2")
    inline1 = pg.get_attribute("#viewerContainer1","style") or ""
    check("second viewer -> auto size cleared, CSS back in control", inline1.strip()=="" and pg.get_attribute("#viewerContainer1","data-auto-sized") is None and w4<w2, f"viewer1 inline style '{inline1}', {w2}px -> {w4}px (viewer2 {w5}px)")
    pg.click("#remove-viewer-btn"); pg.wait_for_timeout(800)
    w6,_=size(pg,"#viewerContainer1"); aw6,_=avail(pg)
    check("back to one viewer -> fills again", abs(w6-0.95*aw6)<=2, f"{w6}px of {aw6:.0f}px")
    # manual drag: shrink by 200px, then resize window - must NOT be overridden
    hb=pg.locator("#viewerContainer1 .viewer-resize-handle").bounding_box()
    pg.mouse.move(hb["x"]+hb["width"]/2, hb["y"]+hb["height"]/2); pg.mouse.down(); pg.mouse.move(hb["x"]-200, hb["y"]-100, steps=8); pg.mouse.up(); pg.wait_for_timeout(300)
    w7,h7=size(pg,"#viewerContainer1")
    pg.set_viewport_size({"width":1400,"height":900}); pg.wait_for_timeout(500)
    w8,h8=size(pg,"#viewerContainer1")
    check("a dragged tile is left alone afterwards", (w7,h7)==(w8,h8) and w7<w6 and pg.get_attribute("#viewerContainer1","data-user-sized")=="1", f"dragged to {w7}x{h7}, after window resize {w8}x{h8}")
    check("no console or page errors", not errs, "; ".join(errs[:2]))
    print(f"\n{sum(res)}/{len(res)} checks passed"); b.close()
