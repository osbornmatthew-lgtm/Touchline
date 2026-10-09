# Touchline home runner: one-go setup on Windows.
# Open PowerShell as administrator and paste:
#   Set-ExecutionPolicy Bypass -Scope Process -Force; iwr -UseBasicParsing https://raw.githubusercontent.com/osbornmatthew-lgtm/Touchline/main/runner/windows/setup.ps1 | iex
# Safe to run again: it skips anything already done.

$ErrorActionPreference = 'Stop'
$Repo = 'C:\Touchline'
$Key = "$HOME\.ssh\touchline_deploy"
function Step($n, $t) { Write-Host ''; Write-Host "[$n/7] $t" -ForegroundColor Cyan }
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE). Send this window to Claude." } }
function RefreshPath { $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') }

Step 1 'Keep the machine awake on mains power'
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

Step 2 'Git and Python 3.12'
RefreshPath
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements; RefreshPath
}
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3.12 -V; if ($LASTEXITCODE -eq 0) { $py = 'ok' } }
if (-not $py) {
  winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements; RefreshPath
}
& py -3.12 -V; Check 'Python 3.12'
git --version; Check 'Git'

Step 3 'A key that can only push to the Touchline repo'
New-Item -ItemType Directory -Force "$HOME\.ssh" | Out-Null
if (-not (Test-Path $Key)) {
  cmd /c "ssh-keygen -q -t ed25519 -f `"$Key`" -N `"`" -C touchline-runner"; Check 'ssh-keygen'
}
$pub = (Get-Content "$Key.pub" -Raw).Trim()
$pub | Set-Clipboard
Write-Host ''
Write-Host 'This key is now on your clipboard:' -ForegroundColor Yellow
Write-Host $pub
Write-Host ''
Write-Host 'Add it on GitHub: Touchline repo > Settings > Deploy keys > Add deploy key.'
Write-Host 'Title "Home runner", paste the key, tick "Allow write access", Add key.'
Write-Host '(Or tell Claude "add the deploy key" and paste the key line above into the chat.)'
Read-Host 'Press Enter once the key is added'

Step 4 'Get the code'
$ssh = 'ssh -i ' + ($Key -replace '\\', '/') + ' -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new'
if (-not (Test-Path "$Repo\.git")) {
  git -c core.sshCommand="$ssh" clone git@github.com:osbornmatthew-lgtm/Touchline.git $Repo; Check 'git clone'
}
Set-Location $Repo
git config core.sshCommand "$ssh"
git config user.name 'Touchline runner'
git config user.email 'touchline-runner@users.noreply.github.com'
git pull -q; Check 'git pull (is the deploy key added with write access?)'

Step 5 'Python packages and the headless browser'
if (-not (Test-Path "$Repo\.venv\Scripts\python.exe")) { & py -3.12 -m venv .venv; Check 'venv' }
& .venv\Scripts\python -m pip install -q --upgrade pip
& .venv\Scripts\pip install -q -r runner\requirements.txt; Check 'pip install'
& .venv\Scripts\python -m playwright install chromium; Check 'playwright install'

Step 6 'Test against Full-Time'
& .venv\Scripts\python runner\touchline.py probe
& .venv\Scripts\python runner\touchline.py check; Check 'config check'
& .venv\Scripts\python runner\touchline.py run --mode full --dry-run; Check 'dry run'
Write-Host ''
$go = Read-Host 'Dry run done. Publish a real update and switch on the schedule? (y/n)'
if ($go -ne 'y') { Write-Host 'Stopped before going live. Run this again when ready.'; return }
& .venv\Scripts\python runner\touchline.py run --mode full --force; Check 'first live run'

Step 7 'Schedule: Sundays every 10 minutes 10:00 to 18:00, Saturday 08:50, Monday 07:50'
& powershell -ExecutionPolicy Bypass -File runner\windows\install-tasks.ps1; Check 'scheduling'
Write-Host ''
Write-Host 'All done. Logs are in C:\Touchline\.runner\logs. Tell Claude "runner is live" so the old Claude tasks get switched off.' -ForegroundColor Green
