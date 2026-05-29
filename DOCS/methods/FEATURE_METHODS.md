# Feature Ranking Methods in the GSM Pipeline

The GSM pipeline provides **TWO** different methods for ranking features (genes). Understanding the difference is crucial for interpreting your results.

> **IMPORTANT:** Feature scoring is performed EACH ITERATION using that iteration's training data. This ensures proper evaluation since train/test splits differ across iterations. The rankings are then aggregated using Robust Rank Aggregation.

---

## METHOD 1: Individual Feature Ranking (ML-Based)

**Files:**
- `ranked_features_individual_all_iterations.xlsx`
- `aggregated_feature_ranking_individual_rra.xlsx`

**How it works:**
Each feature is scored **INDEPENDENTLY** based on three metrics:

1. **F1 Score:** Binary classification performance using the median threshold.
   - For each feature, samples above median → class 1, below → class 0.
   - Compare predictions to actual labels → compute F1.
2. **Importance Score:** Random Forest feature importance.
   - Train RF on ALL features together.
   - Extract Gini importance for each feature.
3. **Mutual Information:** Information-theoretic dependency.
   - Measures how much knowing the feature reduces uncertainty about the label.

**Ranking:** Features are ranked by `importance_score` (descending).

- **Pros:**
  - Considers each feature's individual predictive power.
  - Independent of group assignments.
- **Cons:**
  - Does NOT consider how features work together in groups.
  - A feature might rank high but belong to a low-performing group.

---

## METHOD 2: Group-Derived Feature Ranking (Recommended) ⭐

**Files:**
- `ranked_features_group_derived_all_iterations.xlsx`
- `aggregated_feature_ranking_group_derived_rra.xlsx`

**How it works:**
Features are ranked based on their **GROUP'S** performance:

1. Groups are scored by F1 (using cross-validation with all group features).
2. Groups are ranked from best F1 to worst F1.
3. Each feature inherits the F1 score of its BEST performing group.
4. Features are ranked by their group's F1 score.

**Example:**
- Gene `ABC` is in Group X (F1=0.95) and Group Y (F1=0.80).
- Gene `ABC` gets assigned to Group X (best group) with F1=0.95.
- Gene `ABC` is ranked among the top features.

**Ranking:** Features wrapped by `best_group_f1` (descending).

- **Pros:**
  - Directly reflects biological pathway/group effectiveness.
  - Features from top-performing groups rank higher.
  - Aligns with the GSM methodology (groups are the key unit).
  - Better for biological interpretation.
- **Cons:**
  - A feature's rank depends on its group assignment.
  - Individual feature importance is not considered.

---

## ROBUST RANK AGGREGATION (RRA) - Applied to Both Methods

After each iteration produces a ranked list, RRA combines them:

1. Each iteration produces a feature ranking (order statistics).
2. Ranks are normalized to `[0, 1]`.
3. RRA computes a p-value from order statistics (beta distribution).
4. Features consistently ranked near the top across iterations get low p-values.
5. Final ranking: sort by aggregated p-value (ascending).

**Output columns:**
- **Aggregated P-Value:** Lower = more consistently high-ranked.
- **Aggregated Score:** `-log10(p-value)`, higher = better.
- **Average Rank:** Mean rank across iterations.
- **Occurrences:** How many iterations the feature appeared in.

---

## Which Method Should I Use?

#### For BIOLOGICAL VALIDATION and publication:
- Use **GROUP-DERIVED** ranking (`aggregated_feature_ranking_group_derived_rra.xlsx`).
- This aligns with the GSM philosophy: groups (pathways) are the key.
- Features from best groups are most relevant to your phenotype.

#### For MACHINE LEARNING feature selection:
- Use **INDIVIDUAL** ranking (`aggregated_feature_ranking_individual_rra.xlsx`).
- Identifies individually predictive features.
- May miss features that only work well in combination.

#### For COMPLETE ANALYSIS:
- Compare both rankings.
- Features that appear in the top 20 of BOTH methods are high-confidence.

---

## Output File Columns

### Individual Ranking Columns
- **feature_name:** Gene/feature identifier
- **f1_score:** Individual F1 classification performance
- **importance_score:** Random Forest importance
- **mutual_info:** Mutual information with target
- **iteration:** Which iteration this was from

### Group-Derived Ranking Columns
- **feature_name:** Gene/feature identifier
- **best_group_name:** Name of the best-performing group containing this feature
- **group_f1_score:** F1 score of that group
- **group_rank:** Rank of that group in this iteration
- **feature_rank:** This feature's rank (derived from group rank)
- **iteration:** Which iteration this was from

### Aggregated Ranking Columns (Both Methods)
- **Rank:** Final RRA rank (`1 = best`)
- **Feature Name:** Gene identifier
- **Aggregated P-Value:** RRA p-value (lower = more consistently high-ranked)
- **Aggregated Score:** `-log10(p-value)`
- **Average Rank:** Mean rank across all iterations
- **Occurrences:** Number of iterations where feature appeared

**Additional for group-derived:**
- **Most Common Group:** The group this feature was most often assigned to
- **Average Group F1:** Mean F1 score of the feature's best groups