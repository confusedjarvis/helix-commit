# Optional Windows convenience. Primary path is ./tools/validate.sh on Linux.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Prefer ./tools/validate.sh on Linux. This script is a Windows convenience wrapper."
Write-Host "Building agent and verifier images..."
docker build -t helix-commit-agent -f environment/Dockerfile environment
if ($LASTEXITCODE -ne 0) { throw "agent image build failed" }
docker build -t helix-commit-verifier -f tests/verifier/Dockerfile tests/verifier
if ($LASTEXITCODE -ne 0) { throw "verifier image build failed" }

function Invoke-Grade([string]$WorkDir) {
    & docker run --rm --network none -e HELIX_REPO=/app -v "${WorkDir}:/app" helix-commit-verifier | Out-Host
    return [int]$LASTEXITCODE
}

function Install-Reference([string]$WorkDir) {
    $src = Join-Path $Root "solution\reference_solution\src\helix_alloc"
    $dst = Join-Path $WorkDir "src\helix_alloc"
    Get-ChildItem $src -Filter *.py | ForEach-Object {
        Copy-Item $_.FullName -Destination (Join-Path $dst $_.Name) -Force
    }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$base = Join-Path $env:TEMP "helix-commit-$stamp"
$nop = Join-Path $base "nop"
$oracle = Join-Path $base "oracle"
New-Item -ItemType Directory -Path $base | Out-Null
Copy-Item -Recurse (Join-Path $Root "environment\repo") $nop
Copy-Item -Recurse (Join-Path $Root "environment\repo") $oracle
Install-Reference $oracle

$nopCode = Invoke-Grade $nop
$oracleCode = Invoke-Grade $oracle

Write-Host ""
Write-Host "NOP exit=$nopCode (expect != 0)"
Write-Host "ORACLE exit=$oracleCode (expect 0)"
Write-Host "Work trees: $base"

if ($oracleCode -ne 0) { throw "Reference solution failed the verifier" }
if ($nopCode -eq 0) { throw "Starter unexpectedly passed the verifier" }
Write-Host "validate.ps1 convenience PASS. Run ./tools/validate.sh for the full Linux battery."
