# Contributing to GSM Pipeline 🤝

Thank you for your interest in contributing! This document explains how to report bugs, suggest features, and submit code changes.

---

## Quick Links

- [Development Guide](DOCS/developer/DEVELOPMENT.md) — Project structure, testing, coding standards
- [GitHub Workflow](DOCS/developer/GITHUB_WORKFLOW.md) — Branching, committing, Pull Requests
- [Troubleshooting](DOCS/TROUBLESHOOTING.md) — Common issues and fixes

---

## How to Contribute

### 1. Report Bugs 🐛

Open a GitHub issue with:
- A clear title describing the bug
- Steps to reproduce the problem
- The exact error message (copy-paste, not screenshot)
- Your environment (Python version, OS, WSL or native Linux)

### 2. Suggest Features 💡

Open an issue to discuss new features **before** implementing them. Include:
- What the feature would do
- Why it would be useful
- Any design ideas

### 3. Submit Code Changes

1. **Fork** the repo (or create a branch if you have collaborator access)
2. Create a **feature branch** (`git checkout -b feature-my-change`)
3. Make your changes following the [coding standards](DOCS/developer/DEVELOPMENT.md#6-coding-standards)
4. Run **tests** to ensure nothing is broken: `pytest`
5. **Commit** with a clear message
6. Submit a **Pull Request** (PR)

---

## Pull Request Checklist

Before submitting your PR, verify:

- [ ] Code follows the project's coding standards (type hints, docstrings, dataclasses)
- [ ] All existing tests pass (`pytest`)
- [ ] New tests added for new functionality
- [ ] Functions are ≤ 20 lines with ≤ 2 levels of nesting
- [ ] No dictionaries/tuples used for structured data (use dataclasses)
- [ ] Documentation updated if you changed how something works
- [ ] PR description explains what, why, and how to test

---

## Review Process

1. A maintainer will review your PR within a few days.
2. They may request changes — this is normal and constructive.
3. Once approved, your code will be merged into `main`.
4. Your contribution will be part of the project!

---

## Code of Conduct

- Be respectful and professional in all interactions
- Give constructive feedback
- Focus on the code, not the person
- Ask for help if you're stuck — that's what the team is for
