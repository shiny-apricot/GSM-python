#!/usr/bin/env python3
"""
Re-run Biological Validation for Seed Stability Experiment

Purpose:
    The original seed stability experiment lost internet during the
    Enrichr / STRING queries.  This script reads the existing results
    JSON, retries biological validation for every seed-run whose PPI
    and enrichment data are missing, and writes the updated JSON back.

Usage:
    python scripts/maintenance/rerun_seed_bio_validation.py
"""

import json
import logging
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.biological_validation import query_enrichr, query_string_db


RESULTS_PATH = project_root / "output" / "seed_stability" / "seed_stability_results.json"
DELAY_BETWEEN_CALLS = 2  # seconds, to avoid rate-limiting


def setup_logger():
    logger = logging.getLogger("rerun_bio")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S")
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger


def main():
    logger = setup_logger()

    if not RESULTS_PATH.exists():
        logger.error(f"Results file not found: {RESULTS_PATH}")
        return

    data = json.loads(RESULTS_PATH.read_text())
    comparisons = data["comparisons"]

    total_runs = sum(len(c["seed_results"]) for c in comparisons)
    needs_retry = sum(
        1 for c in comparisons for sr in c["seed_results"]
        if sr["string_ppi_count"] == 0 and not sr["top_kegg_term"]
    )

    logger.info("=" * 60)
    logger.info(f"  Re-running biological validation")
    logger.info(f"  Total seed-runs: {total_runs}")
    logger.info(f"  Needing retry: {needs_retry}")
    logger.info("=" * 60)

    success = 0
    failed = 0

    for comp in comparisons:
        ds = comp["dataset"]
        for sr in comp["seed_results"]:
            genes = sr.get("top_genes", [])
            if not genes:
                logger.warning(f"  {ds} seed={sr['seed']}: no genes, skipping")
                continue

            # Only retry if both PPI and enrichment are missing
            has_ppi = sr["string_ppi_count"] > 0
            has_enrichment = bool(sr["top_kegg_term"]) or bool(sr["top_disgenet_term"])
            if has_ppi and has_enrichment:
                logger.info(f"  {ds} seed={sr['seed']}: already has data, skipping")
                success += 1
                continue

            # Run Enrichr only if needed
            if not has_enrichment:
                logger.info(f"  {ds} seed={sr['seed']}: querying Enrichr ({len(genes)} genes)...")
                try:
                    enrichr_results = query_enrichr(genes, logger)
                    time.sleep(DELAY_BETWEEN_CALLS)

                    kegg_terms = [r for r in enrichr_results if "KEGG" in r.library]
                    if kegg_terms:
                        best = min(kegg_terms, key=lambda r: r.p_value)
                        sr["top_kegg_term"] = best.term
                        sr["top_kegg_pvalue"] = best.p_value

                    dg_terms = [r for r in enrichr_results if "DisGeNET" in r.library]
                    if dg_terms:
                        best = min(dg_terms, key=lambda r: r.p_value)
                        sr["top_disgenet_term"] = best.term
                        sr["top_disgenet_pvalue"] = best.p_value

                    logger.info(f"    Enrichr OK: KEGG='{sr['top_kegg_term']}' DG='{sr['top_disgenet_term']}'")
                except Exception as e:
                    logger.warning(f"    Enrichr FAILED: {e}")
                    failed += 1
            else:
                logger.info(f"  {ds} seed={sr['seed']}: Enrichr already done, skipping")

            # Run STRING only if needed
            if not has_ppi:
                logger.info(f"  {ds} seed={sr['seed']}: querying STRING ({len(genes)} genes)...")
                try:
                    string_data = query_string_db(genes, logger)
                    time.sleep(DELAY_BETWEEN_CALLS)

                    interactions = string_data.get("interactions", [])
                    sr["string_ppi_count"] = len(interactions)
                    sr["top_interactions"] = [
                        {
                            "protein1": i.protein1,
                            "protein2": i.protein2,
                            "score": i.score,
                        }
                        for i in sorted(interactions, key=lambda x: x.score, reverse=True)[:5]
                    ]
                    logger.info(f"    STRING OK: {sr['string_ppi_count']} interactions")
                    success += 1
                except Exception as e:
                    logger.warning(f"    STRING FAILED: {e}")
                    failed += 1

    # Recompute PPI ranges per dataset
    for comp in comparisons:
        ppis = [sr["string_ppi_count"] for sr in comp["seed_results"]]
        comp["ppi_range"] = f"{min(ppis)}-{max(ppis)}" if ppis else "0-0"

    # Save updated results
    data["comparisons"] = comparisons
    RESULTS_PATH.write_text(json.dumps(data, indent=2))

    logger.info(f"\n{'=' * 60}")
    logger.info(f"  Done. Success: {success}, Failed: {failed}")
    logger.info(f"  Updated: {RESULTS_PATH}")
    logger.info(f"{'=' * 60}")

    # Print summary
    print("\n" + "=" * 90)
    print("  SEED STABILITY — BIOLOGICAL VALIDATION (updated)")
    print("=" * 90)
    print(f"{'Dataset':<10} {'Seed':<6} {'PPI':<6} {'Top KEGG':<30} {'Top DisGeNET':<30}")
    print("-" * 90)
    for comp in comparisons:
        for sr in comp["seed_results"]:
            print(
                f"{comp['dataset']:<10} {sr['seed']:<6} "
                f"{sr['string_ppi_count']:<6} "
                f"{sr.get('top_kegg_term','')[:28]:<30} "
                f"{sr.get('top_disgenet_term','')[:28]:<30}"
            )
    print("=" * 90)


if __name__ == "__main__":
    main()
