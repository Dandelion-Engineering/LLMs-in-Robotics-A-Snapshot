param([Parameter(Mandatory=$true)][string]$PlanHash)
$ErrorActionPreference = 'Stop'
$cleanupRoot = $PSScriptRoot
$repoRoot = [IO.Path]::GetFullPath((Join-Path $cleanupRoot '..\..\..\..'))
$libRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'venv\Lib'))
$tempRoot = [IO.Path]::GetFullPath($env:TEMP)
$planPath = Join-Path $cleanupRoot 'cleanup-plan.json'
if ((Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $PlanHash) { throw 'Plan hash changed' }
$plan = Get-Content -LiteralPath $planPath -Raw -Encoding UTF8 | ConvertFrom-Json
$resultPath = Join-Path $cleanupRoot 'cleanup-result.json'
$journalPath = Join-Path $cleanupRoot 'deletion-status.jsonl'
if ((Test-Path -LiteralPath $resultPath) -or (Test-Path -LiteralPath $journalPath)) { throw 'Cleanup is once only; result already exists' }
function VolumeSnapshot {
    $snapshot = @{}
    foreach ($drive in @('C','D')) {
        $info = [IO.DriveInfo]::new($drive + ':\')
        $snapshot[$drive] = @{ free = $info.AvailableFreeSpace; total = $info.TotalSize }
    }
    return $snapshot
}
function CheckAncestors([string]$target) {
    $node = Get-Item -LiteralPath $target -Force
    while ($null -ne $node) {
        if (($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Reparse path: $target" }
        if ($node -is [IO.FileInfo]) { $node = $node.Directory } else { $node = $node.Parent }
    }
}
function CheckedPath($item) {
    $resolved = (Resolve-Path -LiteralPath $item.path -ErrorAction Stop).ProviderPath
    if ($resolved -ne [IO.Path]::GetFullPath($item.path)) { throw "Resolved path mismatch: $resolved" }
    CheckAncestors $resolved
    if ($item.kind -eq 'file') {
        if (-not $resolved.StartsWith($libRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or $resolved -notmatch '\\__pycache__\\[^\\]+\.pyc$') { throw "Outside admitted cache scope: $resolved" }
        $file = Get-Item -LiteralPath $resolved -Force
        if ($file.Length -ne $item.bytes -or $file.LastWriteTimeUtc.ToFileTimeUtc() -ne $item.mtime_filetime) { throw "Cache metadata changed: $resolved" }
        if ((Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) { throw "Cache hash changed: $resolved" }
        $source = (Resolve-Path -LiteralPath $item.source).ProviderPath
        if (-not $source.StartsWith($libRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Source outside environment' }
        CheckAncestors $source
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.source_sha256) { throw "Surviving source changed: $source" }
        $handle = [IO.File]::Open($resolved,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None)
        $handle.Dispose()
    } elseif ($item.kind -eq 'empty_tree') {
        $directory = Get-Item -LiteralPath $resolved -Force
        if ($directory.Parent.FullName -ne $tempRoot -or $directory.Name -notmatch '^(robot-codex-session9-|robot-codex-isolation-schema-|robot-candidate-)') { throw "Outside admitted temp scope: $resolved" }
        $children = @(Get-ChildItem -LiteralPath $resolved -Recurse -Force)
        foreach ($child in $children) {
            if (-not $child.PSIsContainer -or ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Temp tree is not empty: $resolved" }
        }
        if ((1 + $children.Count) -ne $item.directories) { throw "Empty tree changed: $resolved" }
    } else { throw 'Unknown candidate type' }
    return $resolved
}
$start = Get-Date -Format o
$before = VolumeSnapshot
$passed = $false
$fail = $null
$deleted = 0
$logical = [long]0
$allocated = [long]0
try {
    & (Join-Path $repoRoot 'venv\Scripts\python.exe') -X utf8 -B (Join-Path $cleanupRoot 'quiescence.py') 'quiescence-at-delete.json'
    if ($LASTEXITCODE -ne 0) { throw 'Project not quiescent' }
    foreach ($item in $plan.targets) { $null = CheckedPath $item }
    $before = VolumeSnapshot
    foreach ($item in $plan.targets) {
        $resolved = CheckedPath $item
        if ($item.kind -eq 'empty_tree') {
            # Scope and every descendant were checked above. Only empty directories are removed.
            $children = @(Get-ChildItem -LiteralPath $resolved -Recurse -Force | Sort-Object { $_.FullName.Length } -Descending)
            foreach ($child in $children) { Remove-Item -LiteralPath $child.FullName -Force -ErrorAction Stop }
        }
        Remove-Item -LiteralPath $resolved -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $resolved) { throw "Deletion did not remove path: $resolved" }
        @{ path=$resolved; status='deleted_verified_absent'; bytes=$item.bytes; allocated=$item.allocated; time=(Get-Date -Format o) } | ConvertTo-Json -Compress | Add-Content -LiteralPath $journalPath -Encoding UTF8
        $deleted++; $logical += [long]$item.bytes; $allocated += [long]$item.allocated
    }
    $passed = $true
} catch { $fail = $_.Exception.Message }
$after = VolumeSnapshot
$result = @{ passed=$passed; started=$start; finished=(Get-Date -Format o); plan_sha256=$PlanHash; deleted_targets=$deleted; logical_bytes=$logical; file_allocated_bytes=$allocated; volumes_before=$before; volumes_after=$after; error=$fail }
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding UTF8
$result | ConvertTo-Json -Depth 8
if (-not $passed) { exit 1 }
