"""
🧬 Biological Validation Script for GSM Pipeline

Purpose:
    Validate selected features using external biological databases via APIs.
    Queries Enrichr, STRING-db, and DisGeNET for pathway enrichment and
    protein-protein interactions.

Key Functions:
    - run_biological_validation: Main entry point
    - query_enrichr: Get pathway enrichments from Enrichr API
    - query_string_db: Get PPI network from STRING-db
    - query_disgenet: Get disease associations (requires API key)

Output:
    - Enrichment tables (CSV)
    - STRING network data (JSON/TSV)
    - Validation summary report (TXT)

Example Usage:
    >>> python biological_validation.py output/gsm_2026_01_24-08_46_49

API References:
    - Enrichr: https://maayanlab.cloud/Enrichr/
    - STRING: https://string-db.org/cgi/help.pl?subpage=api
    - DisGeNET: https://www.disgenet.org/api/

File Map:
    Entry point:
        - run_biological_validation(): orchestrates API calls + outputs

    Data extraction:
        - extract_top_genes(): reads top-N genes from results JSON

    API queries:
        - query_enrichr(), query_string_db(), query_disgenet()

    Persistence + reports:
        - save_enrichr_results(), save_string_results(), save_disgenet_results()
        - save_validation_summary(), save_biological_validation_explanation()

    Group-level validation:
        - validate_top_groups(), save_group_validation_results()
"""

import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import requests


##### CONSTANTS #####
ENRICHR_URL = "https://maayanlab.cloud/Enrichr"
STRING_API_URL = "https://string-db.org/api"
DISGENET_API_URL = "https://www.disgenet.org/api"

# Retry settings for external API calls
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 2.0


def _request_with_retry(
    method: str,
    url: str,
    logger: logging.Logger,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    files: dict | None = None,
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF_SECONDS,
) -> requests.Response:
    """Send an HTTP request with exponential-backoff retry on failure.

    Retries on HTTP 429 (rate limit), 5xx (server error), and
    connection/timeout errors.  Raises on non-retryable 4xx.
    """
    backoff = initial_backoff
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            if method.upper() == "GET":
                resp = requests.get(url, params=params, headers=headers, timeout=30)
            else:
                resp = requests.post(url, params=params, headers=headers, files=files, timeout=30)

            # Success
            if resp.status_code == 200:
                return resp

            # Retryable status codes
            if resp.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    f"   ⚠️  API {resp.status_code} on {url} "
                    f"(attempt {attempt}/{max_retries}), retrying in {backoff:.0f}s…"
                )
                time.sleep(backoff)
                backoff *= 2
                last_exception = Exception(
                    f"HTTP {resp.status_code} from {url}"
                )
                continue

            # Non-retryable client error
            resp.raise_for_status()

        except requests.exceptions.ConnectionError as exc:
            # FAST FAIL: Check if this is a complete DNS/internet failure
            if "NameResolutionError" in str(exc) or "Failed to resolve" in str(exc):
                logger.error(
                    f"   ❌ Fatal network error (DNS) on {url}. "
                    f"Skipping retries to save time."
                )
                # Immediately raise the exception to break the loop, bypassing the sleep timer
                raise Exception(f"Network offline or DNS failure: {exc}")

            # Standard retry for other types of connection interruptions
            logger.warning(
                f"   ⚠️  Connection error on {url} "
                f"(attempt {attempt}/{max_retries}), retrying in {backoff:.0f}s…"
            )
            last_exception = exc
            time.sleep(backoff)
            backoff *= 2

        except requests.exceptions.Timeout as exc:
            logger.warning(
                f"   ⚠️  Timeout on {url} "
                f"(attempt {attempt}/{max_retries}), retrying in {backoff:.0f}s…"
            )
            last_exception = exc
            time.sleep(backoff)
            backoff *= 2

    raise Exception(
        f"API request to {url} failed after {max_retries} retries: {last_exception}"
    )

# Enrichr gene set libraries to query
ENRICHR_LIBRARIES = [
    "KEGG_2021_Human",
    "GO_Biological_Process_2023",
    "GO_Molecular_Function_2023",
    "Reactome_2022",
    "WikiPathway_2023_Human",
    "DisGeNET",
]


@dataclass
class EnrichmentResult:
    """Result from pathway enrichment analysis."""
    library: str
    term: str
    p_value: float
    adjusted_p_value: float
    overlap: str
    genes: List[str]
    combined_score: float


@dataclass
class StringInteraction:
    """Protein-protein interaction from STRING."""
    protein1: str
    protein2: str
    score: float
    

@dataclass
class DiseaseAssociation:
    """Gene-disease association from DisGeNET."""
    gene: str
    disease_name: str
    disease_id: str
    score: float
    source: str


@dataclass
class ValidationReport:
    """Complete biological validation report."""
    input_genes: List[str]
    enrichr_results: List[EnrichmentResult] = field(default_factory=list)
    string_interactions: List[StringInteraction] = field(default_factory=list)
    disease_associations: List[DiseaseAssociation] = field(default_factory=list)
    string_network_url: str = ""


@dataclass
class GroupValidationResult:
    """Results of biological validation for a gene group."""
    group_name: str
    genes: List[str]
    enrichment_results: List[EnrichmentResult]
    string_interactions: List[StringInteraction]
    network_url: str
    pathway_summary: str


##### MAIN ENTRY POINT #####
def run_biological_validation(
    output_dir: Path,
    results_json_path: Path,
    logger: logging.Logger,
    disgenet_api_key: Optional[str] = None,
    top_n_genes: int = 20,
    grouping_data_path: Optional[Path] = None,
    top_n_groups: int = 5,
    gene_column: str = "feature_id",
    group_column: str = "group_name",
) -> ValidationReport:
    """Run complete biological validation on selected features and groups.
    
    Args:
        output_dir: Directory to save validation results
        results_json_path: Path to modeling_results_all_iterations.json
        logger: Logger instance
        disgenet_api_key: Optional API key for DisGeNET
        top_n_genes: Number of top genes to validate (default: 20)
        grouping_data_path: Optional path to grouping file for group validation
        top_n_groups: Number of top groups to validate (default: 5)
        gene_column: Column name for genes in grouping file
        group_column: Column name for groups in grouping file
    
    Returns:
        ValidationReport with all analysis results
    """
    logger.info("Running biological validation...")
    
    validation_dir = output_dir / "biological_validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    
    # Save explanation file first
    save_biological_validation_explanation(output_dir, logger)
    
    ##### PART 1: Validate Individual Genes #####
    logger.debug("")
    logger.debug("Validating top individual genes")
    logger.debug("-" * 50)
    
    # Extract top genes from results
    genes = extract_top_genes(results_json_path, logger, top_n=top_n_genes)
    logger.debug(f"Validating {len(genes)} genes: {', '.join(genes[:5])}...")
    
    report = ValidationReport(input_genes=genes)
    
    # Query Enrichr
    try:
        enrichr_results = query_enrichr(genes, logger)
        report.enrichr_results = enrichr_results
        save_enrichr_results(enrichr_results, validation_dir, logger)
    except Exception as e:
        logger.warning(f"⚠️ Enrichr query failed: {e}")
    
    # Query STRING-db
    try:
        string_data = query_string_db(genes, logger)
        report.string_interactions = string_data['interactions']
        report.string_network_url = string_data['network_url']
        save_string_results(string_data, validation_dir, logger)
    except Exception as e:
        logger.warning(f"⚠️ STRING-db query failed: {e}")
    
    # Query DisGeNET (if API key provided)
    if disgenet_api_key:
        try:
            disease_assocs = query_disgenet(genes, disgenet_api_key, logger)
            report.disease_associations = disease_assocs
            save_disgenet_results(disease_assocs, validation_dir, logger)
        except Exception as e:
            logger.warning(f"⚠️ DisGeNET query failed: {e}")
    else:
        logger.debug("DisGeNET skipped (no API key)")
    
    # Generate summary report for individual genes
    save_validation_summary(report, validation_dir, logger)
    
    ##### PART 2: Validate Top Groups #####
    if grouping_data_path and grouping_data_path.exists():
        logger.debug("")
        logger.debug("Validating top gene groups")
        logger.debug("-" * 50)
        
        group_results = validate_top_groups(
            output_dir=output_dir,
            grouping_data_path=grouping_data_path,
            logger=logger,
            top_n_groups=top_n_groups,
            gene_column=gene_column,
            group_column=group_column,
        )
        
        if group_results:
            logger.info(f"✅ Validated {len(group_results)} groups")
    else:
        logger.debug("")
        logger.debug("Group validation skipped (no grouping file)")
    
    logger.info(f"Biological validation done: {validation_dir.name}")
    return report


##### GENE EXTRACTION #####
def extract_top_genes(results_path: Path, logger: logging.Logger, top_n: int = 20) -> List[str]:
    """Extract top genes from modeling results based on feature importance.
    
    Tries multiple sources in priority order:
    1. aggregated_feature_ranking_group_derived_rra.xlsx (features ranked by group F1 - RECOMMENDED)
    2. aggregated_feature_ranking_individual_rra.xlsx (features ranked by ML importance)
    3. best_averaged_features.xlsx (averaged across iterations)
    4. modeling_results_all_iterations.json (fallback - aggregate manually)
    """
    output_dir = results_path.parent
    
    # Priority 1: Try group-derived RRA (features ranked by group F1 score)
    group_derived_path = output_dir / "aggregated_feature_ranking_group_derived_rra.xlsx"
    if group_derived_path.exists():
        try:
            import pandas as pd
            df = pd.read_excel(group_derived_path)
            if 'Feature Name' in df.columns:
                top_genes = df['Feature Name'].head(top_n).tolist()
                top_genes = [g.split('(')[0] if '(' in g else g for g in top_genes]
                logger.debug(f"Extracted {len(top_genes)} top genes from group-derived RRA ranking")
                return top_genes
        except Exception as e:
            logger.warning(f"   Could not read group-derived RRA file: {e}")
    
    # Priority 2: Try individual RRA aggregated features
    rra_path = output_dir / "aggregated_feature_ranking_individual_rra.xlsx"
    if rra_path.exists():
        try:
            import pandas as pd
            df = pd.read_excel(rra_path)
            # Get top features by RRA score
            if 'Feature Name' in df.columns:
                top_genes = df['Feature Name'].head(top_n).tolist()
                # Clean gene names (remove suffixes like "(1)" or "(2)")
                top_genes = [g.split('(')[0] if '(' in g else g for g in top_genes]
                logger.debug(f"Extracted {len(top_genes)} top genes from individual RRA ranking")
                return top_genes
        except Exception as e:
            logger.warning(f"   Could not read individual RRA file: {e}")
    
    # Priority 3: Try best averaged features
    avg_path = output_dir / "best_averaged_features.xlsx"
    if avg_path.exists():
        try:
            import pandas as pd
            df = pd.read_excel(avg_path)
            if 'Feature Name' in df.columns:
                top_genes = df['Feature Name'].head(top_n).tolist()
                top_genes = [g.split('(')[0] if '(' in g else g for g in top_genes]
                logger.debug(f"Extracted {len(top_genes)} top genes from averaged features")
                return top_genes
        except Exception as e:
            logger.warning(f"   Could not read averaged features file: {e}")
    
    # Priority 4: Fallback to JSON aggregation
    logger.debug("Using JSON fallback for genes")
    with open(results_path, 'r') as f:
        all_results = json.load(f)
    
    # Aggregate feature importance across all iterations
    gene_scores = {}
    
    for iteration_data in all_results:
        for result in iteration_data.get('results', []):
            importance = result.get('feature_importance', {})
            for gene, score in importance.items():
                # Clean gene name (remove suffixes)
                clean_gene = gene.split('(')[0] if '(' in gene else gene
                if clean_gene not in gene_scores:
                    gene_scores[clean_gene] = []
                gene_scores[clean_gene].append(score)
    
    # Calculate mean importance and sort
    gene_means = {gene: sum(scores)/len(scores) for gene, scores in gene_scores.items()}
    sorted_genes = sorted(gene_means.items(), key=lambda x: x[1], reverse=True)
    
    top_genes = [gene for gene, _ in sorted_genes[:top_n]]
    logger.debug(f"Extracted {len(top_genes)} top genes by importance (JSON fallback)")
    
    return top_genes


##### ENRICHR API #####
def query_enrichr(genes: List[str], logger: logging.Logger) -> List[EnrichmentResult]:
    """Query Enrichr API for pathway enrichment analysis.
    
    Args:
        genes: List of gene symbols
        logger: Logger instance
    
    Returns:
        List of EnrichmentResult objects
    """
    logger.debug("Querying Enrichr...")
    
    # Step 1: Submit gene list (with retry)
    genes_str = "\n".join(genes)
    payload = {
        "list": (None, genes_str),
        "description": (None, "GSM Pipeline Top Features")
    }
    
    response = _request_with_retry(
        "POST", f"{ENRICHR_URL}/addList", logger, files=payload
    )
    
    result = response.json()
    user_list_id = result.get('userListId')
    
    if not user_list_id:
        raise Exception("Failed to get userListId from Enrichr")
    
    logger.debug(f"Enrichr list ID: {user_list_id}")
    
    # Step 2: Query each library
    all_results = []
    
    for library in ENRICHR_LIBRARIES:
        logger.debug(f"Querying: {library}")
        
        try:
            response = _request_with_retry(
                "GET", f"{ENRICHR_URL}/enrich", logger,
                params={"userListId": user_list_id, "backgroundType": library}
            )
        except Exception:
            logger.warning(f"   ⚠️ Failed to query {library} after retries")
            continue
        
        data = response.json()
        terms = data.get(library, [])
        
        # Parse top 10 results per library
        for term_data in terms[:10]:
            # Enrichr returns: [rank, term, p-value, z-score, combined_score, 
            #                   overlapping_genes, adjusted_p-value, old_p-value, old_adj_p-value]
            if len(term_data) >= 7:
                enrichment = EnrichmentResult(
                    library=library,
                    term=term_data[1],
                    p_value=term_data[2],
                    adjusted_p_value=term_data[6] if len(term_data) > 6 else term_data[2],
                    overlap=f"{len(term_data[5])}/{term_data[1].split('(')[-1].rstrip(')') if '(' in term_data[1] else 'N/A'}",
                    genes=term_data[5] if isinstance(term_data[5], list) else [],
                    combined_score=term_data[4]
                )
                all_results.append(enrichment)
        
        # Rate limiting
        time.sleep(0.5)
    
    # Sort by combined score
    all_results.sort(key=lambda x: x.combined_score, reverse=True)
    
    logger.debug(f"Enrichr: {len(all_results)} results")
    return all_results


##### STRING-db API #####
def query_string_db(genes: List[str], logger: logging.Logger, species: int = 9606) -> Dict:
    """Query STRING-db for protein-protein interactions.
    
    Args:
        genes: List of gene symbols
        logger: Logger instance
        species: NCBI taxonomy ID (9606 = human)
    
    Returns:
        Dictionary with interactions list and network URL
    """
    logger.debug("Querying STRING-db...")
    
    genes_str = "%0d".join(genes)
    
    # Get interaction network
    params = {
        "identifiers": genes_str,
        "species": species,
        "caller_identity": "gsm_pipeline"
    }
    
    # Get interactions (with retry)
    try:
        response = _request_with_retry(
            "GET", f"{STRING_API_URL}/json/network", logger, params=params
        )
    except Exception as exc:
        logger.warning(f"   ⚠️ STRING network query failed after retries: {exc}")
        response = None
    
    interactions = []
    if response is not None and response.status_code == 200:
        network_data = response.json()
        
        for edge in network_data:
            interaction = StringInteraction(
                protein1=edge.get('preferredName_A', edge.get('stringId_A', '')),
                protein2=edge.get('preferredName_B', edge.get('stringId_B', '')),
                score=edge.get('score', 0)
            )
            interactions.append(interaction)
        
        logger.debug(f"STRING: {len(interactions)} interactions")
    
    # Generate network image URL
    network_url = (
        f"https://string-db.org/api/image/network?"
        f"identifiers={genes_str}&species={species}&network_flavor=confidence"
    )
    
    # Get enrichment from STRING (with retry)
    try:
        enrichment_response = _request_with_retry(
            "GET", f"{STRING_API_URL}/json/enrichment", logger, params=params
        )
    except Exception as exc:
        logger.warning(f"   ⚠️ STRING enrichment query failed after retries: {exc}")
        enrichment_response = None
    
    string_enrichment = []
    if enrichment_response is not None and enrichment_response.status_code == 200:
        string_enrichment = enrichment_response.json()
        logger.debug(f"STRING enrichment: {len(string_enrichment)} terms")
        
    # Get PPI enrichment stats (p-value, expected edges)
    try:
        ppi_response = _request_with_retry(
            "GET", f"{STRING_API_URL}/json/ppi_enrichment", logger, params=params
        )
    except Exception as exc:
        logger.warning(f"   ⚠️ STRING PPI enrichment query failed after retries: {exc}")
        ppi_response = None
        
    ppi_stats = {}
    if ppi_response is not None and ppi_response.status_code == 200:
        ppi_data = ppi_response.json()
        if len(ppi_data) > 0:
            ppi_stats = ppi_data[0]
            logger.debug(f"STRING PPI stats: p-value {ppi_stats.get('p_value')}")
    
    return {
        "interactions": interactions,
        "network_url": network_url,
        "enrichment": string_enrichment,
        "ppi_stats": ppi_stats
    }


##### DisGeNET API #####
def query_disgenet(
    genes: List[str], 
    api_key: str, 
    logger: logging.Logger
) -> List[DiseaseAssociation]:
    """Query DisGeNET for gene-disease associations.
    
    Args:
        genes: List of gene symbols
        api_key: DisGeNET API key
        logger: Logger instance
    
    Returns:
        List of DiseaseAssociation objects
    """
    logger.debug("Querying DisGeNET...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "accept": "application/json"
    }
    
    all_associations = []
    
    for gene in genes:
        try:
            response = _request_with_retry(
                "GET", f"{DISGENET_API_URL}/gda/gene/{gene}", logger,
                headers=headers
            )
        except Exception:
            logger.warning(f"   ⚠️ DisGeNET query failed for {gene} after retries")
            time.sleep(0.3)
            continue
        
        if response.status_code == 200:
            data = response.json()
            
            for assoc in data[:5]:  # Top 5 per gene
                disease_assoc = DiseaseAssociation(
                    gene=gene,
                    disease_name=assoc.get('disease_name', ''),
                    disease_id=assoc.get('diseaseid', ''),
                    score=assoc.get('score', 0),
                    source=assoc.get('source', '')
                )
                all_associations.append(disease_assoc)
        
        # Rate limiting
        time.sleep(0.3)
    
    logger.debug(f"DisGeNET: {len(all_associations)} associations")
    return all_associations


##### SAVE RESULTS #####
def save_enrichr_results(
    results: List[EnrichmentResult], 
    output_dir: Path, 
    logger: logging.Logger
) -> None:
    """Save Enrichr results to CSV."""
    import csv
    
    output_path = output_dir / "enrichr_results.csv"
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Library', 'Term', 'P-value', 'Adjusted P-value', 
            'Overlap', 'Combined Score', 'Genes'
        ])
        
        for result in results:
            writer.writerow([
                result.library,
                result.term,
                f"{result.p_value:.2e}",
                f"{result.adjusted_p_value:.2e}",
                result.overlap,
                f"{result.combined_score:.2f}",
                "; ".join(result.genes)
            ])
    
    logger.debug(f"Saved: {output_path.name}")


def save_string_results(data: Dict, output_dir: Path, logger: logging.Logger) -> None:
    """Save STRING-db results."""
    import csv
    
    # Save interactions
    interactions_path = output_dir / "string_interactions.csv"
    
    with open(interactions_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Protein 1', 'Protein 2', 'Confidence Score'])
        
        for interaction in data['interactions']:
            writer.writerow([
                interaction.protein1,
                interaction.protein2,
                f"{interaction.score:.3f}"
            ])
    
    logger.debug(f"Saved: {interactions_path.name}")
    
    # Save network URL
    url_path = output_dir / "string_network_url.txt"
    with open(url_path, 'w') as f:
        f.write(f"STRING Network Visualization URL:\n{data['network_url']}\n")
        f.write(f"\nOpen this URL in a browser to view the protein-protein interaction network.\n")
    
    logger.debug(f"Saved: {url_path.name}")
    
    # Save enrichment
    if data.get('enrichment'):
        enrichment_path = output_dir / "string_enrichment.json"
        with open(enrichment_path, 'w') as f:
            json.dump(data['enrichment'], f, indent=2)
        logger.debug(f"Saved: {enrichment_path.name}")
        
    # Save PPI stats
    if data.get('ppi_stats'):
        ppi_stats_path = output_dir / "string_ppi_stats.json"
        with open(ppi_stats_path, 'w') as f:
            json.dump(data['ppi_stats'], f, indent=2)
        logger.debug(f"Saved: {ppi_stats_path.name}")


def save_disgenet_results(
    results: List[DiseaseAssociation], 
    output_dir: Path, 
    logger: logging.Logger
) -> None:
    """Save DisGeNET results to CSV."""
    import csv
    
    output_path = output_dir / "disgenet_associations.csv"
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Gene', 'Disease Name', 'Disease ID', 'Score', 'Source'])
        
        for result in results:
            writer.writerow([
                result.gene,
                result.disease_name,
                result.disease_id,
                f"{result.score:.3f}",
                result.source
            ])
    
    logger.debug(f"Saved: {output_path.name}")


def save_validation_summary(
    report: ValidationReport, 
    output_dir: Path, 
    logger: logging.Logger
) -> None:
    """Save comprehensive validation summary."""
    output_path = output_dir / "validation_summary.txt"
    
    with open(output_path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("BIOLOGICAL VALIDATION SUMMARY - GSM PIPELINE\n")
        f.write("=" * 70 + "\n\n")
        
        # Input genes
        f.write("INPUT GENES:\n")
        f.write("-" * 40 + "\n")
        f.write(", ".join(report.input_genes) + "\n\n")
        
        # Enrichr summary
        f.write("PATHWAY ENRICHMENT (Enrichr):\n")
        f.write("-" * 40 + "\n")
        
        if report.enrichr_results:
            # Group by library
            by_library = {}
            for result in report.enrichr_results:
                if result.library not in by_library:
                    by_library[result.library] = []
                by_library[result.library].append(result)
            
            for library, results in by_library.items():
                f.write(f"\n{library}:\n")
                for r in results[:3]:  # Top 3 per library
                    f.write(f"  • {r.term}\n")
                    f.write(f"    P-value: {r.p_value:.2e}, Combined Score: {r.combined_score:.2f}\n")
                    f.write(f"    Genes: {', '.join(r.genes[:5])}\n")
        else:
            f.write("  No enrichment results available.\n")
        
        f.write("\n")
        
        # STRING summary
        f.write("PROTEIN-PROTEIN INTERACTIONS (STRING-db):\n")
        f.write("-" * 40 + "\n")
        
        if report.string_interactions:
            f.write(f"  Total interactions found: {len(report.string_interactions)}\n\n")
            f.write("  Top interactions by confidence:\n")
            
            sorted_interactions = sorted(
                report.string_interactions, 
                key=lambda x: x.score, 
                reverse=True
            )
            
            for interaction in sorted_interactions[:10]:
                f.write(f"  • {interaction.protein1} <-> {interaction.protein2}")
                f.write(f" (score: {interaction.score:.3f})\n")
            
            f.write(f"\n  Network visualization: {report.string_network_url}\n")
        else:
            f.write("  No protein interactions found.\n")
        
        f.write("\n")
        
        # DisGeNET summary
        f.write("DISEASE ASSOCIATIONS (DisGeNET):\n")
        f.write("-" * 40 + "\n")
        
        if report.disease_associations:
            # Group by gene
            by_gene = {}
            for assoc in report.disease_associations:
                if assoc.gene not in by_gene:
                    by_gene[assoc.gene] = []
                by_gene[assoc.gene].append(assoc)
            
            for gene, assocs in by_gene.items():
                f.write(f"\n  {gene}:\n")
                for a in assocs[:3]:
                    f.write(f"    • {a.disease_name} (score: {a.score:.3f})\n")
        else:
            f.write("  No disease associations retrieved.\n")
            f.write("  (DisGeNET requires API key for queries)\n")
        
        f.write("\n")
        f.write("=" * 70 + "\n")
        f.write("END OF VALIDATION SUMMARY\n")
        f.write("=" * 70 + "\n")
    
    logger.debug(f"Saved: {output_path.name}")


##### GROUP-LEVEL VALIDATION #####
def validate_top_groups(
    output_dir: Path,
    grouping_data_path: Path,
    logger: logging.Logger,
    top_n_groups: int = 5,
    gene_column: str = "feature_id",
    group_column: str = "group_name",
) -> List[GroupValidationResult]:
    """
    Validate top-ranked gene groups from RRA ranking.
    
    This connects your best groups (from aggregated_group_ranking_rra.xlsx)
    to biological databases to show WHY these groups are meaningful.
    
    Args:
        output_dir: Path to GSM output directory
        grouping_data_path: Path to grouping file (to get genes per group)
        logger: Logger instance
        top_n_groups: Number of top groups to validate (default: 5)
        gene_column: Column name for genes in grouping file
        group_column: Column name for groups in grouping file
        
    Returns:
        List of GroupValidationResult for each validated group
    """
    import pandas as pd
    
    ##### STEP 1: Load Top Groups from RRA Ranking #####
    rra_file = output_dir / "aggregated_group_ranking_rra.xlsx"
    if not rra_file.exists():
        logger.warning(f"⚠️ Group ranking file not found: {rra_file}")
        return []
    
    logger.debug(f"Loading top {top_n_groups} groups from RRA")
    
    group_df = pd.read_excel(rra_file)
    
    # Get top N group names (try different column names)
    group_name_col = None
    for col in ['Group Name', 'Group', 'group_name', 'group']:
        if col in group_df.columns:
            group_name_col = col
            break
    
    if group_name_col is None:
        logger.error(f"❌ Cannot find group column in RRA ranking file. Columns: {list(group_df.columns)}")
        return []
    
    top_groups = group_df[group_name_col].head(top_n_groups).tolist()
    logger.debug(f"Top groups: {', '.join(str(g) for g in top_groups[:3])}...")
    
    ##### STEP 2: Load Grouping File to Get Genes per Group #####
    logger.debug("Loading grouping file for genes per group")
    
    if not grouping_data_path.exists():
        logger.warning(f"⚠️ Grouping file not found: {grouping_data_path}")
        return []
    
    # Try different separators
    try:
        grouping_df = pd.read_csv(grouping_data_path, sep=",")
    except:
        try:
            grouping_df = pd.read_csv(grouping_data_path, sep="\t")
        except Exception as e:
            logger.error(f"❌ Could not read grouping file: {e}")
            return []
    
    # Find gene and group columns
    if gene_column not in grouping_df.columns:
        # Try to find a matching column
        for col in grouping_df.columns:
            if 'gene' in col.lower() or 'feature' in col.lower():
                gene_column = col
                break
    
    if group_column not in grouping_df.columns:
        for col in grouping_df.columns:
            if 'group' in col.lower() or 'pathway' in col.lower():
                group_column = col
                break
    
    ##### STEP 3: Validate Each Top Group #####
    results = []
    
    for i, group_name in enumerate(top_groups, 1):
        logger.debug(f"Validating Group {i}/{len(top_groups)}: {group_name}")
        
        # Get genes in this group
        group_genes = grouping_df[grouping_df[group_column] == group_name][gene_column].tolist()
        
        if not group_genes:
            logger.warning(f"      ⚠️ No genes found for group: {group_name}")
            continue
        
        logger.info(f"      Found {len(group_genes)} genes in group")
        
        # Limit to top 50 genes for API queries (avoid overload)
        genes_to_query = group_genes[:50]
        
        # Query Enrichr for pathway enrichment
        enrichment_results = []
        try:
            enrichment_results = query_enrichr(genes_to_query, logger)
        except Exception as e:
            logger.warning(f"      ⚠️ Enrichr query failed: {e}")
        
        # Query STRING for protein interactions
        string_interactions = []
        network_url = ""
        try:
            string_result = query_string_db(genes_to_query, logger)
            string_interactions = string_result.get('interactions', [])
            network_url = string_result.get('network_url', "")
        except Exception as e:
            logger.warning(f"      ⚠️ STRING query failed: {e}")
        
        # Create pathway summary
        sig_pathways = [e for e in enrichment_results if e.p_value < 0.05]
        if sig_pathways:
            top_pathway = sig_pathways[0]
            pathway_summary = f"Top pathway: {top_pathway.term} (p={top_pathway.p_value:.2e})"
        else:
            pathway_summary = "No significant pathways found"
        
        results.append(GroupValidationResult(
            group_name=str(group_name),
            genes=group_genes,
            enrichment_results=enrichment_results,
            string_interactions=string_interactions,
            network_url=network_url,
            pathway_summary=pathway_summary
        ))
        
        # Rate limiting between groups
        time.sleep(1)
    
    ##### STEP 4: Save Group Validation Results #####
    if results:
        save_group_validation_results(results, output_dir, logger)
    
    return results


def save_group_validation_results(
    results: List[GroupValidationResult],
    output_dir: Path,
    logger: logging.Logger
) -> None:
    """Save group validation results to files."""
    import pandas as pd
    
    validation_dir = output_dir / "biological_validation"
    validation_dir.mkdir(exist_ok=True)
    
    ##### Save Excel Summary #####
    summary_data = []
    for result in results:
        # Count significant pathways (p < 0.05)
        sig_pathways = [p for p in result.enrichment_results if p.p_value < 0.05]
        
        summary_data.append({
            "Group": result.group_name,
            "Gene_Count": len(result.genes),
            "Significant_Pathways": len(sig_pathways),
            "Total_Pathways": len(result.enrichment_results),
            "PPI_Interactions": len(result.string_interactions),
            "Top_Pathway": sig_pathways[0].term if sig_pathways else "None",
            "Top_Pathway_Pvalue": sig_pathways[0].p_value if sig_pathways else None,
            "STRING_Network_URL": result.network_url
        })
    
    summary_df = pd.DataFrame(summary_data)
    excel_path = validation_dir / "group_validation_summary.xlsx"
    summary_df.to_excel(excel_path, index=False)
    logger.info(f"   💾 Saved: group_validation_summary.xlsx")
    
    ##### Save Detailed Text Report #####
    report_path = validation_dir / "group_validation_report.txt"
    with open(report_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("GROUP-LEVEL BIOLOGICAL VALIDATION REPORT\n")
        f.write("=" * 70 + "\n\n")
        
        f.write("This report shows how your TOP RANKED GROUPS from the GSM pipeline\n")
        f.write("relate to known biological pathways and protein interactions.\n\n")
        
        f.write("-" * 70 + "\n")
        f.write("WHY THIS MATTERS:\n")
        f.write("-" * 70 + "\n")
        f.write("• Groups with significant pathway enrichment are biologically meaningful\n")
        f.write("• High protein-protein interactions suggest functional gene modules\n")
        f.write("• This validates that your classification is based on real biology\n\n")
        
        for result in results:
            f.write("=" * 70 + "\n")
            f.write(f"GROUP: {result.group_name}\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"Genes in group: {len(result.genes)}\n")
            f.write(f"Sample genes: {', '.join(result.genes[:10])}")
            if len(result.genes) > 10:
                f.write(f" ... and {len(result.genes) - 10} more")
            f.write("\n\n")
            
            # Pathway enrichment
            f.write("PATHWAY ENRICHMENT:\n")
            f.write("-" * 40 + "\n")
            sig_pathways = [p for p in result.enrichment_results if p.p_value < 0.05]
            if sig_pathways:
                for pathway in sig_pathways[:10]:
                    f.write(f"• {pathway.term}\n")
                    f.write(f"  P-value: {pathway.p_value:.2e}, Score: {pathway.combined_score:.1f}\n")
                    if pathway.genes:
                        f.write(f"  Genes: {', '.join(pathway.genes[:5])}\n")
                    f.write("\n")
            else:
                f.write("No significant pathways found (p < 0.05)\n\n")
            
            # Protein interactions
            f.write("PROTEIN-PROTEIN INTERACTIONS:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total interactions: {len(result.string_interactions)}\n")
            if result.network_url:
                f.write(f"View network: {result.network_url}\n")
            f.write("\n")
        
        f.write("=" * 70 + "\n")
        f.write("END OF GROUP VALIDATION REPORT\n")
        f.write("=" * 70 + "\n")
    
    logger.info(f"   💾 Saved: group_validation_report.txt")


##### EXPLANATION FILE #####
def save_biological_validation_explanation(output_dir: Path, logger: logging.Logger) -> None:
    """
    Save an explanation file describing what biological validation means
    and how to interpret the results.
    """
    validation_dir = output_dir / "biological_validation"
    validation_dir.mkdir(exist_ok=True)
    
    explanation_path = validation_dir / "README_BIOLOGICAL_VALIDATION.txt"
    
    content = """
================================================================================
                    BIOLOGICAL VALIDATION - WHAT IT MEANS
================================================================================

OVERVIEW
--------
Biological validation checks if the genes and groups identified by the GSM
pipeline have real biological significance - not just statistical artifacts.

This is CRITICAL for publication because it shows your findings are:
  ✓ Biologically meaningful (not random correlations)
  ✓ Connected to known pathways and diseases
  ✓ Supported by existing scientific knowledge


================================================================================
                           WHAT EACH FILE CONTAINS
================================================================================

1. validation_summary.txt
   ----------------------
   Human-readable summary of all validation results.
   Use this for a quick overview of findings.

2. enrichr_results.csv
   --------------------
   Pathway enrichment analysis results from Enrichr.
   Shows which biological pathways your genes are involved in.
   
   Key columns:
   • Library: Database source (KEGG, GO, Reactome, etc.)
   • Term: Pathway/process name
   • P-value: Statistical significance (lower = more significant)
   • Combined_Score: Enrichr's confidence score (higher = better)
   • Genes: Your genes found in this pathway

3. string_interactions.tsv
   ------------------------
   Protein-protein interaction data from STRING database.
   Shows which of your genes/proteins physically interact.
   
   Key columns:
   • protein1, protein2: Interacting proteins
   • score: Confidence score (0-1, higher = more confident)

4. string_network.json
   --------------------
   Network data for visualization.
   Use the network_url in validation_summary.txt for interactive view.

5. group_validation_summary.xlsx (if group validation enabled)
   ------------------------------------------------------------
   Validation results for your top-ranked gene GROUPS.
   Shows why each group is biologically meaningful.

6. group_validation_report.txt (if group validation enabled)
   ----------------------------------------------------------
   Detailed text report for each validated group.


================================================================================
                         HOW TO INTERPRET RESULTS
================================================================================

PATHWAY ENRICHMENT (Enrichr)
----------------------------
What it tests: "Are my genes over-represented in known biological pathways?"

Good signs:
  ✓ Low p-values (< 0.05) for relevant pathways
  ✓ High combined scores (> 100)
  ✓ Pathways related to your study (e.g., cancer pathways for cancer data)
  ✓ Multiple genes overlapping with each pathway

Example interpretation:
  "KEGG: Central carbon metabolism in cancer (p=6.76e-09)"
  → Your genes are significantly enriched in cancer metabolism pathways
  → This supports biological relevance of your findings

Red flags:
  ✗ No significant pathways (p > 0.05 for all)
  ✗ Only generic pathways (e.g., "RNA binding")
  ✗ Pathways unrelated to your study context


PROTEIN-PROTEIN INTERACTIONS (STRING)
-------------------------------------
What it tests: "Do my genes encode proteins that interact with each other?"

Good signs:
  ✓ Many interactions among your genes (> 20)
  ✓ High confidence scores (> 0.7)
  ✓ Network forms connected clusters

Interpretation:
  High interactions = Your genes form a functional network
  → They work together in the cell
  → Not random genes, but a coherent biological module

Example:
  "57 interactions found, top: HRAS <-> BRAF (score: 0.999)"
  → HRAS and BRAF are well-known interacting proteins
  → Your pipeline correctly identified the RAS-RAF signaling axis


DISEASE ASSOCIATIONS (DisGeNET)
-------------------------------
What it tests: "Are my genes associated with known diseases?"

Good signs:
  ✓ Genes associated with diseases relevant to your study
  ✓ High association scores

Example:
  "TP53 associated with: Malignant neoplasm (score: 0.95)"
  → TP53 is a well-known cancer gene
  → Your pipeline correctly identified it


================================================================================
                        FOR YOUR PUBLICATION
================================================================================

You can include these statements in your paper:

Methods section:
  "Biological validation was performed using Enrichr for pathway enrichment,
   STRING-db for protein-protein interaction analysis, and DisGeNET for
   disease associations."

Results section:
  "The top-ranked genes showed significant enrichment in [X] pathways
   (p < 0.05), including [pathway1], [pathway2], and [pathway3].
   STRING analysis revealed [N] protein-protein interactions among the
   selected genes, suggesting they form a functional network."

Discussion:
  "The biological validation confirms that our GSM pipeline identified
   genes with known roles in [disease/process], supporting the biological
   relevance of our classification model."


================================================================================
                              API REFERENCES
================================================================================

Enrichr:
  Chen EY, et al. Enrichr: interactive and collaborative HTML5 gene list
  enrichment analysis tool. BMC Bioinformatics. 2013;14:128.
  https://maayanlab.cloud/Enrichr/

STRING:
  Szklarczyk D, et al. STRING v11: protein-protein association networks
  with increased coverage. Nucleic Acids Res. 2019;47:D483-D490.
  https://string-db.org/

DisGeNET:
  Piñero J, et al. DisGeNET: a comprehensive platform integrating information
  on human disease-associated genes and variants. Nucleic Acids Res. 2017.
  https://www.disgenet.org/

================================================================================
"""
    
    with open(explanation_path, "w") as f:
        f.write(content)
    
    logger.info(f"   💾 Saved: README_BIOLOGICAL_VALIDATION.txt (explanation file)")


##### STANDALONE EXECUTION #####
if __name__ == "__main__":
    import sys
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(
        description="Run biological validation on GSM pipeline results"
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Path to GSM output directory (e.g., output/gsm_2026_01_24-08_46_49)"
    )
    parser.add_argument(
        "--disgenet-key",
        type=str,
        default=None,
        help="DisGeNET API key (optional)"
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    results_path = output_dir / "modeling_results_all_iterations.json"
    
    if not results_path.exists():
        print(f"Error: Results file not found: {results_path}")
        sys.exit(1)
    
    report = run_biological_validation(
        output_dir, 
        results_path, 
        logger,
        disgenet_api_key=args.disgenet_key
    )
    
    print(f"\n✅ Biological validation complete!")
    print(f"   Enrichment results: {len(report.enrichr_results)}")
    print(f"   Protein interactions: {len(report.string_interactions)}")
    print(f"   Disease associations: {len(report.disease_associations)}")
    print(f"\n   View STRING network: {report.string_network_url}")
