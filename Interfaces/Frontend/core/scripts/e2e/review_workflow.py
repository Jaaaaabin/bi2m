"""Review-workflow verification on test_1. Verdicts written during the
run are cleared at the end (never persist test state)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT
from playwright.sync_api import sync_playwright
V="#viewerContainer1"; res=[]
def check(n,ok,d=""): res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}"+(f" - {d}" if d else ""))
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader"]); pg=b.new_page(viewport={"width":1600,"height":900}, device_scale_factor=2)
    errs=[]; pg.on("pageerror",lambda e:errs.append(str(e))); pg.on("console",lambda m: m.type=="error" and errs.append(m.text))
    pg.goto(BASE_URL,wait_until="networkidle")
    # --- 2.7 empty state lists example models and loads into THIS tile ---
    pg.wait_for_selector(f"{V} .viewer-empty-examples .viewer-empty-example-item", timeout=15000)
    n_ex=pg.locator(f"{V} .viewer-empty-examples .viewer-empty-example-item").count()
    check("empty tile lists the server's example models", n_ex>=1, f"{n_ex} items")
    pg.click(f'{V} .viewer-empty-examples .viewer-empty-example-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row",timeout=180000,state="attached"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    check("clicking it loads the model into that tile", pg.locator(f"{V} .ifc-name-label").inner_text().strip()=="example_autcon.ifc" and pg.locator(".viewer-container").count()==1)
    key=pg.evaluate("""async () => { const url = performance.getEntriesByType('resource').map(r=>r.name).find(n=>/viewerModel\\.js/.test(n)); const m=await import(url);
      const reg=await import(performance.getEntriesByType('resource').map(r=>r.name).find(n=>/viewerRegistry\\.js/.test(n))); const e=reg.viewerData[0]; const model=e.fragments.groups.values().next().value; return m.getModelKey(model); }""")
    print("   fileKey", key)
    before=pg.evaluate(f"() => localStorage.getItem('bi2m:verdicts:{key}')")
    try:
        rows=pg.locator(f"{V} .intent-row").count()
        # --- 2.1 ledgers + progress ---
        check("every category and domain header carries a ledger", pg.locator(f"{V} .intent-category-header .intent-ledger").count()==pg.locator(f"{V} .intent-category-header").count() and pg.locator(f"{V} .intent-domain-header .intent-ledger").count()==pg.locator(f"{V} .intent-domain-header").count())
        prog=pg.locator(f"{V} .intent-progress-text").inner_text().strip()
        check("panel shows review progress", prog.endswith(f"of {rows} reviewed"), prog)
        # --- corroboration chip + pre-flight line (2026-09-21) ---
        n_corr=pg.locator(f"{V} .intent-corroborates").count()
        check("some rows carry a corroboration chip with a tooltip naming the other detector", n_corr>0 and "Also found independently by" in (pg.locator(f"{V} .intent-corroborates").first.get_attribute("title") or ""), f"{n_corr} chips")
        pf=pg.locator(f"{V} .intent-preflight:not(.intent-preflight-unlikely)")
        check("pre-flight is one folded line with a count", pf.count()==1 and not pf.evaluate("el => el.hidden") and not pf.evaluate("el => el.open") and "not applicable to this model" in pf.locator("summary").inner_text(), pf.locator("summary").inner_text() if pf.count() else "-")
        pf.locator("summary").click(); pg.wait_for_timeout(150)
        check("...and expands on click to the per-reason list", pf.evaluate("el => el.open") and pf.locator(".intent-preflight-body").is_visible() and "no " in pf.locator(".intent-preflight-body").inner_text())
        pf.locator("summary").click(); pg.wait_for_timeout(100)
        # --- 2.5 type floor ---
        small=pg.evaluate(f"""() => [...document.querySelectorAll('{V} .viewer-intent-panel *, #sidebar-panel *, {V} .viewer-camera-panel *, #status-strip *')].filter(el => el.textContent.trim() && !el.children.length && parseFloat(getComputedStyle(el).fontSize) < 11).map(el => el.className+':'+getComputedStyle(el).fontSize)""")
        check("no interface text below 11px", not small, "; ".join(sorted(set(small))[:5]))
        pw=pg.locator(f"{V} .viewer-intent-panel").bounding_box()["width"]
        check("intent panel width within clamp(260, 25%, 380)", 259<=pw<=381, f"{pw:.0f}px")
        # --- 2.2 keyboard ---
        sec=pg.locator(f"{V} .intent-category-section").first; sec.locator(".intent-category-header").click(); pg.wait_for_timeout(300)
        pg.locator(f"{V} .viewer-intent-panel-inner").click(position={"x":5,"y":5}); pg.keyboard.press("ArrowDown"); pg.wait_for_timeout(150)
        first=sec.locator(".intent-row").first
        check("ArrowDown makes the first visible row current + focused", first.evaluate("el => el.classList.contains('is-current') && document.activeElement===el"))
        pg.keyboard.press("ArrowDown"); pg.wait_for_timeout(100)
        second=sec.locator(".intent-row").nth(1)
        check("ArrowDown again moves to the second row", second.evaluate("el => el.classList.contains('is-current')") and not first.evaluate("el => el.classList.contains('is-current')"))
        pg.keyboard.press("ArrowUp"); pg.wait_for_timeout(100)
        check("ArrowUp moves back", first.evaluate("el => el.classList.contains('is-current')"))
        pg.keyboard.press("a"); pg.wait_for_timeout(150)
        check("a accepts the current row (same handler as the button)", first.get_attribute("data-verdict")=="accepted" and first.locator(".intent-accept-btn").evaluate("el => el.classList.contains('is-active')"))
        hdr=sec.locator(".intent-category-header"); acc_w=hdr.locator(".intent-ledger-accepted").evaluate("el => el.style.width")
        cat_n=sec.locator(".intent-row").count()
        check("category ledger advanced by one row", abs(float(acc_w.rstrip('%'))-100/cat_n)<0.01, f"{acc_w} of {cat_n} rows")
        check("progress text updated", pg.locator(f"{V} .intent-progress-text").inner_text().strip().startswith("1 of"), pg.locator(f"{V} .intent-progress-text").inner_text())
        # Reset fades in over --transition-fast (0.2s); sampling at a fixed 150ms sat on the
        # ease curve's shoulder and failed under load (2026-09-23). Wait for the end state.
        try:
            first.locator(".intent-reset-btn").evaluate("el => new Promise(done => { const t=setInterval(() => { if (parseFloat(getComputedStyle(el).opacity) > 0.9) { clearInterval(t); done(true); } }, 25); setTimeout(() => { clearInterval(t); done(false); }, 2000); })")
        except Exception:
            pass
        check("Reset became prominent on the verdicted row", first.locator(".intent-reset-btn").evaluate("el => parseFloat(getComputedStyle(el).opacity)")>0.9)
        pg.keyboard.press("r"); pg.wait_for_timeout(150)
        check("r rejects", first.get_attribute("data-verdict")=="rejected" and first.evaluate("el => el.classList.contains('verdict-rejected')") and float(hdr.locator(".intent-ledger-rejected").evaluate("el => el.style.width").rstrip('%'))>0)
        # --- 2.3 filter ---
        pg.keyboard.press("/"); check("/ focuses the filter", pg.evaluate("() => document.activeElement.classList.contains('intent-filter-input')"))
        pg.keyboard.type("zzzz-no-match"); pg.wait_for_timeout(200)
        hidden=pg.locator(f"{V} .intent-row[hidden]").count()
        check("text filter hides non-matching rows, DOM complete", hidden==rows and pg.locator(f"{V} .intent-row").count()==rows, f"{hidden} hidden of {rows}")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        check("Esc in the filter clears it", pg.locator(f"{V} .intent-row[hidden]").count()==0)
        pg.keyboard.press("Escape")  # blur
        pg.click(f'{V} .intent-chip[data-chip="rejected"]'); pg.wait_for_timeout(200)
        shown=pg.locator(f"{V} .intent-row:not([hidden])").count()
        check("Rejected chip shows only the rejected row", shown==1 and pg.locator(f'{V} .intent-chip[data-chip="rejected"]').get_attribute("aria-pressed")=="true", f"{shown} shown")
        check("category counts read shown / total while filtering", hdr.locator(".intent-category-count").inner_text().strip()==f"1 / {cat_n}", hdr.locator(".intent-category-count").inner_text())
        pg.click(f'{V} .intent-chip[data-chip="rejected"]'); pg.wait_for_timeout(200)
        # --- pending-chip review rhythm: judge, and the keyboard lands on the next row ---
        pg.click(f'{V} .intent-chip[data-chip="pending"]'); pg.wait_for_timeout(150)
        third=sec.locator(".intent-row").nth(2)
        second.click(position={"x":4,"y":4}); pg.wait_for_timeout(100); pg.keyboard.press("a"); pg.wait_for_timeout(200)
        check("Pending chip on: accepting the current row hides it and hands focus to the next", second.evaluate("el => el.hidden") and third.evaluate("el => el.classList.contains('is-current') && document.activeElement===el"))
        pg.keyboard.press("ArrowDown"); pg.wait_for_timeout(100)
        check("...and ArrowDown continues from there, not from the top", sec.locator(".intent-row").nth(3).evaluate("el => el.classList.contains('is-current')"))
        pg.keyboard.press("ArrowUp"); pg.keyboard.press("ArrowUp"); pg.wait_for_timeout(100)  # back onto first (pending)
        pg.click(f'{V} .intent-chip[data-chip="pending"]'); pg.wait_for_timeout(150)
        second.click(position={"x":4,"y":4}); pg.keyboard.press("u"); pg.wait_for_timeout(150)
        # ledger legibility at 2x: two accepted + two rejected in one category
        third.click(position={"x":4,"y":4}); pg.keyboard.press("a"); pg.wait_for_timeout(100)
        sec.locator(".intent-row").nth(3).click(position={"x":4,"y":4}); pg.keyboard.press("r"); pg.wait_for_timeout(200)
        hdr.scroll_into_view_if_needed(); hdr.screenshot(path=f"{OUT}/ledger_header.png", scale="device")
        pg.locator(f"{V} .intent-progress").screenshot(path=f"{OUT}/ledger_progress.png", scale="device")
        for r in [third, sec.locator(".intent-row").nth(3)]:
            r.click(position={"x":4,"y":4}); pg.keyboard.press("u"); pg.wait_for_timeout(100)
        # reset via keyboard
        first.click(position={"x":4,"y":4}); pg.keyboard.press("u"); pg.wait_for_timeout(150)
        check("u resets (verdict removed from storage)", first.get_attribute("data-verdict")=="pending" and pg.evaluate(f"() => {{ const v=JSON.parse(localStorage.getItem('bi2m:verdicts:{key}')||'{{}}'); return Object.keys(v).length; }}")==0)
        # --- ] moves category ---
        pg.keyboard.press("]"); pg.wait_for_timeout(200)
        sec2=pg.locator(f"{V} .intent-category-section").nth(1)
        check("] opens the next category and lands on its first row", sec2.evaluate("el => el.open") and sec2.locator(".intent-row").first.evaluate("el => el.classList.contains('is-current')"))
        # --- 2.4 density: evidence clamp ---
        clamp=first.locator(".intent-evidence").evaluate("el => getComputedStyle(el).webkitLineClamp")
        check("evidence clamped to two lines", clamp=="2", clamp)
        long_row=pg.locator(f"{V} .intent-row.has-more").first
        if long_row.count():
            long_row.locator(".intent-evidence").click(); pg.wait_for_timeout(100)
            check("clicking overflowing evidence expands it", long_row.evaluate("el => el.classList.contains('is-expanded') && getComputedStyle(el.querySelector('.intent-evidence')).webkitLineClamp==='none'"))
        else:
            check("has-more affordance present on some row", False, "no .has-more rows (evidence may all fit)")
        # --- 2.8 pulse on refer via Enter ---
        first.click(position={"x":4,"y":4})
        # the pulse lasts 450ms and a software-GL frame can take longer - record its appearance instead of sampling it
        first.locator(".intent-status-icon").evaluate("el => { el.dataset.pulsed=''; new MutationObserver(() => { if (el.classList.contains('is-pulsing')) el.dataset.pulsed='1'; }).observe(el, {attributes: true, attributeFilter: ['class']}); }")
        pg.keyboard.press("Enter")
        pg.wait_for_selector(f'{V} .intent-row[data-refer-status="done"]', timeout=60000); pg.wait_for_timeout(100)
        pulsed=first.locator(".intent-status-icon").evaluate("el => el.dataset.pulsed==='1'")
        check("Enter refers the current row; status ring pulsed once", first.locator(".intent-refer-btn").evaluate("el => el.classList.contains('is-active')") and bool(pulsed))
        pg.wait_for_timeout(700)
        check("pulse class removed after the animation", not first.locator(".intent-status-icon").evaluate("el => el.classList.contains('is-pulsing')"))
        check("Refer contract intact: data-refer-status=done, aria-busy cleared", first.get_attribute("data-refer-status")=="done" and first.locator(".intent-refer-btn").get_attribute("aria-busy") is None)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        check("Esc = Clear Selection (refer button released)", not first.locator(".intent-refer-btn").evaluate("el => el.classList.contains('is-active')"))
        pg.keyboard.press("?"); pg.wait_for_timeout(250)
        check("? opens the floating cheat sheet over the viewport", pg.locator(V).evaluate("el => el.classList.contains('shortcuts-open')") and pg.locator(f"{V} .viewer-shortcuts-panel").is_visible() and "j" not in pg.locator(f"{V} .viewer-shortcuts-panel dt").all_inner_texts()[0])
        pg.keyboard.press("?"); pg.wait_for_timeout(250)
        pg.click(f"{V} .viewer-shortcuts-toggle-btn"); pg.wait_for_timeout(250)
        check("its own corner button (next to the intent toggle) opens it too", pg.locator(f"{V} .viewer-shortcuts-panel").is_visible())
        pg.click(f"{V} .viewer-shortcuts-close"); pg.wait_for_timeout(250)
        check("the close button hides it", not pg.locator(f"{V} .viewer-shortcuts-panel").is_visible())
        pg.keyboard.press("j"); pg.wait_for_timeout(100)
        check("j is no longer a shortcut", first.evaluate("el => el.classList.contains('is-current')"))
        # sticky still fine
        # the biggest category: column stacks since 2026-10-07 (alignment's rows fold into claims)
        big=pg.locator(f"{V} .intent-category-section").filter(has=pg.locator('.intent-row[data-intent-id*="-colsupport-"]')).first
        big.evaluate("el => { el.open = true; }"); pg.wait_for_timeout(200); n=big.locator(".intent-row").count(); big.locator(".intent-row").nth(n-2).scroll_into_view_if_needed(); pg.wait_for_timeout(200)
        pb=pg.locator(f"{V} .viewer-intent-panel").bounding_box(); hb=big.locator(".intent-category-header").bounding_box()
        check("sticky headers still hold with the ledger", abs(hb["y"]-(pb["y"]+26))<=2, f"header y={hb['y']:.0f}, panel top {pb['y']:.0f}")
        pg.screenshot(path=f"{OUT}/tier2_light.png")
        pg.click("#theme-toggle-btn"); pg.wait_for_timeout(300); pg.screenshot(path=f"{OUT}/tier2_dark.png"); pg.click("#theme-toggle-btn")
        # second viewer: chip added and removed
        pg.click("#add-viewer-btn"); pg.wait_for_selector(".viewer-container:nth-child(2) .viewer-empty-examples", timeout=15000)
        check("new empty tile also lists examples", pg.locator(".viewer-container:nth-child(2) .viewer-empty-examples .viewer-empty-example-item").count()>=1)
        pg.click("#remove-viewer-btn"); pg.wait_for_timeout(300)
        check("no console or page errors", not errs, "; ".join(errs[:2]))
    finally:
        pg.evaluate(f"() => {{ const k='bi2m:verdicts:{key}'; {'localStorage.removeItem(k)' if before is None else f'localStorage.setItem(k, {before!r})'} }}")
        after=pg.evaluate(f"() => localStorage.getItem('bi2m:verdicts:{key}')")
        print("   verdict storage restored:", after==before)
    print(f"\n{sum(res)}/{len(res)} checks passed"); b.close()
