param(
  [string]$Repo = "mySebbe/codex-sync-kit",
  [string]$Ref = "main",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Step($Message) {
  Write-Host "==> $Message"
}

$localRoot = Join-Path $env:LOCALAPPDATA "codex-sync-kit"
$appRoot = Join-Path $localRoot "app"
$venvRoot = Join-Path $localRoot ".venv"
$binRoot = Join-Path $localRoot "bin"
$cmdPath = Join-Path $binRoot "codex-sync.cmd"
$zipUrl = "https://github.com/$Repo/archive/refs/heads/$Ref.zip"
$zipPath = Join-Path $env:TEMP "codex-sync-kit-$Ref.zip"
$extractRoot = Join-Path $env:TEMP "codex-sync-kit-install"

Step "Checking required tools"
foreach ($tool in @("python", "git", "gh", "codex")) {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
    throw "Missing required tool: $tool"
  }
}

if ($DryRun) {
  Step "Dry run only"
  Write-Host "Would download $zipUrl"
  Write-Host "Would install into $localRoot"
  exit 0
}

Step "Downloading source"
Remove-Item -Recurse -Force $extractRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force
$sourceRoot = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1

Step "Installing app"
Remove-Item -Recurse -Force $appRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $localRoot | Out-Null
Copy-Item -Recurse -Force $sourceRoot.FullName $appRoot

Step "Creating Python environment"
python -m venv $venvRoot
$python = Join-Path $venvRoot "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install $appRoot

Step "Creating command shim"
New-Item -ItemType Directory -Force -Path $binRoot | Out-Null
$script = "@echo off`r`n`"$venvRoot\Scripts\codex-sync.exe`" %*`r`n"
Set-Content -Path $cmdPath -Value $script -Encoding ASCII

Step "Installing Codex plugin source"
& $python -m codex_sync_kit plugin install --source (Join-Path $appRoot "plugin\codex-sync-kit")

Step "Registering Codex plugin"
& codex plugin add codex-sync-kit@personal

Write-Host ""
Write-Host "Installed Codex Sync Kit."
Write-Host "Add this to PATH for the current shell:"
Write-Host "  `$env:Path = `"$binRoot;`$env:Path`""
Write-Host "Initialize your private vault:"
Write-Host "  codex-sync init --provider github --owner mySebbe --vault codex-sync-vault"
