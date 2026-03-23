# cer.ps1 -- Clean Extractor Results
# Place in project root. Run with:
#   powershell -ExecutionPolicy Bypass -File .\cer.ps1 [mode]
#
# Modes:
#   (default)  -- reset state only, keep .md files (most common after quota reset)
#   full       -- delete state + all generated .md files
#   viewer     -- delete synced viewer/public/pages files
#   all        -- delete everything (state + pages + viewer sync)
#
# This script does NOT create upstream exports.
# To contribute infrastructure improvements back to upstream:
#   1. git checkout -b feat/your-improvement
#   2. git add extractor/ viewer/ README.md  (infrastructure only, no book content)
#   3. git commit -m "feat: describe improvement"
#   4. git push origin feat/your-improvement
#   5. Open PR on GitHub: your-fork:feat/... -> upstream:main

param(
    [string]$Mode = "default"
)

$ErrorActionPreference = "Stop"

function ok($msg)   { Write-Host "  [OK]  $msg" -ForegroundColor Green }
function warn($msg) { Write-Host "  [!]   $msg" -ForegroundColor Yellow }
function info($msg) { Write-Host "  -->   $msg" -ForegroundColor Cyan }
function head($msg) { Write-Host $msg -ForegroundColor DarkCyan }

head ""
head "============================================================"
head "  CER -- Clean Extractor Results  |  Mode: $Mode"
head "============================================================"
Write-Host ""

# ============================================================
# STATE RESET (runs in all modes)
# ============================================================
$stateFile = "output\.extraction_state.json"
$stateTmp  = "output\.extraction_state.tmp"

if (Test-Path $stateFile) {
    Remove-Item $stateFile -Force
    ok "Deleted state file: $stateFile"
} else {
    warn "State file not found (already clean): $stateFile"
}
if (Test-Path $stateTmp) {
    Remove-Item $stateTmp -Force
    ok "Deleted temp state: $stateTmp"
}

# ============================================================
# FULL -- delete generated .md pages and output artifacts
# ============================================================
if ($Mode -in @("full", "all")) {
    $pagesDir = "output\pages"
    if (Test-Path $pagesDir) {
        $count = (Get-ChildItem "$pagesDir\*.md" -ErrorAction SilentlyContinue).Count
        Remove-Item "$pagesDir\*.md" -Force -ErrorAction SilentlyContinue
        ok "Deleted $count .md files from $pagesDir"
    } else {
        warn "Pages dir not found: $pagesDir"
    }
    foreach ($f in @("output\index.json", "output\theme.json", "output\cover.png")) {
        if (Test-Path $f) { Remove-Item $f -Force; ok "Deleted: $f" }
    }
}

# ============================================================
# VIEWER -- delete synced viewer/public files
# ============================================================
if ($Mode -in @("viewer", "all")) {
    $viewerPages = "viewer\public\pages"
    if (Test-Path $viewerPages) {
        $count = (Get-ChildItem "$viewerPages\*.md" -ErrorAction SilentlyContinue).Count
        Remove-Item "$viewerPages\*.md" -Force -ErrorAction SilentlyContinue
        ok "Deleted $count .md files from $viewerPages"
    }
    foreach ($f in @("viewer\public\index.json","viewer\public\theme.json","viewer\public\cover.png")) {
        if (Test-Path $f) { Remove-Item $f -Force; ok "Deleted: $f" }
    }
}

# ============================================================
# DONE
# ============================================================
Write-Host ""
info "Done. Run the extractor:"
Write-Host "  python extractor/extractor.py" -ForegroundColor White
Write-Host ""
