# GitHub Copilot Pro Guide (Simple + Practical)

GitHub Copilot is an AI assistant for coding.

Analogy: it’s like **autocorrect + a helpful lab colleague** who can draft code, suggest next lines, and explain errors.

Important reality check:
- Copilot can be very helpful, but it can also be wrong.
- Treat its suggestions like a *draft protocol* that you still must review.

---

## 1) What you need

- A GitHub account
- GitHub Copilot Pro subscription (or access via your organization if your lab provides it)
- VS Code installed

---

## 2) Subscribe to Copilot Pro

1. Log into GitHub
2. Go to GitHub Copilot settings / billing
3. Subscribe to **Copilot Pro**

Note: If you are a student or an instructor, you may have a free option available through GitHub Education — see the "Getting GitHub Copilot Free (Students & Instructors)" section below before purchasing. GitHub also occasionally offers free trials.

(Exact pages can change over time; the easiest is to search “GitHub Copilot Pro subscribe”.)

Screenshot placeholder (optional):
- `![Copilot subscription page](images/copilot-subscribe.png)`

---

## 3) Install Copilot in VS Code

In VS Code:
1. Open Extensions
2. Search: **GitHub Copilot**
3. Install it
4. Also install: **GitHub Copilot Chat** (if it is not included)

Then:
- Sign in to GitHub when VS Code asks

Tip: You can confirm you’re signed in by clicking the Accounts icon (bottom-left) in VS Code.

Screenshot placeholder (optional):
- `![VS Code Copilot extension install](images/vscode-copilot-install.png)`

---

## 4) How to use Copilot (3 common ways)

### A) Inline suggestions while you type

- Start writing a function
- Copilot will suggest the rest
- Press **Tab** to accept (or keep typing to ignore)

### B) Copilot Chat: ask questions about code

Where to find it:
- In the left sidebar, open the **Chat** view (or a Copilot icon, depending on VS Code version)
- Or use the Command Palette: `Ctrl+Shift+P` → search “Copilot Chat”

Examples:
- “Explain what this function does in simple words.”
- “Why am I getting this error? Here is the traceback.”
- “Suggest a minimal fix without changing behavior.”

### C) Ask Copilot to draft code changes

Examples:
- “Add input validation to the Streamlit upload step.”
- “Refactor this to be more readable for beginners.”

---

## 5) Good prompting (simple patterns that work)

Think of prompting like giving a clear experimental protocol request.

### Pattern 1: Goal + constraints

“Goal: add a new parameter to the UI.
Constraints: keep it beginner-friendly; do not add new pages; update docs.”

### Pattern 2: Provide an example input/output

“Input: a CSV with columns A,B,label.
Output: a cleaned DataFrame with missing values removed.
Please write a function with type hints.”

### Pattern 3: Ask for a checklist

“Give me a checklist to debug why Streamlit won’t start in WSL.”

---

## 6) Copilot safety + privacy for research

- Avoid pasting sensitive patient data or private datasets into AI chats.
- If you must share data-like content, consider anonymizing it first.
- Review generated code carefully before running it.

---

## 7) Using Copilot with this repo (recommended)

Useful prompts specific to this project:
- “Where is the main workflow entry point, and how does data flow through the stages?”
- “Help me add a small docstring and type hints to this function.”
- “I want to change the output folder naming; where should I do it?”

When Copilot suggests big changes, ask it to do *smaller steps*:
- “Make the smallest change that fixes the bug.”
- “Do not refactor unrelated files.”

### Practical VS Code workflow (recommended)

1. Open the file you want to change
2. Select a small block of code
3. Ask Copilot Chat: “Explain this in simple words”
4. Then ask: “Suggest a minimal improvement”
5. Apply the change and run the UI/workflow to confirm it still works

---

## 8) If Copilot suggestions are confusing

Try:
- “Explain your suggestion step-by-step like I’m new to Python.”
- “Show a minimal example.”
- “What are the risks of this change?”

## Getting GitHub Copilot Free (Students & Instructors)

GitHub often provides free or sponsored Copilot access to verified students and educators through GitHub Education or institutional programs. The exact program names and verification steps can change, so always check the official GitHub Education pages first. Below are the typical steps and practical tips.

A. Students (typical path)

1. Verify eligibility:
	- You usually must be a currently enrolled student at an accredited educational institution.
	- Common evidence: school-issued email address (e.g., name@university.edu), student ID card, enrollment letter, or transcript.

2. Apply for the GitHub Student Developer Pack / Education benefits:
	- Sign into GitHub (create an account if you don't have one).
	- Visit the GitHub Education or Student Developer Pack page and click the "Get benefits" or "Apply" button.
	- Fill out the form and upload verification (school email confirmation or scanned student ID). Follow any instructions shown on the application form.

3. Wait for approval:
	- Approval time varies (hours → a few days). Check the email tied to your GitHub account and the application status page.

4. Activate Copilot (if included):
	- Once verified, the Student Pack may include free access to Copilot. Visit https://copilot.github.com or your GitHub settings -> "GitHub Copilot" and follow prompts to enable it under your account.
	- Install the GitHub Copilot extension in VS Code and sign in with the same GitHub account.

B. Instructors / Teaching Staff (typical path)

1. Verify instructor status:
	- Eligibility may require proof of employment or instructor status at an educational institution (school email, employment letter, web page listing, etc.).

2. Apply via GitHub Education (Teacher / Instructor verification):
	- Sign into GitHub and go to the GitHub Education or teacher-specific application page.
	- Provide the requested documentation and any course links (GitHub Classroom, syllabus) that help verify your role.

3. Institutional plans and site licenses:
	- Some universities and departments arrange site or enterprise licenses for Copilot. Check with your IT or academic computing group — they may already have a campus-wide arrangement and can provision accounts.

4. Enable Copilot for your account:
	- After verification, enable Copilot via https://copilot.github.com or GitHub settings and install the VS Code extension.

C. Practical tips & troubleshooting

- Use a school email address if possible — it speeds up and simplifies verification.
- If you must upload documents (ID, enrollment letter), redact any unnecessary personal data but keep the verification details visible.
- Check spam/junk folders for verification emails and monitor the GitHub Education application page for status updates.
- If approval is delayed or denied, contact GitHub Education support (there is usually a help link on the application page) and provide the requested clarifications.
- For institutional provisioning, ask your department IT or teaching support to check for existing GitHub Campus/Enterprise programs.

D. Notes and caveats

- Programs and eligibility change over time — always consult the official GitHub Education pages for the latest instructions and program names.
- Free access is typically tied to your GitHub account and will expire if your verified student/teacher status changes. Keep documentation up to date if you need extended access.

If you want, I can insert direct official link placeholders into this doc (or set the exact URLs currently used by GitHub Education). Want me to add those links now?
