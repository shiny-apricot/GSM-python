---
name: run_experiment
description: A custom AI skill to standardize how experiments are run and logged in this repository.
---

# Run Experiment Skill

When the user asks you to "run the pipeline", "run experiments", or similar tasks involving running scripts in `scripts/experiments/` or `src/workflows/`, you MUST use this skill.

## Procedure
1. Verify that you have activated the virtual environment (`source venv/bin/activate`).
2. Run the specified Python script (e.g. `python scripts/experiments/run_baselines.py`).
3. If the run will take a significant amount of time (e.g. Monte Carlo loops on all 7 datasets), notify the user and use the terminal's background capability or propose using the `/goal` command.
4. Once the experiment finishes, you MUST append a summary of the run to `.ai_context/EXPERIMENT_RESULTS.md`.
5. The summary must include:
   - Date and time of run
   - Script name
   - Command used
   - Short summary of outcome/metrics
   - Path to the generated output directory (e.g. `output/gsm_2026_07_04...`)
6. If the run fails, log the exact error in `.ai_context/EXPERIMENT_RESULTS.md` with the label `[FAILED]`.
