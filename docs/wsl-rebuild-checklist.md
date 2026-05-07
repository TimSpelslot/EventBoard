# WSL Rebuild Checklist

This checklist is for rebuilding this repository on a fresh Ubuntu WSL instance without carrying over old local state.

## Before removing the current WSL distro

1. Review local code changes and either commit them or save a patch.
2. Push the branch you want to keep to GitHub.
3. Back up local files that must not be pushed.
4. Export a short list of tools and settings you want to recreate.
5. Remove the old distro only after you can restore the repo and secrets from outside WSL.

### Commit and push the repo state

From the repository root:

```bash
git status
git add -A
git commit -m "WIP before WSL rebuild"
git push origin HEAD
```

If you do not want to commit unfinished work, save a patch instead:

```bash
git diff > ../eventboard-before-wsl-rebuild.patch
git status --short > ../eventboard-before-wsl-rebuild.status.txt
```

This repository already has a GitHub remote configured:

```bash
git remote -v
```

Expected remote:

```text
origin  https://github.com/TimSpelslot/Eventboard.git
```

### Files to back up outside Git

Back up these files to your Windows SSD, OneDrive, or a password manager / encrypted archive:

- `backend/app/config/config.local.json`
- `backend/app/config/config.json`
- `backend/app/config/serviceAccountKey.json` if you created it locally
- `frontend/.env`
- Any `.env`, `.json`, `.pem`, or local key file you created outside source control
- Any database dump you still need

Suggested backup directory on Windows:

```text
D:\Backups\eventboard-wsl-rebuild\
```

Example backup commands from WSL:

```bash
mkdir -p /mnt/d/Backups/eventboard-wsl-rebuild
cp backend/app/config/config.local.json /mnt/d/Backups/eventboard-wsl-rebuild/ 2>/dev/null || true
cp backend/app/config/config.json /mnt/d/Backups/eventboard-wsl-rebuild/ 2>/dev/null || true
cp backend/app/config/serviceAccountKey.json /mnt/d/Backups/eventboard-wsl-rebuild/ 2>/dev/null || true
cp frontend/.env /mnt/d/Backups/eventboard-wsl-rebuild/ 2>/dev/null || true
```

### Secrets and credentials

The current workspace contains local config files with real credentials. If any of those values were ever committed, copied into chat, or synced somewhere unsafe, rotate them.

Checklist:

1. Rotate Google OAuth client secret if needed.
2. Rotate database passwords if needed.
3. Rotate Firebase service account key if needed.
4. Revoke any unused local API keys.

### Optional backup items

These are useful if you want a faster rebuild, but they are not required:

- VS Code settings and installed extension list
- `.ssh` directory if you use SSH auth for GitHub
- `.gitconfig`
- shell aliases from `.bashrc` or `.zshrc`
- a list of apt packages you care about

Helpful commands:

```bash
code --list-extensions > ../vscode-extensions.txt
git config --global --list > ../gitconfig-export.txt
cp ~/.bashrc ../bashrc.backup
cp ~/.gitconfig ../gitconfig.backup 2>/dev/null || true
```

## Remove and recreate Ubuntu WSL

Run these from PowerShell on Windows, not inside WSL.

1. Verify the distro name.
2. Shut it down.
3. Unregister it.
4. Install a fresh Ubuntu distro.
5. Put the new distro on the SSD location you want.

### Check installed distros

```powershell
wsl --list --verbose
```

### Shut down WSL

```powershell
wsl --shutdown
```

### Remove the old Ubuntu distro

Replace `Ubuntu` with the exact distro name from `wsl --list --verbose`.

```powershell
wsl --unregister Ubuntu
```

### Reinstall on SSD

If you want full control over the install location, the most reliable method is:

1. Install Ubuntu once from the Store or with `wsl --install -d Ubuntu`.
2. Export it.
3. Re-import it to the SSD path you want.

Example:

```powershell
wsl --install -d Ubuntu
wsl --shutdown
wsl --export Ubuntu D:\WSL\ubuntu-clean.tar
wsl --unregister Ubuntu
wsl --import Ubuntu D:\WSL\Ubuntu D:\WSL\ubuntu-clean.tar --version 2
```

Then start it:

```powershell
wsl -d Ubuntu
```

## First-time setup in the new WSL

Inside the fresh Ubuntu shell:

1. Create your Linux user if prompted.
2. Update packages.
3. Install Git.
4. Restore SSH keys or sign into GitHub CLI if you use it.
5. Clone the repository to the new home directory.

Example:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git
git clone https://github.com/TimSpelslot/Eventboard.git
cd Eventboard
```

## Rebuild this repo

From the repository root, run the bootstrap script:

```bash
bash scripts/bootstrap-wsl-dev.sh
```

What it does:

- installs base apt packages needed for Python, Node, and native builds
- installs `uv` if missing
- installs Node.js 20 through `nvm` if needed
- creates the backend virtual environment and installs Python deps
- installs frontend npm deps
- creates missing config skeletons from the checked-in examples

## Restore local secrets after bootstrap

Copy back only the files you actually still need:

```bash
cp /mnt/d/Backups/eventboard-wsl-rebuild/config.local.json backend/app/config/ 2>/dev/null || true
cp /mnt/d/Backups/eventboard-wsl-rebuild/config.json backend/app/config/ 2>/dev/null || true
cp /mnt/d/Backups/eventboard-wsl-rebuild/serviceAccountKey.json backend/app/config/ 2>/dev/null || true
cp /mnt/d/Backups/eventboard-wsl-rebuild/.env frontend/.env 2>/dev/null || true
```

Then open and verify:

```bash
sed -n '1,80p' backend/app/config/config.local.json
sed -n '1,40p' frontend/.env
```

## Verify the rebuilt environment

Backend:

```bash
cd backend
uv run pytest
uv run python main.py
```

Frontend in another shell:

```bash
cd frontend
npm test
npx quasar dev
```

## Recommended VS Code flow after reinstall

From Windows:

1. Install VS Code.
2. Install the `WSL` extension.
3. Open the distro with `code .` from inside WSL.
4. Reinstall your saved extensions if needed.

## Clean-start rules

To avoid carrying the same problems into the new distro:

1. Do not copy old virtual environments, `node_modules`, or caches.
2. Do not copy the whole old home directory.
3. Restore only source code, secrets, SSH keys, and a few shell settings.
4. Let Python and Node dependencies reinstall from lockfiles and project metadata.