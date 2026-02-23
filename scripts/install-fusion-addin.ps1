# Install the LegoMCP Fusion 360 add-in (Windows)
# Usage: .\scripts\install-fusion-addin.ps1 [-Mode symlink|copy]
#
# Symlink mode (default) requires either:
#   - Developer Mode enabled (Settings > Update & Security > For developers), OR
#   - Running PowerShell as Administrator

param(
    [ValidateSet("symlink", "copy")]
    [string]$Mode = "symlink"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
$AddinSrc = Join-Path $RepoRoot "fusion360-addin\LegoMCP"

if (-not (Test-Path $AddinSrc)) {
    Write-Error "Add-in source not found at $AddinSrc"
    exit 1
}

$AddinsDir = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\AddIns"
$AddinDest = Join-Path $AddinsDir "LegoMCP"

Write-Host "Source:  $AddinSrc"
Write-Host "Target:  $AddinDest"
Write-Host "Mode:    $Mode"
Write-Host ""

if (-not (Test-Path $AddinsDir)) {
    New-Item -ItemType Directory -Path $AddinsDir -Force | Out-Null
}

# Remove existing (symlink or directory)
if (Test-Path $AddinDest) {
    $item = Get-Item $AddinDest -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        # It's a symlink — remove the junction/symlink
        cmd /c rmdir "$AddinDest"
    } else {
        Remove-Item -Recurse -Force $AddinDest
    }
}

if ($Mode -eq "symlink") {
    try {
        New-Item -ItemType SymbolicLink -Path $AddinDest -Target $AddinSrc | Out-Null
        Write-Host "Symlink created." -ForegroundColor Green
        Write-Host "Changes to fusion360-addin\LegoMCP\ are reflected automatically after Fusion restart."
    } catch {
        Write-Host "Symlink failed. Trying directory junction instead..." -ForegroundColor Yellow
        cmd /c mklink /J "$AddinDest" "$AddinSrc"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Junction created." -ForegroundColor Green
            Write-Host "Changes to fusion360-addin\LegoMCP\ are reflected automatically after Fusion restart."
        } else {
            Write-Host "Junction also failed. Falling back to copy mode..." -ForegroundColor Yellow
            Copy-Item -Recurse -Force $AddinSrc $AddinDest
            Write-Host "Files copied. Re-run this script after git pull to update." -ForegroundColor Yellow
        }
    }
} else {
    Copy-Item -Recurse -Force $AddinSrc $AddinDest
    Write-Host "Files copied." -ForegroundColor Green
    Write-Host "Note: Re-run this script after git pull to update."
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open Fusion 360"
Write-Host "  2. Go to Tools > Add-Ins (Shift+S)"
Write-Host "  3. Find LegoMCP and click Run"
Write-Host "  4. Verify: curl http://127.0.0.1:8767/health"
