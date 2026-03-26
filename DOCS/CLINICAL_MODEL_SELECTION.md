# Clinical Model Selection Guide

## When to use which bundle

1. **Disease-matched bundle first (recommended)**
   - Use a bundle trained on a cohort that matches the patient's disease context.
   - Example: prostate patient -> prostate-trained bundle.

2. **No disease-matched bundle available**
   - Use predictions as **exploratory support only**.
   - Require stronger external validation (pathology, imaging, standard labs).

3. **Multi-bundle consensus**
   - Use as a secondary signal for uncertainty reduction.
   - Include disease-matched bundles in the set whenever possible.
   - Treat low agreement as uncertainty, not disagreement to average away.

## What clinicians should always see in the report

- Training dataset ID (cohort provenance)
- Number of training samples
- Number of expected features
- Confidence score and agreement ratio
- Explicit warning for out-of-domain / non-matched disease usage

## Suggested interpretation thresholds

- **High confidence**: >= 0.80
- **Medium confidence**: 0.55 to 0.79
- **Low confidence**: < 0.55
- **Low consensus warning**: agreement < 0.70

## Practical workflow

1. Select disease-matched bundle.
2. Run inference and inspect confidence + agreement.
3. If no match exists, run multi-bundle consensus and flag as exploratory.
4. Confirm with standard clinical diagnostics before action.
