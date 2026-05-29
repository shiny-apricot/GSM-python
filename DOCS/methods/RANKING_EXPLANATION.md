# Aggregated Group Ranking

Understanding the `aggregated_group_ranking.xlsx` file.

## What this file represents

This output combines multiple ranked group lists (one per iteration) into a single stable ranking using **Robust Rank Aggregation (RRA)**. Each group is scored based on how consistently it appears near the top across all lists.

## How aggregation works

1. For each iteration, groups are ranked (`1 = best`). Missing groups are treated as the worst rank in that list.
2. Each rank is converted into a normalized rank (`rank / list_size`).
3. RRA computes a **p-value** from the ordered normalized ranks using order statistics.
4. **Aggregated Score** = `-log10(aggregated p-value)`. Higher means stronger evidence of consistently high ranking.
5. **Average Rank** is the mean of the raw ranks across lists.

## Column Meanings

| Column | Description |
|---|---|
| **Rank** | Final order after aggregation (lower is better). |
| **Group Name** | The group label being aggregated. |
| **Aggregated P-Value** | RRA probability that a group would achieve its observed ranks by chance. Smaller is better. |
| **Aggregated Score** | `-log10(Aggregated P-Value)`. Higher is better. |
| **Average Rank** | Mean raw rank across all lists (lower is better). |
| **Occurrences** | How many lists the group appeared in (missing lists count as absent). |

**Notes:**
- Ties are resolved by lower Aggregated P-Value, then lower Average Rank.
- Missing groups are penalized by assigning the worst rank for that list.

## Biological Validation Integration

When biological validation is enabled (`RUN_BIOLOGICAL_VALIDATION=True`), the top groups from `aggregated_group_ranking_rra.xlsx` are automatically validated:

1. The top 5 groups (by RRA ranking) are extracted.
2. All genes within each group are collected from the original grouping file.
3. For each group, biological databases are queried:
   - **Enrichr:** Pathway enrichment (KEGG, GO, Reactome)
   - **STRING-db:** Protein-protein interaction network
4. Results are saved to:
   - `group_validation_summary.xlsx`: Detailed per-group results.
   - `group_validation_report.txt`: Human-readable summary.
   - `README_BIOLOGICAL_VALIDATION.txt`: Interpretation guide.

This connects your best-performing groups (from the ML analysis) to known biological pathways and networks, helping you understand *why* these groups are predictive.
