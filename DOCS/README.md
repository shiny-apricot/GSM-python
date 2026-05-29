# DOCS — Guides for Lab Members 🧬

These guides are written for lab members who are **not** computer scientists.
Think of them like a "lab protocol" for running and contributing to this codebase.

---

## Start Here

| Step | Guide | What You'll Learn |
|------|-------|-------------------|
| 1 | **[Installation Guide](INSTALLATION.md)** | Set up WSL2/Linux/macOS, Python, VS Code, and clone the project |
| 2 | **[Run the Pipeline](RUNNING.md)** | Quick test, full runs, batch runs, Streamlit UI |
| 3 | **[Common Problems](TROUBLESHOOTING.md)** | Fixes for the most frequent errors |

## If You Want to Contribute or Modify Code

| Step | Guide | What You'll Learn |
|------|-------|-------------------|
| 4 | **[Development Basics](developer/DEVELOPMENT.md)** | Project structure, testing, coding habits |
| 5 | **[Git + GitHub Workflow](developer/GITHUB_WORKFLOW.md)** | Branching, committing, Pull Requests |
| 6 | **[GitHub Copilot (AI Assistant)](developer/COPILOT.md)** | Installing and using Copilot for coding |

## Reference

| Document | Description |
|----------|-------------|
| **[Project Map](../PROJECT_MAP.md)** | Every file, folder, and key function |
| **[Ranking Methods](methods/RANKING_EXPLANATION.md)** | Understand how aggregated group ranking works |
| **[Feature Methods](methods/FEATURE_METHODS.md)** | Understand the two methods for feature ranking |
| **[Dataset Exclusions](methods/DATASET_EXCLUSIONS.md)** | Why GDS3268 and GDS4206 were dropped |
| **[Contributing](../CONTRIBUTING.md)** | How to report bugs, suggest features, submit PRs |

## Advanced Topics

| Document | Description |
|----------|-------------|
| **[Web Deployment](advanced/WEB_DEPLOYMENT.md)** | Running the UI as a web app or Docker container |
| **[Clinical Model Selection](advanced/CLINICAL_MODEL_SELECTION.md)** | Choosing the model for production inference |
| **[Google Docs Review](../reports_ARCHIVE/manuscript/review/GOOGLE_DOCS_REVIEW_BRIDGE_GUIDE.md)** | How to bridge tracked changes into Markdown for the AI |

---

## Adding Screenshots

If screenshots are needed, add them under `DOCS/images/` and reference them like:

```markdown
![Screenshot: VS Code WSL](images/vscode-wsl.png)
```

For now, the guides are usable without screenshots.
