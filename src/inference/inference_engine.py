"""
🏥 Inference Engine — Predict Disease Status for New Patient Samples

Purpose:
    Core inference logic that takes a saved ModelBundle and new patient
    expression data, then produces confidence-scored predictions using
    an ensemble of trained models.

Key Functions:
    - infer(): Main entry point — bundle + patient data → predictions
    - preprocess_patient_data(): Apply saved scaler + feature selection
    - _ensemble_predict(): Combine predictions from multiple models

Ensemble Strategies:
    - mean_probability: Average predicted probabilities (default, recommended)
    - majority_vote: Hard vote across models

Example Usage:
    >>> from src.inference import load_bundle, infer
    >>> bundle = load_bundle(Path("output/bundles/bundle_GDS2545.gsm.zip"))
    >>> results = infer(bundle, patient_df, logger=logger)
    >>> for r in results:
    ...     print(f"Sample {r.sample_id}: {r.predicted_class} "
    ...           f"(confidence={r.confidence:.2%})")
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.inference.model_bundle import ModelBundle


##### Data Structures #####

@dataclass
class InferenceResult:
    """Prediction result for a single patient sample.

    Attributes:
        sample_id: Identifier for the patient sample
        predicted_class: Human-readable class label ('positive'/'negative')
        predicted_label: Mapped class label (e.g. 'disease'/'control')
        confidence: Ensemble confidence score (0.0–1.0)
        risk_level: Clinical risk category based on confidence
        agreement_ratio: Fraction of models that agree on the prediction
        individual_probabilities: Per-model probability of positive class
        top_contributing_genes: Most important features for this prediction
    """
    sample_id: str
    predicted_class: str
    predicted_label: str
    confidence: float
    risk_level: str
    agreement_ratio: float
    individual_probabilities: list[float]
    top_contributing_genes: dict[str, float] = field(default_factory=dict)


@dataclass
class InferenceSummary:
    """Summary of inference across all patient samples."""
    n_samples: int
    n_positive: int
    n_negative: int
    mean_confidence: float
    results: list[InferenceResult]
    bundle_id: str
    model_name: str
    ensemble_strategy: str
    training_dataset: str = ""
    n_training_samples: int = 0
    n_features_expected: int = 0
    bundle_created_at: str = ""
    bundle_sklearn_version: str = ""


##### Constants #####
RISK_THRESHOLD_HIGH = 0.80
RISK_THRESHOLD_MEDIUM = 0.55
DEFAULT_TOP_GENES = 10


##### Core Functions #####

def preprocess_patient_data(
    patient_data: pd.DataFrame,
    bundle: ModelBundle,
    logger: logging.Logger,
) -> pd.DataFrame:
    """Preprocess patient expression data to match training conditions.

    Applies the same normalization scaler and feature selection that
    were used during training. This is critical for inference accuracy.

    Args:
        patient_data: Raw patient expression matrix (samples × genes)
        bundle: Loaded ModelBundle with scaler and feature names
        logger: Logger instance

    Returns:
        Preprocessed DataFrame with exactly the features the model expects

    Raises:
        ValueError: If too many required features are missing
    """
    required_features = bundle.metadata.feature_names
    available_features = [f for f in required_features if f in patient_data.columns]
    missing_features = [f for f in required_features if f not in patient_data.columns]

    if not available_features:
        raise ValueError(
            "No matching features found in patient data. "
            f"Expected features like: {required_features[:5]}"
        )

    # Warn about missing features (common in cross-platform scenarios)
    missing_ratio = len(missing_features) / len(required_features)
    if missing_ratio > 0.5:
        raise ValueError(
            f"Too many features missing ({len(missing_features)}/{len(required_features)} = "
            f"{missing_ratio:.0%}). Patient data may be from an incompatible platform."
        )
    if missing_features:
        logger.warning(
            f"⚠️ {len(missing_features)}/{len(required_features)} features missing "
            f"from patient data. Missing features will be zero-filled."
        )

    # Build feature matrix with exact column order
    X = pd.DataFrame(0.0, index=patient_data.index, columns=required_features)
    X[available_features] = patient_data[available_features].values

    # Coerce to numeric (handle any non-numeric values)
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    # Apply the saved normalization scaler
    try:
        X_scaled = pd.DataFrame(
            bundle.scaler.transform(X),
            columns=required_features,
            index=patient_data.index,
        )
    except Exception as e:
        logger.warning(f"⚠️ Scaler transform failed ({e}), using raw values")
        X_scaled = X

    return X_scaled


def _classify_risk(confidence: float, predicted_positive: bool) -> str:
    """Map confidence score to clinical risk level.

    For positive predictions (disease): higher confidence = higher risk.
    For negative predictions (control): higher confidence = lower risk.
    """
    if predicted_positive:
        if confidence >= RISK_THRESHOLD_HIGH:
            return "HIGH"
        elif confidence >= RISK_THRESHOLD_MEDIUM:
            return "MEDIUM"
        else:
            return "LOW"
    else:
        # Negative prediction — invert the scale
        if confidence >= RISK_THRESHOLD_HIGH:
            return "LOW"       # Very confident it's NOT disease
        elif confidence >= RISK_THRESHOLD_MEDIUM:
            return "MEDIUM"
        else:
            return "HIGH"      # Not confident it's negative → still risky


def _get_ensemble_feature_importance(
    bundle: ModelBundle,
    top_n: int = DEFAULT_TOP_GENES,
) -> dict[str, float]:
    """Aggregate feature importances across all models, weighted by F1.

    Models with higher F1 contribute proportionally more to the
    aggregated importance vector.  Only works for tree-based models
    that expose feature_importances_.
    """
    importances = np.zeros(len(bundle.metadata.feature_names))
    weight_sum = 0.0

    for model_artifact in bundle.models:
        model = model_artifact.model
        if hasattr(model, "feature_importances_"):
            fi = model.feature_importances_
            if len(fi) == len(importances):
                w = max(model_artifact.f1_score, 0.01)
                importances += fi * w
                weight_sum += w

    if weight_sum > 0:
        importances /= weight_sum

    # Build name→importance dict, sorted descending
    feature_importance = dict(
        zip(bundle.metadata.feature_names, importances)
    )
    sorted_features = sorted(
        feature_importance.items(), key=lambda x: x[1], reverse=True
    )
    return dict(sorted_features[:top_n])


def _get_per_sample_importance(
    bundle: ModelBundle,
    X_row: np.ndarray,
    top_n: int = DEFAULT_TOP_GENES,
) -> dict[str, float]:
    """Compute per-sample feature contribution using prediction variance.

    For each feature, measures how much the ensemble's prediction
    changes when that feature is replaced with its training-set mean
    (approximated as 0 in scaled space). This is a fast, model-agnostic
    approximation of SHAP-style local importance.

    Args:
        bundle: Loaded ModelBundle
        X_row: Preprocessed feature vector for one sample (1-D array)
        top_n: Number of top features to return

    Returns:
        Dict of gene name → importance score, sorted descending
    """
    feature_names = bundle.metadata.feature_names
    n_features = len(feature_names)

    # Baseline prediction with all features
    baseline_probs = []
    for ma in bundle.models:
        model = ma.model
        try:
            if hasattr(model, "predict_proba"):
                baseline_probs.append(model.predict_proba(X_row.reshape(1, -1))[0, 1])
            else:
                baseline_probs.append(float(model.predict(X_row.reshape(1, -1))[0]))
        except Exception:
            continue

    if not baseline_probs:
        return _get_ensemble_feature_importance(bundle, top_n)

    baseline = np.mean(baseline_probs)

    # For efficiency, only test the top global features (not all 20k)
    global_imp = _get_ensemble_feature_importance(bundle, top_n=min(n_features, 50))
    candidate_indices = {
        i for i, fname in enumerate(feature_names) if fname in global_imp
    }

    importances = {}
    for idx in candidate_indices:
        # Zero-out the feature (replace with training mean in scaled space)
        X_perturbed = X_row.copy()
        X_perturbed[idx] = 0.0

        perturbed_probs = []
        for ma in bundle.models:
            model = ma.model
            try:
                if hasattr(model, "predict_proba"):
                    perturbed_probs.append(
                        model.predict_proba(X_perturbed.reshape(1, -1))[0, 1]
                    )
                else:
                    perturbed_probs.append(
                        float(model.predict(X_perturbed.reshape(1, -1))[0])
                    )
            except Exception:
                continue

        if perturbed_probs:
            shift = abs(baseline - np.mean(perturbed_probs))
            importances[feature_names[idx]] = round(float(shift), 6)

    # Sort and take top-N
    sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_imp[:top_n])


def infer(
    bundle: ModelBundle,
    patient_data: pd.DataFrame,
    *,
    logger: logging.Logger,
    sample_id_column: Optional[str] = None,
    top_genes: int = DEFAULT_TOP_GENES,
) -> InferenceSummary:
    """Run clinical inference on new patient expression data.

    Preprocesses the data using the bundle's saved scaler, then
    generates F1-weighted ensemble predictions with confidence scores.
    Models with higher held-out F1 contribute proportionally more
    to both the probability estimates and the feature importances.

    Args:
        bundle: Loaded ModelBundle
        patient_data: Patient expression matrix (samples × genes).
            May include a sample ID column and/or label column.
        logger: Logger instance
        sample_id_column: Column name for sample IDs (optional).
            If None, uses DataFrame index.
        top_genes: Number of top genes to include in each result

    Returns:
        InferenceSummary with per-sample results and overall statistics

    Example:
        >>> bundle = load_bundle("bundle_GDS2545.gsm.zip")
        >>> data = pd.read_csv("new_patients.csv")
        >>> summary = infer(bundle, data, logger=logger)
        >>> for r in summary.results:
        ...     print(f"{r.sample_id}: {r.predicted_label} ({r.risk_level})")
    """
    meta = bundle.metadata
    strategy = meta.ensemble_strategy
    label_map = meta.label_mapping
    pos_label = label_map.get("positive", "positive")
    neg_label = label_map.get("negative", "negative")

    logger.info(
        f"🏥 Clinical inference: {len(patient_data)} samples, "
        f"{meta.n_models_saved} models ({strategy})"
    )

    # Determine sample IDs
    if sample_id_column and sample_id_column in patient_data.columns:
        sample_ids = patient_data[sample_id_column].astype(str).tolist()
        # Drop the ID column before preprocessing
        data_for_inference = patient_data.drop(columns=[sample_id_column])
    else:
        sample_ids = [str(idx) for idx in patient_data.index]
        data_for_inference = patient_data

    # Drop any label/class columns if present (inference doesn't need them)
    cols_to_drop = []
    for col in ["class", "label", "target", "Class", "Label", "Target"]:
        if col in data_for_inference.columns:
            cols_to_drop.append(col)
    if cols_to_drop:
        logger.info(f"  Dropping label columns: {cols_to_drop}")
        data_for_inference = data_for_inference.drop(columns=cols_to_drop)

    # Preprocess patient data
    X = preprocess_patient_data(data_for_inference, bundle, logger)

    # Get ensemble-level feature importance (fallback for all samples)
    ensemble_importance = _get_ensemble_feature_importance(bundle, top_genes)

    # Decide whether to compute per-sample importance
    # (skip for very large batches to stay fast)
    compute_per_sample = len(X) <= 200

    # Collect predictions from all models
    n_models = len(bundle.models)
    all_probabilities = np.zeros((len(X), n_models))
    all_predictions = np.zeros((len(X), n_models), dtype=int)

    # Compute per-model F1 weights (models with higher F1 contribute more)
    f1_scores = np.array([m.f1_score for m in bundle.models])
    model_weights = np.maximum(f1_scores, 0.01)  # avoid zero weights
    model_weights = model_weights / model_weights.sum()

    for i, model_artifact in enumerate(bundle.models):
        model = model_artifact.model
        try:
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(X)[:, 1]
            elif hasattr(model, "decision_function"):
                # Normalize decision function to [0, 1]
                raw = model.decision_function(X)
                proba = 1.0 / (1.0 + np.exp(-raw))
            else:
                proba = model.predict(X).astype(float)

            all_probabilities[:, i] = proba
            all_predictions[:, i] = (proba >= 0.5).astype(int)
        except Exception as e:
            logger.warning(f"⚠️ Model {i} prediction failed: {e}")
            all_probabilities[:, i] = 0.5
            all_predictions[:, i] = 0

    # Generate results per sample
    results = []
    for row_idx in range(len(X)):
        sample_probas = all_probabilities[row_idx]
        sample_preds = all_predictions[row_idx]

        # Ensemble prediction — F1-weighted
        if strategy == "mean_probability":
            ensemble_prob = float(np.dot(model_weights, sample_probas))
            predicted_positive = ensemble_prob >= 0.5
        else:  # majority_vote
            weighted_votes = float(np.dot(model_weights, sample_preds))
            predicted_positive = weighted_votes >= 0.5
            ensemble_prob = weighted_votes

        # Confidence = distance from decision boundary
        confidence = abs(ensemble_prob - 0.5) * 2  # Scale to 0–1

        # Agreement ratio (F1-weighted)
        if predicted_positive:
            agreement = float(np.dot(model_weights, sample_preds))
        else:
            agreement = float(np.dot(model_weights, 1 - sample_preds))

        predicted_class = "positive" if predicted_positive else "negative"
        predicted_label = pos_label if predicted_positive else neg_label
        risk_level = _classify_risk(confidence, predicted_positive)

        # Per-sample gene importance (falls back to ensemble if batch is large)
        if compute_per_sample:
            sample_importance = _get_per_sample_importance(
                bundle, X.values[row_idx], top_genes
            )
        else:
            sample_importance = ensemble_importance

        results.append(InferenceResult(
            sample_id=sample_ids[row_idx],
            predicted_class=predicted_class,
            predicted_label=predicted_label,
            confidence=round(confidence, 4),
            risk_level=risk_level,
            agreement_ratio=round(agreement, 4),
            individual_probabilities=[round(float(p), 4) for p in sample_probas],
            top_contributing_genes=sample_importance,
        ))

    # Summary statistics
    n_positive = sum(1 for r in results if r.predicted_class == "positive")
    n_negative = len(results) - n_positive
    mean_confidence = float(np.mean([r.confidence for r in results])) if results else 0.0

    logger.info(
        f"✅ Inference complete: {n_positive} positive, {n_negative} negative "
        f"(mean confidence: {mean_confidence:.2%})"
    )

    return InferenceSummary(
        n_samples=len(results),
        n_positive=n_positive,
        n_negative=n_negative,
        mean_confidence=round(mean_confidence, 4),
        results=results,
        bundle_id=meta.bundle_id,
        model_name=meta.model_name,
        ensemble_strategy=strategy,
        training_dataset=meta.dataset_name,
        n_training_samples=meta.n_training_samples,
        n_features_expected=meta.n_features,
        bundle_created_at=meta.created_at,
        bundle_sklearn_version=meta.sklearn_version,
    )


##### Multi-Bundle Inference #####

@dataclass
class MultiBundleResult:
    """Aggregated prediction for one sample across multiple bundles.

    Each bundle (trained on a different dataset) produces its own
    prediction.  This dataclass merges those into a single consensus.

    Attributes:
        sample_id: Patient sample identifier
        predicted_class: Consensus class ('positive' / 'negative')
        consensus_confidence: Mean confidence across bundles
        risk_level: Clinical risk from consensus confidence
        bundle_predictions: Per-bundle detail (bundle_id → InferenceResult)
        n_bundles_positive: How many bundles predicted positive
        n_bundles_total: Total bundles that contributed
        agreement_ratio: Fraction of bundles that agree with consensus
        top_contributing_genes: Merged gene importance across bundles
    """
    sample_id: str
    predicted_class: str
    consensus_confidence: float
    risk_level: str
    bundle_predictions: dict[str, InferenceResult]
    n_bundles_positive: int
    n_bundles_total: int
    agreement_ratio: float
    top_contributing_genes: dict[str, float] = field(default_factory=dict)


@dataclass
class MultiBundleSummary:
    """Summary of multi-bundle inference across all patient samples."""
    n_samples: int
    n_positive: int
    n_negative: int
    mean_confidence: float
    results: list[MultiBundleResult]
    bundle_ids: list[str]
    n_bundles: int


def _merge_gene_importances(
    per_bundle: list[dict[str, float]],
    top_n: int = DEFAULT_TOP_GENES,
) -> dict[str, float]:
    """Merge gene importance dicts from multiple bundles.

    Averages the importance of each gene across the bundles
    that include it, then returns the top-N.
    """
    gene_scores: dict[str, list[float]] = {}
    for imp_dict in per_bundle:
        for gene, score in imp_dict.items():
            gene_scores.setdefault(gene, []).append(score)

    averaged = {
        gene: round(float(np.mean(scores)), 6)
        for gene, scores in gene_scores.items()
    }
    sorted_genes = sorted(averaged.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_genes[:top_n])


def multi_infer(
    bundles: list[ModelBundle],
    patient_data: pd.DataFrame,
    *,
    logger: logging.Logger,
    sample_id_column: Optional[str] = None,
    top_genes: int = DEFAULT_TOP_GENES,
    weight_by_f1: bool = True,
) -> MultiBundleSummary:
    """Run clinical inference across multiple model bundles.

    Each bundle was trained on a different dataset and contains
    its own feature set, scaler, and ensemble of models.  This
    function runs ordinary ``infer()`` per bundle, then combines
    the predictions into a weighted consensus.

    Args:
        bundles: List of loaded ModelBundle objects
        patient_data: Patient expression matrix (samples × genes)
        logger: Logger instance
        sample_id_column: Column name for sample IDs (optional)
        top_genes: Number of top genes per result
        weight_by_f1: If True, weight each bundle's vote by its
            ensemble F1 mean.  Otherwise, equal weight.

    Returns:
        MultiBundleSummary with per-sample consensus results

    Example:
        >>> b1 = load_bundle("bundle_GDS2545.gsm.zip")
        >>> b2 = load_bundle("bundle_GDS3257.gsm.zip")
        >>> summary = multi_infer([b1, b2], patients, logger=logger)
        >>> for r in summary.results:
        ...     print(f"{r.sample_id}: {r.predicted_class} "
        ...           f"({r.n_bundles_positive}/{r.n_bundles_total} bundles positive)")
    """
    if not bundles:
        raise ValueError("At least one ModelBundle is required.")

    logger.info(
        f"🏥 Multi-bundle inference: {len(bundles)} bundles, "
        f"{len(patient_data)} samples"
    )

    # Run per-bundle inference
    per_bundle_summaries: list[InferenceSummary] = []
    for i, bundle in enumerate(bundles):
        logger.info(
            f"  ▸ Bundle {i + 1}/{len(bundles)}: "
            f"{bundle.metadata.dataset_name} "
            f"({bundle.metadata.n_features} features)"
        )
        summary = infer(
            bundle, patient_data,
            logger=logger,
            sample_id_column=sample_id_column,
            top_genes=top_genes,
        )
        per_bundle_summaries.append(summary)

    # Determine sample IDs from the first bundle's results
    sample_ids = [r.sample_id for r in per_bundle_summaries[0].results]
    n_samples = len(sample_ids)

    # Compute bundle weights
    if weight_by_f1:
        weights = np.array([
            b.metadata.ensemble_f1_mean for b in bundles
        ])
        # Avoid zero weights
        weights = np.maximum(weights, 0.01)
        weights = weights / weights.sum()
    else:
        weights = np.ones(len(bundles)) / len(bundles)

    # Aggregate predictions per sample
    multi_results: list[MultiBundleResult] = []
    for sample_idx in range(n_samples):
        sid = sample_ids[sample_idx]
        bundle_preds: dict[str, InferenceResult] = {}
        weighted_prob_sum = 0.0
        importances: list[dict[str, float]] = []

        for bundle_idx, summary in enumerate(per_bundle_summaries):
            result = summary.results[sample_idx]
            bid = summary.bundle_id
            bundle_preds[bid] = result

            # Weighted probability (use mean of individual model probs)
            mean_prob = float(np.mean(result.individual_probabilities))
            weighted_prob_sum += weights[bundle_idx] * mean_prob

            if result.top_contributing_genes:
                importances.append(result.top_contributing_genes)

        # Consensus prediction
        predicted_positive = weighted_prob_sum >= 0.5
        consensus_confidence = round(
            abs(weighted_prob_sum - 0.5) * 2, 4
        )

        n_positive_bundles = sum(
            1 for r in bundle_preds.values()
            if r.predicted_class == "positive"
        )
        n_total = len(bundles)
        agreement = (
            n_positive_bundles / n_total if predicted_positive
            else (n_total - n_positive_bundles) / n_total
        )

        predicted_class = "positive" if predicted_positive else "negative"
        risk_level = _classify_risk(consensus_confidence, predicted_positive)
        merged_genes = _merge_gene_importances(importances, top_genes)

        multi_results.append(MultiBundleResult(
            sample_id=sid,
            predicted_class=predicted_class,
            consensus_confidence=consensus_confidence,
            risk_level=risk_level,
            bundle_predictions=bundle_preds,
            n_bundles_positive=n_positive_bundles,
            n_bundles_total=n_total,
            agreement_ratio=round(agreement, 4),
            top_contributing_genes=merged_genes,
        ))

    n_pos = sum(1 for r in multi_results if r.predicted_class == "positive")
    n_neg = len(multi_results) - n_pos
    mean_conf = float(np.mean(
        [r.consensus_confidence for r in multi_results]
    )) if multi_results else 0.0

    logger.info(
        f"✅ Multi-bundle inference complete: "
        f"{n_pos} positive, {n_neg} negative across {len(bundles)} bundles "
        f"(mean confidence: {mean_conf:.2%})"
    )

    return MultiBundleSummary(
        n_samples=len(multi_results),
        n_positive=n_pos,
        n_negative=n_neg,
        mean_confidence=round(mean_conf, 4),
        results=multi_results,
        bundle_ids=[b.metadata.bundle_id for b in bundles],
        n_bundles=len(bundles),
    )
