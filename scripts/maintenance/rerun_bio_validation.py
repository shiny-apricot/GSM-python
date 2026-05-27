"""
Re-run biological validation for datasets that had API failures.

Usage:
    python scripts/maintenance/rerun_bio_validation.py
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.biological_validation import run_biological_validation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("bio_rerun")


##### DATASETS THAT NEED RE-VALIDATION #####
DATASETS = {
    "GDS2547": "gsm_2026_02_13-14_57_25_GDS2547_cancer-DisGeNET_gedinet",
    "GDS2771": "gsm_2026_02_13-15_42_52_GDS2771_cancer-DisGeNET_gedinet",
    "GDS3837": "gsm_2026_02_14-04_34_24_GDS3837_cancer-DisGeNET_gedinet",
    "GDS5499": "gsm_2026_02_14-09_02_14_GDS5499_cancer-DisGeNET_gedinet",
}

OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"


def main():
    for gds_id, folder_name in DATASETS.items():
        output_dir = OUTPUT_ROOT / folder_name
        results_json = output_dir / "modeling_results_all_iterations.json"

        if not results_json.exists():
            logger.error(f"Results JSON not found for {gds_id}: {results_json}")
            continue

        logger.info(f"{'='*60}")
        logger.info(f"Re-running biological validation for {gds_id}")
        logger.info(f"  Dir: {output_dir.name}")
        logger.info(f"{'='*60}")

        try:
            report = run_biological_validation(
                output_dir=output_dir,
                results_json_path=results_json,
                logger=logger,
                top_n_genes=20,
            )
            logger.info(
                f"  {gds_id} done — "
                f"Enrichr: {len(report.enrichr_results)}, "
                f"STRING: {len(report.string_interactions)}"
            )
        except Exception as e:
            logger.error(f"  {gds_id} FAILED: {e}")

    logger.info("All re-validations complete.")


if __name__ == "__main__":
    main()
