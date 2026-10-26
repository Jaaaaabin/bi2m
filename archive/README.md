# archive — legacy folders, not maintained

Moved here on 2026-10-20 during the reorganisation. Nothing in the live pipeline imports from these.

- `0_archi_rag_agent/` — the first Neufert RAG agent (`agent/`, Sep 2026), its tier-1 knowledge base (`tier1/`) and
  sample outputs (`outputs/`). `agent/export_dataset.py` is what produced `data/neufert/dataset/`; its path constants
  still expect `vlm_pages.sqlite` next to the package and `1_dataset/` under the project root, so fix those before
  re-running it.
- `3_cuatesting/` — an unrelated computer-use (desktop automation) test with its own `.venv` and screen recordings.
