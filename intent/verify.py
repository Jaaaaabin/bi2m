"""Quote verification: is source.quote really on the page?"""

from __future__ import annotations

from difflib import SequenceMatcher

from .corpus import Page, norm


def verify_quote(quote: str, page: Page) -> tuple[str, str | None]:
    """Return (status, unit_id). status in {exact, fuzzy, failed}."""
    q = norm(quote)
    if not q:
        return "failed", None
    units = [(uid, norm(txt)) for uid, txt in page.all_text_units()]
    for uid, txt in units:
        if q in txt:
            return "exact", uid
    # fuzzy: best window match ratio on the closest unit
    best, best_uid = 0.0, None
    for uid, txt in units:
        if not txt:
            continue
        # slide a window of len(q) across txt in steps; cheap enough for page-sized text
        L = len(q)
        if len(txt) <= L:
            r = SequenceMatcher(None, q, txt).ratio()
            if r > best:
                best, best_uid = r, uid
            continue
        step = max(1, L // 4)
        for i in range(0, len(txt) - L + 1, step):
            r = SequenceMatcher(None, q, txt[i:i + L]).ratio()
            if r > best:
                best, best_uid = r, uid
            if best > 0.97:
                break
    if best >= 0.85:
        return "fuzzy", best_uid
    return "failed", None
