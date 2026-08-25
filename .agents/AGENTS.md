# Antigravity AI - Global Rules and Guidelines

> **CRITICAL ARCHITECTURE NOTE**: This file contains NO project state. All ephemeral project state is strictly maintained in `.ai_context/`.

## 0. THE CRITICAL REFLEX (NEVER END A TURN WITHOUT THIS)
**WHENEVER** you modify any code, create a file, or reorganize folders, you are **FORBIDDEN** from ending your turn without doing the following first:
1. Update `CODE_CHANGES.md` with exactly what you did.
2. Update `STATUS.md` and `TASKS.md` if the state changed.
3. Run `python3 scripts/generate_architecture_map.py` to update the map.
**If you have not done these things, DO NOT STOP CALLING TOOLS.**

## 1. The `.ai_context` Knowledge Base
Consult these files before planning or executing:
- **`STATUS.md` & `TASKS.md`**: Project state and upcoming tasks.
- **`IMPLEMENTATION_ROADMAP.md`**: Current active checklist.
- **`PROJECT_MAP.md` & `AST_MAP.md`**: Architecture and code map. (Generated automatically via `generate_architecture_map.py`).
- **`CODE_CHANGES.md`**: Changelog.
- **`EXPERIMENT_RESULTS.md`**: Logs and stats.
- **`AI_MEMORY.md`**: User preferences and strict constraints.
*Workspace Hygiene*: Always migrate completed items from `TASKS.md` to `ARCHIVED_TASKS.md` to save context, and remember that running `generate_architecture_map.py` (Rule 0) is what keeps the LLM's AST map from going stale.

## 2. Deep Reasoning & Cognitive Protocol (The "Opus" Standard)
- **Mandatory Scratchpad (Think Before Acting)**: Before outputting any final code, editing a file, or making an architectural decision, you MUST evaluate the problem inside `<scratchpad> ... </scratchpad>` tags. Think veeery loooong on each aspect of the issue and discuss it in the scratchpad briefly.
- **The Devil's Advocate (Self-Correction)**: Within your scratchpad, ruthlessly critique your own drafted solution. Fix any logical flaws before presenting the final answer.
- **Structured Outputs**: When explaining concepts or proposing architectures, strictly use this framework: 1) Theoretical Basis, 2) Architectural Justification, 3) Step-by-Step Code (with inline comments), 4) Performance/Complexity Analysis.
- **Determinism**: Avoid creative guesses in logic. Rely on mathematically and programmatically proven patterns. Take your time to build the computation tree in your scratchpad.

## 3. Execution & Methodology Protocol
- **Divide and Conquer**: Never solve a complex task blindly. Create an `implementation_plan.md` artifact, get User Approval, execute iteratively, and verify constantly.
- **Anti-Omission**: Verify that EVERY clause of the user prompt is addressed before executing.
- **External Resources**: Ask the user to run academic searches (e.g. Elicit, Consensus) if missing scientific context.
- **Healthy Skepticism**: Challenge user requests if they contradict the codebase state.

## 4. Domain-Specific Architecture & Conventions
- **Lifecycle**: Raw CSV → t-test filter → DisGeNET group projection → per-group CV scoring → aggregated model → rank features → biological validation → `.gsm.zip`.
- **Module Comm**: Workflow calls Domain. Domain does not import Domain. UI calls Workflow.
- **Dev Principles**: Top-down, pure functions, `dataclasses` (no dicts/tuples), type hints, max 20 lines. Rely on `numpy` and `dask`.
- **Validation**: Enrichr + STRING-db + DisGeNET (`output/<run>/biological_validation/`).

## 5. Workflows & Output
- **Background Tasks**: Launch long processes asynchronously via `run_command` (`WaitMsBeforeAsync`). Do NOT poll or sleep. Use `manage_task` only if requested.
- **Formatting**: Use GitHub alerts (`> [!NOTE]`), Mermaid diagrams, and carousels for artifacts.
- **Knowledge Items (KIs)**: Review KI summaries before acting. Generate KIs for recurring patterns.