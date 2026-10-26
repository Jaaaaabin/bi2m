"""Shared knobs for the Playwright harnesses in this directory.

BASE_URL  the running viewer (default http://localhost:3000/; override with
          BI2M_E2E_URL, e.g. for `vite preview` on another port).
OUT       where screenshots and JSON reports land (default ./out, gitignored;
          override with BI2M_E2E_OUT).
The dev server is NOT started here on purpose - the harnesses read the app
the user is looking at, HMR edits included.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_URL = os.environ.get("BI2M_E2E_URL", "http://localhost:3000/")
OUT = os.environ.get("BI2M_E2E_OUT", os.path.join(HERE, "out"))
os.makedirs(OUT, exist_ok=True)

# Headless Chromium here renders through SwiftShader (software GL). CPU-side
# numbers (long tasks, DOM, JS) are valid; frame times are not evidence.
CHROMIUM_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]

# The fixture that streams from a pre-converted tile set instead of parsing a
# raw IFC. It was EMPTY from 2026-09-21, when test_7.ifc left the corpus and
# took public/tiles/935f3af683fd0c3c/ with it, until 2026-09-24 - when the
# streamed path turned out to have had a fixture the whole time:
# public/tiles/654d77285c2cbe1b/ is test_4.ifc, converted by an earlier run of
# scripts/tileIfc.mjs and never named here. Verified that day: this harness
# and unload_model.py both pass against it (308 intent rows, 0 console
# errors), and the streamed load is the fast one - 0.6 s to a reviewable
# panel against 13.1 s for the un-tiled test_5.ifc of comparable size.
#
# public/tiles/ is a gitignored build artifact, so a clone that has not run
# the converter has no tile sets at all and the skip path still matters. The
# env var overrides, and any model can take its place:
# **Empty again since 2026-09-24**, when the owner reduced `data/` to a single
# `example_autcon.ifc` and `test_4.ifc` left with the rest. Its tile set is
# still on disk (public/tiles/654d77285c2cbe1b/), but these harnesses load a
# fixture through the example flyout by FILE NAME, and there is no longer a
# file to pick - so the streamed sections skip once more. Two ways back:
# restore `data/test_4.ifc`, or tile the surviving fixture and name it here.
# The second still changes what every other harness measures: a tiled model
# streams, and the reference values (refer_zoom.py, views.py) were taken on
# the parsed path - Refer itself works on a streamed model since 2026-10-21
# (streamed_refer.py covers it on an upload the server serves tiled, without
# touching this fixture).
#     node scripts/tileIfc.mjs data/<model>.ifc
#     BI2M_E2E_STREAMED=<model>.ifc python3 scripts/e2e/run_all.py
STREAMED_MODEL = os.environ.get("BI2M_E2E_STREAMED", "")


def skip_streamed(what):
    """Prints one SKIP line and returns True when there is no tiled fixture.
    Deliberately not a check(): run_all counts [FAIL] lines and the N/M ratio,
    so a skip stays visible to a human without silently passing as a check."""
    if STREAMED_MODEL:
        return False
    print(f"  [SKIP] {what} - no tiled fixture (see STREAMED_MODEL in _common.py)")
    return True
