# Installation Guide 🖥️

This project runs best in Linux.

> **Native Linux / macOS users:** Skip to [Step 3](#3-install-basic-tools) — you already have a Linux terminal. On Windows, the easiest way is **WSL2** (Windows Subsystem for Linux).

---

## 0) What You Need

- Internet connection
- At least **4 GB free disk space** for Python packages and datasets
- Admin access on your computer
- (Windows only): Windows 10 (version 2004+, Build 19041+) or Windows 11

---

## 1) Install WSL + Ubuntu (Windows Only)

### Option A (recommended): One Command

1. Open **PowerShell as Administrator** (right-click Start → "Windows Terminal (Admin)" or search "PowerShell" → Run as Admin)
2. Run:

```powershell
wsl --install
```

3. **Restart your computer** when it asks.

After restart, Ubuntu should open automatically. If not, search "Ubuntu" in the Start Menu.

### Option B: If Option A Did Not Work

```powershell
# Enable the required Windows features manually
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Restart your computer, then set WSL 2 as default
wsl --set-default-version 2

# Install Ubuntu
wsl --install -d Ubuntu
```

---

## 2) Open Ubuntu (WSL)

- Open **Start Menu** → search **Ubuntu** → open it.
- The first time, it asks you to create a Linux **username + password**.
  - The password will **not** show when typing — this is normal Linux behavior.
  - Pick something simple you can remember (e.g., `labuser`).

---

## 3) Install Basic Tools

In the Ubuntu/Linux terminal (or macOS Terminal with Homebrew):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git git-lfs python3 python3-venv python3-pip build-essential curl
```

(`sudo` will ask for the password you created for Ubuntu. Mac users should use `brew install git git-lfs python3` instead).

---

## 4) Install VS Code + WSL Extension

### Install VS Code

Download and install from [https://code.visualstudio.com/](https://code.visualstudio.com/).

> **Important:** Install VS Code on **Windows**, not inside WSL.

### Install the WSL Extension

In VS Code:
1. Open Extensions (`Ctrl+Shift+X`)
2. Search: **WSL**
3. Install: **Remote - WSL** (by Microsoft)

This lets VS Code edit and run code *inside* Ubuntu/WSL seamlessly.

### Recommended Extensions

While you're at it, also install:
- **Python** (by Microsoft)
- **GitHub Copilot Chat** — AI-assisted coding and Q&A
- **Rainbow CSV** — color-coded CSV viewing
- **vscode-pdf** — view PDF files directly in VS Code
- **TODO Highlight** — highlight TODOs in code

---

## 5) Clone the Project

### Method A: Terminal (recommended to ensure data downloads correctly)

```bash
cd ~
git lfs install
git clone https://github.com/shiny-apricot/GSM-to-python.git
cd GSM-to-python
git lfs pull    # Download actual data files (not just LFS pointers)
```

### Method B: VS Code

1. In VS Code, press `Ctrl+Shift+P` → **WSL: New WSL Window**
2. Verify `WSL: Ubuntu` appears in the bottom-left corner
3. Press `Ctrl+Shift+P` → **Git: Clone**
4. Paste: `https://github.com/shiny-apricot/GSM-to-python.git`
5. Choose your Linux home folder (`/home/<you>/`)
6. Click **Open** when prompted
7. **Important:** Open the VS Code terminal (`Ctrl+~`) and run `git lfs install && git lfs pull` to download the actual data files.

> **Tip:** (Windows) Avoid cloning into `/mnt/c/...` (Windows filesystem). Keeping the code inside Linux (`/home/<you>/...`) is **significantly faster** for file I/O.

---

## 6) Create a Python Virtual Environment

### Method A: VS Code

1. Press `Ctrl+Shift+P` → **Python: Create Environment**
2. Choose **Venv**
3. Select the default Python 3 interpreter
4. Wait for it to finish

### Method B: Terminal

```bash
cd ~/GSM-to-python
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal prompt.

---

## 7) Install Python Dependencies

In the VS Code terminal (or Ubuntu terminal with venv active):

```bash
pip install --upgrade pip
pip install -r dependencies.txt
```

This installs pandas, numpy, scikit-learn, xgboost, streamlit, and all other requirements.

---

## 8) Verify the Installation

```bash
# Quick test — should complete in ~1-2 minutes
python run_test.py
```

If you see a summary with F1/AUC scores, everything is working!

---

## 9) Open the Project in VS Code (If You Cloned via Terminal)

From the project root:

```bash
code .
```

VS Code should open and show `WSL: Ubuntu` in the bottom-left.

---

## 10) Updating the Project Later

### VS Code Way

1. Open **Source Control** (left sidebar)
2. Click **...** → **Pull**

### Terminal Way

```bash
cd ~/GSM-to-python
source venv/bin/activate
git pull
pip install -r dependencies.txt   # In case dependencies changed
```

---

## 11) Optional: Run the Streamlit UI

```bash
streamlit run src/ui/app.py
```

It will print a URL like `http://localhost:8501`. Open that in your Windows browser.

> **WSL tip:** If the URL doesn't auto-open, manually copy it into Chrome/Edge.

---

---

# WSL Troubleshooting Guide 🔧

This section covers the most common WSL problems people encounter.
For pipeline-specific issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## WSL Installation Issues

### "WSL is not recognized" or "wsl --install" does nothing

**Cause:** Your Windows version is too old or WSL features are not enabled.

**Fix:**
1. Check your Windows version: press `Win+R`, type `winver`. You need **Windows 10 version 2004** (Build 19041) or later.
2. If your version is old, update Windows via Settings → Update & Security → Windows Update.
3. If version is fine but WSL still won't install, enable features manually:

```powershell
# Run in PowerShell as Administrator
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

4. Restart your computer, then run:

```powershell
wsl --set-default-version 2
wsl --install -d Ubuntu
```

---

### "WslRegisterDistribution failed with error: 0x80370102"

**Cause:** Hyper-V / virtualization is not enabled in BIOS.

**Fix:**
1. Restart your computer and enter **BIOS/UEFI** (usually by pressing `F2`, `F10`, `Del`, or `Esc` during boot — depends on your manufacturer).
2. Find **Virtualization Technology** (may be called "Intel VT-x", "AMD-V", "SVM Mode", or "Virtualization") and **enable** it.
3. Save and exit BIOS.
4. Try `wsl --install` again.

> **Lenovo laptops:** Look under Security → Virtualization.
> **HP laptops:** Look under System Configuration → Virtualization Technology.
> **Dell laptops:** Look under Virtualization Support → Virtualization.

---

### "WslRegisterDistribution failed with error: 0x800701bc"

**Cause:** WSL 2 Linux kernel update is missing.

**Fix:**
1. Download the WSL 2 kernel update from: https://aka.ms/wsl2kernel
2. Run the installer.
3. Restart your terminal and try again.

---

### "WslRegisterDistribution failed with error: 0x80370114"

**Cause:** Nested virtualization conflict (common in VMs or with other hypervisors).

**Fix:**
```powershell
# In PowerShell as Admin
bcdedit /set hypervisorlaunchtype auto
# Restart your computer
```

If you use VMware or VirtualBox, they may conflict with Hyper-V. You can either:
- Use WSL 2 (and keep those VMs turned off), or
- Switch VirtualBox/VMware to use Hyper-V backend.

---

### "Error: 0x80004002" or "The Virtual Machine could not be started"

**Cause:** Windows Hypervisor Platform feature is not enabled.

**Fix:**
```powershell
# Run in PowerShell as Administrator
Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -NoRestart
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
# Restart
```

---

### WSL installs but Ubuntu is stuck at "Installing, this may take a few minutes..."

**Fix:**
1. Wait up to 10 minutes — first-time setup can be slow.
2. If still stuck, close the window and try:

```powershell
wsl --shutdown
wsl
```

3. If that fails, unregister and reinstall:

```powershell
wsl --unregister Ubuntu
wsl --install -d Ubuntu
```

---

## WSL Runtime Issues

### "WSL is extremely slow" (file operations, pip install, git)

**Cause:** You're working on files stored in `/mnt/c/` (Windows filesystem), which is very slow from WSL.

**Fix:**
- Always keep your project in the **Linux filesystem**: `/home/<you>/GSM-to-python`
- Never clone or work in `/mnt/c/Users/...` paths
- If you already cloned there, move it:

```bash
cp -r /mnt/c/Users/YourName/GSM-to-python ~/GSM-to-python
cd ~/GSM-to-python
```

> **Performance difference:** Linux filesystem is **5–10x faster** than `/mnt/c/` for file I/O.

---

### "Cannot connect to localhost" / Streamlit URL doesn't open

**Cause:** WSL networking sometimes doesn't forward ports automatically.

**Fixes (try in order):**
1. Copy the exact URL from the terminal (e.g., `http://localhost:8501`) and paste it in your Windows browser.
2. Try `http://127.0.0.1:8501` instead of `localhost`.
3. If neither works, find WSL's IP address:

```bash
hostname -I
# Example output: 172.28.176.1
```

Then open `http://172.28.176.1:8501` in your Windows browser.

4. If using WSL2 on an older Windows build, you may need to add a port proxy:

```powershell
# Run in PowerShell as Admin
netsh interface portproxy add v4tov4 listenport=8501 listenaddress=0.0.0.0 connectport=8501 connectaddress=$(wsl hostname -I)
```

---

### "DNS resolution failed" / `sudo apt update` fails / `pip install` can't download

**Cause:** WSL's DNS resolver can break, especially on corporate/university networks or VPNs.

**Fix:**
```bash
# Create a custom resolv.conf
sudo rm /etc/resolv.conf
sudo bash -c 'echo "nameserver 8.8.8.8" > /etc/resolv.conf'
sudo bash -c 'echo "nameserver 8.8.4.4" >> /etc/resolv.conf'

# Prevent WSL from overwriting it
sudo bash -c 'echo "[network]" > /etc/wsl.conf'
sudo bash -c 'echo "generateResolvConf = false" >> /etc/wsl.conf'
```

Then restart WSL:
```powershell
# In PowerShell
wsl --shutdown
```

---

### WSL "out of memory" or process killed

**Cause:** By default, WSL 2 can use up to 80% of your system RAM, which may not be enough for large datasets.

**Fix:** Create/edit `C:\Users\<YourName>\.wslconfig`:

```ini
[wsl2]
memory=8GB
swap=4GB
processors=4
```

Then restart WSL:
```powershell
wsl --shutdown
```

---

### "Permission denied" when running scripts

**Fix:**
```bash
# Check if the file is executable
ls -la run_test.py

# If not, make it executable
chmod +x run_test.py

# Or just run via python (recommended)
python run_test.py
```

---

### Clock skew / "file has modification time in the future"

**Cause:** WSL's clock can drift out of sync with Windows after sleep/hibernate.

**Fix:**
```bash
sudo hwclock -s
```

Or restart WSL entirely:
```powershell
wsl --shutdown
```

---

### VS Code says "WSL: Cannot connect" or extensions don't load

**Fixes:**
1. Make sure the **Remote - WSL** extension is installed in VS Code (on the Windows side).
2. Restart VS Code completely.
3. Try opening from the Ubuntu terminal:

```bash
cd ~/GSM-to-python
code .
```

4. If still broken, reinstall the VS Code Server inside WSL:

```bash
rm -rf ~/.vscode-server
# Then reopen VS Code — it will reinstall automatically
```

---

### "git: command not found" inside WSL

**Fix:**
```bash
sudo apt update
sudo apt install -y git
```

---

### WSL takes forever to start / hangs on "Starting"

**Fixes:**
1. Close all WSL terminals and PowerShell windows.
2. Force shutdown:

```powershell
wsl --shutdown
```

3. Wait 10 seconds, then reopen Ubuntu.
4. If persistent, check for Windows updates — some builds have WSL bugs.
5. As a last resort, reset WSL:

```powershell
wsl --unregister Ubuntu
wsl --install -d Ubuntu
# Warning: This deletes all data inside that Ubuntu instance!
```

---

## Python & Package Issues in WSL

### "command not found: python"

Ubuntu uses `python3` by default, not `python`.

**Fix:**
```bash
# Option 1: Use python3 everywhere
python3 run_test.py

# Option 2: Create an alias (add to ~/.bashrc)
echo 'alias python=python3' >> ~/.bashrc
source ~/.bashrc
```

---

### `pip install` fails with "error: externally-managed-environment"

**Cause:** Newer Ubuntu versions (23.04+) prevent installing packages globally to protect the system Python.

**Fix:** Always use a virtual environment (which we do):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r dependencies.txt
```

If you need to force a global install (not recommended):

```bash
pip install --break-system-packages <package>
```

---

### `pip install` fails with compiler errors (gcc, g++)

Some packages (like `scipy`, `scikit-learn`) need C/C++ compilers.

**Fix:**
```bash
sudo apt update
sudo apt install -y build-essential python3-dev gfortran libopenblas-dev
pip install -r dependencies.txt
```

---

### "No module named 'tkinter'" or matplotlib backend errors

**Fix:**
```bash
sudo apt install -y python3-tk
```

For headless environments (remote servers), set the matplotlib backend:

```bash
export MPLBACKEND=Agg
# Or add to ~/.bashrc:
echo 'export MPLBACKEND=Agg' >> ~/.bashrc
```

---

## Git LFS Issues

### Data files are tiny (~130 bytes) and contain "version https://git-lfs.github.com/spec/v1"

**Cause:** Git LFS wasn't installed when you cloned.

**Fix:**
```bash
sudo apt install -y git-lfs
git lfs install
git lfs pull
```

---

### `git lfs pull` hangs or times out

**Fix:**
1. Check your internet connection.
2. Try pulling specific files:

```bash
git lfs pull --include="data/expression_data/*.csv"
```

3. If on a corporate network, you may need to configure a proxy:

```bash
git config --global http.proxy http://proxy.company.com:8080
```

---

## VPN and Firewall Issues

### WSL loses network when VPN is connected

This is one of the most common WSL complaints. VPN software (Cisco AnyConnect, GlobalProtect, etc.) often breaks WSL networking.

**Fix 1: Update WSL** (Microsoft has been fixing VPN issues):
```powershell
wsl --update
```

**Fix 2: Configure DNS manually** (see the DNS section above).

**Fix 3: Use WSL mirrored networking** (Windows 11 22H2+):

Edit `C:\Users\<YourName>\.wslconfig`:
```ini
[wsl2]
networkingMode=mirrored
```

Then restart WSL.

**Fix 4: Cisco AnyConnect specific** — add a routing fix:

```powershell
# Run in PowerShell as Admin after VPN connects
Get-NetAdapter | Where-Object {$_.InterfaceDescription -Match "Cisco"} | Set-NetIPInterface -InterfaceMetric 6000
```

---

## Need More Help?

If none of the above fixes your problem:

1. Copy the **exact error message**.
2. Note which **step** you were on.
3. Check if you're inside **WSL** or **Windows** (this matters!).
4. Ask a colleague, or open an issue on GitHub with this info.

Also see:
- [General Troubleshooting](TROUBLESHOOTING.md)
- [Microsoft's official WSL troubleshooting](https://learn.microsoft.com/en-us/windows/wsl/troubleshooting)
