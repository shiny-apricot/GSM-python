# Persistent AI Memory

This file stores specific user preferences and demands to ensure AI agents act consistently across all conversations.

## Preferences
- **Highlighting Document Changes**: Whenever an AI agent modifies a `.docx` document (or similar format supporting highlights), the agent must explicitly highlight the changed text (e.g., using yellow background highlight) so the user can easily spot, verify, and later remove the highlight before submission.
- **Honest Codebase Representation**: Always ensure that manuscript text accurately reflects the actual codebase (`STATUS.md`), removing any false or "overfitting" statements designed to please reviewers if they contradict the true implementation.
- **Versioning**: Whenever modifying a `.docx` file, do not overwrite the original file. Instead, save the modified file as a new version by incrementing the version number in the filename (e.g., `G-S-M_REVIEW5.docx` -> `G-S-M_REVIEW6.docx`).
- **Consolidated Stakeholder/Reviewer Feedback**: Always consult `REVIEWER_MAP.md` before generating manuscript drafts or response letters. It is the definitive source for maintaining the required scientific tone, explicitly tracking reviewer concerns, and ensuring our messaging directly answers reviewer objections without evasion.
- **LaTeX Compilation & Cleanup**: Do not expect the user to run external bash scripts to clean up LaTeX auxiliary files (e.g., `.aux`, `.log`, `.nav`). Instead, when compiling or generating LaTeX documents, the AI must proactively compile the file and automatically delete the junk files itself.
