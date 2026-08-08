# setup_runner.ps1
# ─────────────────
# One-time setup: registers your Windows machine as a GitHub Actions
# self-hosted runner for amithviswas/linkedin-automation-agent.
#
# Run this ONCE as Administrator:
#   Right-click PowerShell → "Run as Administrator"
#   cd d:\Linkdin
#   .\setup_runner.ps1

param(
    [string]$GitHubToken = ""
)

$repo = "amithviswas/linkedin-automation-agent"
$runnerDir = "C:\actions-runner"
$runnerVersion = "2.321.0"

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  GitHub Actions Self-Hosted Runner Setup" -ForegroundColor Cyan
Write-Host "  Repo: $repo" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

# ── Get registration token ────────────────────────────────────────────────────
if (-not $GitHubToken) {
    Write-Host "Getting runner registration token from GitHub..." -ForegroundColor Yellow
    $tokenJson = gh api -X POST "repos/$repo/actions/runners/registration-token" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not get token. Make sure 'gh' CLI is logged in." -ForegroundColor Red
        Write-Host "Run: gh auth login" -ForegroundColor Yellow
        exit 1
    }
    $regToken = ($tokenJson | ConvertFrom-Json).token
} else {
    $regToken = $GitHubToken
}

Write-Host "✅ Registration token obtained" -ForegroundColor Green

# ── Create runner directory ───────────────────────────────────────────────────
if (-not (Test-Path $runnerDir)) {
    New-Item -ItemType Directory -Path $runnerDir | Out-Null
    Write-Host "✅ Created runner directory: $runnerDir" -ForegroundColor Green
}

# ── Download runner ───────────────────────────────────────────────────────────
$runnerZip = "$runnerDir\actions-runner.zip"
$runnerUrl = "https://github.com/actions/runner/releases/download/v$runnerVersion/actions-runner-win-x64-$runnerVersion.zip"

if (-not (Test-Path "$runnerDir\config.cmd")) {
    Write-Host "Downloading GitHub Actions runner v$runnerVersion..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $runnerUrl -OutFile $runnerZip -UseBasicParsing
    Expand-Archive -Path $runnerZip -DestinationPath $runnerDir -Force
    Remove-Item $runnerZip
    Write-Host "✅ Runner downloaded and extracted" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Runner already downloaded, skipping download" -ForegroundColor Cyan
}

# ── Configure runner ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Configuring runner..." -ForegroundColor Yellow

Set-Location $runnerDir
.\config.cmd `
    --url "https://github.com/$repo" `
    --token $regToken `
    --name "amith-home-pc" `
    --labels "self-hosted,Windows,X64,home-ip" `
    --work "_work" `
    --runasservice `
    --windowslogonaccount "NT AUTHORITY\NETWORK SERVICE" `
    --unattended

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Runner configured and installed as a Windows Service!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The runner will:" -ForegroundColor Cyan
    Write-Host "  • Start automatically when Windows boots" -ForegroundColor White
    Write-Host "  • Run LinkedIn automation from YOUR trusted home IP" -ForegroundColor White
    Write-Host "  • Allow GitHub Actions workflow triggers to work correctly" -ForegroundColor White
    Write-Host ""
    Write-Host "Next step: Update the workflow to use 'runs-on: self-hosted'" -ForegroundColor Yellow
    Write-Host "This is already done — just push and trigger the workflow!" -ForegroundColor Green
} else {
    Write-Host "❌ Runner configuration failed. Check the error above." -ForegroundColor Red
    Write-Host "Try running this script as Administrator." -ForegroundColor Yellow
}

Set-Location "d:\Linkdin"
