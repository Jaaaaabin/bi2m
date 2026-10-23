"""Batch IFC extraction entry point.

Migrated from src/ifc_geometry_processing.py (a prior project's reference driver;
its imports no longer resolved and it was removed 2026-10-09, see commit 2f8acf2) to
the new extraction/ package layout. For every *.ifc file in the data directory, runs
the full extraction + post-processing pipeline and writes results to a per-file
output folder.

Usage:
    uv run python scripts/extract_batch.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from extraction import IfcDataExtractor  # noqa: E402
from file_identity import compute_content_key  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "data" / "extracted"


def process_ifc_file(input_path, output_path):

    extractor = IfcDataExtractor(str(input_path), str(output_path))

    extractor.extract_all_floors()
    extractor.post_processing_floors_to_slabs()

    extractor.extract_all_columns()
    extractor.extract_all_walls()
    extractor.extract_all_curtainwalls()
    extractor.post_processing_walls()

    extractor.wall_column_floor_location_display(
        view_elev=40, view_azim=-130,
        plot_main_plane_directions=True, plot_main_plane=True, plane_vector_length=1,
    )


def main():
    if not DATA_DIR.is_dir():
        print(f"Data directory not found: {DATA_DIR}")
        return

    ifc_files = sorted(DATA_DIR.glob("*.ifc"))
    if not ifc_files:
        print(f"No .ifc files found in {DATA_DIR}")
        return

    for ifc_file in ifc_files:
        # Content key, not the filename stem - the same key
        # scripts/recognize_intents.py uses, so both entry points keep
        # sharing one extraction cache directory per model (and two copies of
        # the same model under different names now share it too, instead of
        # extracting twice). See src/file_identity.py /
        # docs/architecture.md "One key for everything".
        output_path = OUTPUT_DIR / compute_content_key(ifc_file)
        print(f"Extracting {ifc_file.name} -> {output_path}")
        try:
            process_ifc_file(ifc_file, output_path)
        except Exception as e:
            print(f"Error processing {ifc_file.name}: {e}")


if __name__ == "__main__":
    main()
