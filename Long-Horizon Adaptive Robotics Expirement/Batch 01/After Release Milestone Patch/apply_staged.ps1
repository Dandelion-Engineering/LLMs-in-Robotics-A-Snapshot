param([switch]$Apply)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$milestoneManifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
$milestoneExperiment = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$milestoneExpected = @('Runtime/initial_conditions.py', 'Runtime/test_initial_conditions.py')
$milestoneActual = @($milestoneManifest.files | ForEach-Object { $_.target })
if ((($milestoneActual | Sort-Object) -join '|') -ne (($milestoneExpected | Sort-Object) -join '|')) {
    throw 'Unexpected milestone patch target inventory'
}
$milestoneWrites = @()
foreach ($milestoneFile in $milestoneManifest.files) {
    $milestoneTarget = Join-Path $milestoneExperiment $milestoneFile.target
    $milestoneOriginal = Join-Path $PSScriptRoot $milestoneFile.original_path
    $milestoneProposed = Join-Path $PSScriptRoot $milestoneFile.proposed_path
    if ($milestoneFile.original_path -ne ('original/' + $milestoneFile.target) -or
        $milestoneFile.proposed_path -ne ('proposed/' + $milestoneFile.target)) {
        throw 'Unexpected retained milestone source path'
    }
    if ((Get-FileHash -LiteralPath $milestoneOriginal -Algorithm SHA256).Hash.ToLowerInvariant() -ne $milestoneFile.original_sha256) {
        throw ('Retained original source changed: ' + $milestoneFile.target)
    }
    if ((Get-FileHash -LiteralPath $milestoneProposed -Algorithm SHA256).Hash.ToLowerInvariant() -ne $milestoneFile.proposed_sha256) {
        throw ('Retained proposed source changed: ' + $milestoneFile.target)
    }
    if ((Get-FileHash -LiteralPath $milestoneTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $milestoneFile.original_sha256) {
        throw ('Live Runtime base changed; patch was not applied: ' + $milestoneFile.target)
    }
    $milestoneWrites += [pscustomobject]@{
        target = $milestoneTarget
        bytes = [IO.File]::ReadAllBytes($milestoneProposed)
        expected = $milestoneFile.proposed_sha256
    }
}
if (-not $Apply) {
    Write-Output 'Both live bases and retained candidate files match; validation only, no Runtime writes.'
    return
}
# Root must run only after the active source hold ends. Verify every base before
# the first write, then install exactly the reviewed retained bytes.
foreach ($milestoneWrite in $milestoneWrites) {
    [IO.File]::WriteAllBytes($milestoneWrite.target, $milestoneWrite.bytes)
    if ((Get-FileHash -LiteralPath $milestoneWrite.target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $milestoneWrite.expected) {
        throw ('Installed milestone candidate hash differs: ' + $milestoneWrite.target)
    }
}
Write-Output 'Installed the two exact reviewed milestone candidate files. Tests and physical validation are separate.'
