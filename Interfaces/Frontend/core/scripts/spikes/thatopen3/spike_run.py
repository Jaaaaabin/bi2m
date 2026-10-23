import json, sys, time
from playwright.sync_api import sync_playwright
model = sys.argv[1] if len(sys.argv) > 1 else "test_1"
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]); pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.add_init_script("window.__lt=[]; try{new PerformanceObserver(l=>{for(const e of l.getEntries()) window.__lt.push(Math.round(e.duration));}).observe({type:'longtask',buffered:true});}catch(e){}")
    msgs = []; pg.on("console", lambda m: msgs.append(f"[{m.type}] {m.text[:200]}") if m.type in ("error", "warning") else None); pg.on("pageerror", lambda e: msgs.append(f"[pageerror] {str(e)[:200]}"))
    pg.goto(f"http://localhost:3100/spike.html?model={model}", wait_until="networkidle")
    t0 = time.time()
    while time.time() - t0 < 240:
        if pg.evaluate("() => window.__spike && window.__spike.done"): break
        pg.wait_for_timeout(500)
    out = pg.evaluate("() => window.__spike"); lt = pg.evaluate("() => window.__lt"); print("longtasks:", {"count": len(lt), "total_ms": sum(lt), "max_ms": max(lt, default=0)})
    pg.screenshot(path=f"spike3/spike_{model}.png")
    print(json.dumps({k: v for k, v in out.items() if k != "steps"}, indent=1))
    print("--- steps ---"); [print(f"  {s['t']:>6}ms {s['msg']} {json.dumps({k:v for k,v in s.items() if k not in ('t','msg')})}") for s in out["steps"]]
    print("--- console ---"); print("\n".join(msgs[:12]))
    b.close()
