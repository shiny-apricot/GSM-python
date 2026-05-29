# Git + GitHub Workflow 🔄

GitHub is where we store and share the project.
Git is the tool that records changes.

**Lab analogies:**
- **Project files** = your experiment materials
- **Git commit** = a lab notebook entry ("what I changed and why")
- **Branch** = a separate bench where you can work without disturbing others
- **Pull Request (PR)** = asking the team to review your work before it becomes the official protocol
- **Merge** = your update becomes the new official protocol

---

## 1) One-Time Setup

### Configure Your Name/Email

VS Code will usually prompt you the first time you commit. If it doesn't:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### Authenticate with GitHub

Simplest for beginners: use **HTTPS** (no SSH keys needed). VS Code will help you sign in when you push.

> **Tip:** If you're asked for credentials repeatedly, set up credential caching:
> ```bash
> git config --global credential.helper store
> ```

---

## 2) Get the Project

### VS Code (recommended)

1. Open VS Code in WSL: `Ctrl+Shift+P` → **WSL: New WSL Window**
2. `Ctrl+Shift+P` → **Git: Clone**
3. Paste: `https://github.com/shiny-apricot/GSM-to-python.git`
4. Choose a folder → click **Open**

### Terminal

```bash
cd ~
git clone https://github.com/shiny-apricot/GSM-to-python.git
cd GSM-to-python
```

### Contributing Access

| Situation | What to Do |
|-----------|------------|
| You're a collaborator (can push) | Use the repo directly |
| You're not a collaborator | Fork on GitHub, then clone your fork |

---

## 3) Daily Workflow

> **Rule #1:** Never work directly on `main`. Always create a branch.

### Step 1: Pull Latest Changes

**VS Code:** Source Control → **...** → **Pull**

**Terminal:**
```bash
git checkout main
git pull
```

### Step 2: Create a New Branch

Name it like a short description of your task:

**VS Code:**
1. Click the branch name (bottom-left)
2. Choose **Create new branch...**
3. Name it: `yourname-short-task` (e.g., `yasin-fix-upload`)

**Terminal:**
```bash
git checkout -b yasin-fix-upload
```

### Step 3: Make Your Changes

Edit files in VS Code. Keep changes focused on one task.

### Step 4: Review What Changed

**VS Code:** Open **Source Control** (left sidebar) → click files to see diffs.

**Terminal:**
```bash
git status        # See changed files
git diff           # See what changed
```

### Step 5: Commit (Save to Git History)

> **⚠️ CRITICAL (Git LFS):** This project uses **Git Large File Storage (LFS)** for datasets and models (`*.csv`, `*.txt` in data dirs, `*.zip`, etc.). Before adding a new large file, check that it's tracked in `.gitattributes`. Run `git lfs track "*.csv"` if adding a new format. Always run `git lfs install` on your machine before pushing.

**VS Code:**
1. Source Control → click **+** next to files to stage them
2. Write a commit message (e.g., "Fix upload validation in UI")
3. Click **Commit**

**Terminal:**
```bash
git add -A
git commit -m "Fix upload validation in UI"
```

**Commit message tips:**
- Good: "Fix upload validation in UI", "Add boxplot for group scores"
- Bad: "update", "changes", "stuff"

### Step 6: Push to GitHub

**VS Code:** Source Control → **Sync Changes** or **Push**

**Terminal:**
```bash
git push -u origin yasin-fix-upload
```

### Step 7: Open a Pull Request

1. Go to the GitHub repo in your browser
2. Click the banner: **Compare & pull request**
3. Write what you changed, why, and how to test it
4. Submit the PR

### Step 8: After Merge

Once your PR is merged:

**VS Code:**
1. Switch back to `main` (click branch name)
2. Source Control → **...** → **Pull**

**Terminal:**
```bash
git checkout main
git pull
```

---

## 4) Keeping Your Branch Up-to-Date

If `main` has been updated while you're working on your branch:

**VS Code:**
1. Switch to `main` → Pull
2. Switch back to your branch
3. Source Control → **...** → **Branch** → **Merge Branch...** → select `main`

**Terminal:**
```bash
git checkout main
git pull
git checkout yasin-fix-upload
git merge main
```

### If There Are Merge Conflicts

Conflicts happen when two people edited the same lines. Git will mark the conflicting sections:

```
<<<<<<< HEAD
your version of the code
=======
their version of the code
>>>>>>> main
```

**To resolve:**
1. Open the conflicting file
2. Choose which version to keep (or combine them)
3. Remove the `<<<`, `===`, `>>>` markers
4. Save, stage, and commit

VS Code has a built-in merge editor that makes this easier — look for the "Resolve in Merge Editor" button.

---

## 5) Emergency Undo

### Discard Local Edits (Not Committed)

**VS Code:** Right-click file in Source Control → **Discard Changes**

**Terminal:**
```bash
git restore .          # Discard all uncommitted changes
git restore file.py    # Discard changes in one file
```

### Undo Last Commit (Keep Changes)

```bash
git reset --soft HEAD~1
```

### Undo Last Commit (Discard Changes)

```bash
git reset --hard HEAD~1
# Warning: This permanently deletes the changes!
```

---

## 6) Branch Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature-description` | `feature-new-plot` |
| Bug fix | `fix-description` | `fix-upload-crash` |
| Personal | `yourname-task` | `yasin-refactor-scoring` |

One branch = one task. Keep branches short-lived.

---

## 7) Common Git Mistakes and Fixes

| Mistake | Fix |
|---------|-----|
| Committed to `main` by accident | `git reset --soft HEAD~1`, create branch, re-commit |
| Pushed sensitive data | Contact a maintainer immediately |
| Wrong commit message | `git commit --amend -m "new message"` (only if not pushed) |
| Need to update from main | `git merge main` (from your branch) |
| Conflicts scare me | They're safe — Git is asking you to choose. See Section 4 |

---

## Quick Reference Card

```
git checkout main && git pull          # Get latest
git checkout -b my-branch              # Create branch
# ... make changes ...
git add -A && git commit -m "message"  # Save
git push -u origin my-branch           # Upload
# Open PR on GitHub → get review → merge
git checkout main && git pull          # Get merged result
```
