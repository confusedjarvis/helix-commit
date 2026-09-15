$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Grade([string]$WorkDir) {
    & docker run --rm --network none -e HELIX_REPO=/app -v "${WorkDir}:/app" helix-commit-verifier | Out-Host
    return [int]$LASTEXITCODE
}

function New-Work([string]$Name) {
    $dir = Join-Path $env:TEMP "helix-cand-$Name-$(Get-Random)"
    Copy-Item -Recurse (Join-Path $Root "environment\repo") $dir
    return $dir
}

function Copy-Ref([string]$WorkDir, [string[]]$Files) {
    $src = Join-Path $Root "solution\reference_solution\src\helix_alloc"
    $dst = Join-Path $WorkDir "src\helix_alloc"
    foreach ($file in $Files) {
        Copy-Item (Join-Path $src $file) (Join-Path $dst $file) -Force
    }
}

$results = @()

$nop = New-Work "nop"
$results += [pscustomobject]@{ name = "nop"; exit = (Invoke-Grade $nop) }

$oracle = New-Work "oracle"
Copy-Ref $oracle @("allocation.py", "warehouse.py", "compliance.py", "substitution.py", "weights.py")
$results += [pscustomobject]@{ name = "oracle"; exit = (Invoke-Grade $oracle) }

$fefo = New-Work "fefo"
Copy-Ref $fefo @("allocation.py")
$results += [pscustomobject]@{ name = "fefo_only"; exit = (Invoke-Grade $fefo) }

$qa = New-Work "qa"
Copy-Ref $qa @("warehouse.py")
$results += [pscustomobject]@{ name = "qa_log_only"; exit = (Invoke-Grade $qa) }

$mrl = New-Work "mrl"
Copy-Ref $mrl @("compliance.py")
$results += [pscustomobject]@{ name = "arrival_mrl_only"; exit = (Invoke-Grade $mrl) }

$results | Format-Table -AutoSize
$out = Join-Path $Root "analysis\candidate_results.txt"
$results | ForEach-Object { "$($_.name) exit=$($_.exit)" } | Set-Content $out
Write-Host "Wrote $out"
