# DEFERRED synthetic checks. Never dot-source/execute the coordinator's main body.
# No actual queue, native model, CIM, sleep, seeded manifest, or retained evidence calls.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Import-Module -Name (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force -Global -ErrorAction Stop
$hashCommand=Get-Command Get-FileHash -ErrorAction Stop
Write-Output ("Host PowerShell {0}; utility module {1}; Get-FileHash type {2}, source {3}" -f $PSVersionTable.PSVersion,$hashCommand.Module.Path,$hashCommand.CommandType,$hashCommand.Source)
$coordinatorTestRoot=[IO.Path]::GetFullPath($PSScriptRoot)
$source=Join-Path $coordinatorTestRoot 'run_release_series.ps1'
$tokens=$null; $parseErrors=$null
$tree=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$parseErrors)
if (@($parseErrors).Count) { throw ($parseErrors | Out-String) }
foreach ($name in @('Full-Local','Small-File','Convert-ControlJson','Read-Json','Hash-Small','Is-Integer','Is-True','Optional','Assert-Success','Assert-Receipt-In-State','Assert-Job','Wait-Idle','Get-Schedule-State','Test-JsonValueEqual','Assert-Finalized-Receipt')) {
    $defs=@($tree.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name},$true))
    if ($defs.Count -ne 1) { throw "Missing/ambiguous source function: $name" }
    . ([scriptblock]::Create($defs[0].Extent.Text))
}
function Check($Value,[string]$Message) { if (-not $Value) { throw $Message } }
function Refuses([scriptblock]$Action,[string]$Expected) {
    $caught=$null
    try { & $Action } catch { $caught=$_.Exception.Message }
    Check ($null -ne $caught -and $caught.Contains($Expected)) "Expected refusal containing '$Expected'; actual: $caught"
}
$script:checks=0
Check (-not (Is-Integer $false)) 'Boolean false must not stand in for integer exit 0'
Refuses { Assert-Success ([pscustomobject]@{id='20260923T120000000000Z-1234abcd';state='succeeded';exit_status=$false}) } 'integer-exit-0'
$script:checks++

& {
    $seriesQueueRuntime='C:\synthetic\queue'
    $seriesTerminalStates=@('succeeded','failed','canceled','interrupted','worker_start_failed')
    $seriesProject='C:\synthetic\project'; $seriesPython='C:\synthetic\python.exe'
    $JobWaitSeconds=300; $script:seriesPrecedingPids=@(1234,5678); $script:fakeTick=0
    $jobId='20260923T120000000000Z-1234abcd'; $command=@($seriesPython,'runner.py')
    function Read-Json($Path) {
        $state=if ($script:fakeTick -eq 0) {'running'} else {'succeeded'}
        return [pscustomobject]@{version=1;jobs=@([pscustomobject]@{id=$jobId;state=$state;
            worker_pid=1234;child_pid=5678;submitting_project='LLMs-in-Robotics';
            cwd=$seriesProject;resolved_executable=$seriesPython;argv=$command})}
    }
    function Test-Path($LiteralPath) { return $false } # lease/locks absent in every state
    function Get-CimInstance($Filter,$ErrorAction) {
        Check ($Filter.Contains('ProcessId = 1234') -and $Filter.Contains('ProcessId = 5678')) 'Only retained PID predicates required'
        if ($script:fakeTick -eq 1) { return [pscustomobject]@{ProcessId=5678} }
        return @()
    }
    function Start-Sleep($Seconds) { Check ($Seconds -eq 10) 'Reviewed poll interval changed'; $script:fakeTick++ }
    function Write-Host($Object) {}
    $answer=Wait-Idle $jobId $command
    Check ($script:fakeTick -eq 2 -and $answer.state -ceq 'succeeded') 'Absent lease must not bypass running state or a retained live PID'
    $script:checks++
    function Read-Json($Path) { return [pscustomobject]@{version=1;jobs=@([pscustomobject]@{id='foreign';state='queued'})} }
    function Get-CimInstance($Filter,$ErrorAction) { throw 'Must not reach CIM after foreign active job' }
    Refuses { Wait-Idle } 'Another pending/active queue job'
    $script:checks++
}

& {
    $ReleaseDir='C:\synthetic\release'; $Limit=1
    $script:seriesReleaseHash='a'*64
    $script:seriesSchedule=@(
        [pscustomobject]@{run_id='r1';cap_s=300},[pscustomobject]@{run_id='r2';cap_s=600},[pscustomobject]@{run_id='r3';cap_s=900})
    $script:seriesById=@{r1=$true;r2=$true;r3=$true}
    $fakeJob='20260923T120000000000Z-1234abcd'
    $fakeBatch=Join-Path (Join-Path $ReleaseDir 'batches') $fakeJob
    $fakeAttempt=Join-Path (Join-Path $ReleaseDir 'attempts') 'r1'
    $script:fakeMissingAttempt=$false; $script:fakeValidity='valid'; $script:fakeStop=$null
    function Full-Local($Path) { return $Path }
    function Hash-Small($Path) { return ('a'*64) }
    function Resolve-Ref($Reference,$Base) { return (Join-Path $Base $Reference.path) }
    function Test-Path($LiteralPath,$PathType) { return $true }
    function Get-ChildItem($LiteralPath,[switch]$Force) {
        if ($LiteralPath -ceq (Join-Path $ReleaseDir 'batches')) { return [pscustomobject]@{PSIsContainer=$true;Name=$fakeJob;FullName=$fakeBatch} }
        if ($LiteralPath -ceq (Join-Path $ReleaseDir 'attempts')) {
            if ($script:fakeMissingAttempt) { return @() }
            return [pscustomobject]@{PSIsContainer=$true;Name='r1';FullName=$fakeAttempt}
        }
        throw 'Unexpected directory enumeration'
    }
    function Read-Json($Path) {
        if ($Path.Contains('\runs\')) { throw 'Seed manifest must never be opened' }
        switch (Split-Path -Leaf $Path) {
            'planned.json' { return [pscustomobject]@{queue_job_id=$fakeJob;release_sha256=('a'*64);selected_run_ids=@('r1')} }
            'finished.json' { return [pscustomobject]@{queue_job_id=$fakeJob;stop_reason=$script:fakeStop;unlaunched_selected_run_ids=@();
                terminal_run_ids=@('r1');terminal_refs=@([pscustomobject]@{run_id='r1';path='attempts\r1\terminal.json';sha256=('a'*64)})} }
            'finalized.json' { return [pscustomobject]@{queue_job_id=$fakeJob;run_ids=@('r1');official_queue_receipt_sha256=('a'*64)} }
            'official-queue-status.json' { return [pscustomobject]@{id=$fakeJob;state='succeeded';exit_status=0} }
            'terminal.json' { return [pscustomobject]@{run_id='r1';queue_job_id=$fakeJob;release_sha256=('a'*64);integrity_breach=$false;
                post_run_integrity=[pscustomobject]@{passed=$true};
                result=[pscustomobject]@{validity=$script:fakeValidity;execution_status='failed';outcome='failure';infrastructure_invalid=$false}} }
            default { throw "Unexpected metadata read: $Path" }
        }
    }
    $state=Get-Schedule-State
    Check ($state.completed_count -eq 1 -and $state.remaining_count -eq 2 -and
        $state.remaining_task_cap_s -eq 1500 -and $state.next_run_ids[0] -ceq 'r2') 'Valid task failure must retain its disposition and preserve next schedule/caps'
    $script:checks++
    $script:fakeValidity='unknown'
    Refuses { Get-Schedule-State } 'Incident/invalidity'
    $script:fakeValidity='valid'; $script:fakeMissingAttempt=$true
    Refuses { Get-Schedule-State } 'finalized original attempt directory is missing'
    $script:checks++
    $script:fakeMissingAttempt=$false; $script:fakeStop='explicit incident'
    Refuses { Get-Schedule-State } 'Prior incident/unlaunched disposition'
    $script:checks++
}

# Versioned location: execute only these path assignments, never the main body.
foreach ($name in @('seriesExperiment','seriesProject','seriesRuntime')) {
    $nodes=@($tree.FindAll({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left -is [Management.Automation.Language.VariableExpressionAst] -and
        $node.Left.VariablePath.UserPath -ceq $name},$true))
    Check ($nodes.Count -eq 1) "Unique location assignment required: $name"
    # AST-created blocks have no backing file, hence an empty PSScriptRoot.
    # Substitute only that automatic path variable with the captured test root;
    # the actual source expression and parent-count calculation remain intact.
    $locationCode=$nodes[0].Extent.Text.Replace('$PSScriptRoot','$coordinatorTestRoot')
    . ([scriptblock]::Create($locationCode))
}
$expectedExperiment=Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $coordinatorTestRoot))
Check ($seriesExperiment -ceq $expectedExperiment -and $seriesProject -ceq (Split-Path -Parent $expectedExperiment) -and
    $seriesRuntime -ceq (Join-Path $expectedExperiment 'Runtime')) 'Nested coordinator must retain root-selected Runtime location'
$measurementNodes=@($tree.FindAll({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and
    $node.Left -is [Management.Automation.Language.VariableExpressionAst] -and
    $node.Left.VariablePath.UserPath -ceq 'measurementScript'},$true))
Check ($measurementNodes.Count -eq 1) 'Unique retention source assignment required'
. ([scriptblock]::Create($measurementNodes[0].Extent.Text))
Check ($measurementScript -ceq (Join-Path $expectedExperiment 'Batch 01\Release Analysis\measure_retention.py')) 'Retention helper must remain the original Release Analysis helper'
$script:checks++

$testDirectory=[IO.Path]::GetFullPath((Join-Path $coordinatorTestRoot ('synthetic-'+[Guid]::NewGuid().ToString('N'))))
[void][IO.Directory]::CreateDirectory($testDirectory)
$testEncoding=[Text.UTF8Encoding]::new($false)
try {
    # Exact original retention capture, with synthetic one-microsecond bounds
    # expressed in different offsets. A DateTime->culture string conversion
    # loses the fractions and can reverse the interval check.
    $timeText='{"captured_at":"2026-09-23T13:00:39.465344+00:00","started_at":"2026-09-23T13:00:39.465343Z","ended_at":"2026-09-23T06:00:39.465345-07:00","nested":["2026-09-23T13:10:10.595921Z",null,false,0]}'
    $timePath=Join-Path $testDirectory 'timestamps.json'
    [IO.File]::WriteAllText($timePath,$timeText,$testEncoding)
    foreach ($times in @((Read-Json $timePath),(Convert-ControlJson $timeText))) {
        Check ($times.captured_at -is [string] -and $times.captured_at -ceq '2026-09-23T13:00:39.465344+00:00') 'Capture timestamp lost original text/type'
        Check ($times.started_at -is [string] -and $times.ended_at -is [string] -and
            $times.nested[0] -ceq '2026-09-23T13:10:10.595921Z') 'Nested/queue-output timestamps must also remain strings'
        $capture=[DateTimeOffset]::Parse($times.captured_at)
        $start=[DateTimeOffset]::Parse($times.started_at); $end=[DateTimeOffset]::Parse($times.ended_at)
        Check (($capture-$start).Ticks -eq 10 -and ($end-$capture).Ticks -eq 10) 'One-microsecond interval or offset meaning changed'
        Check ($null -eq $times.nested[1] -and $times.nested[2] -is [bool] -and (Is-Integer $times.nested[3])) 'Non-string JSON value types changed'
    }
    $script:checks++

    # Read the tiny exact copies retained from r1's first finalized batch.
    # These are control receipts, not seed manifests or raw episode data.
    $fixtureDirectory=Join-Path $coordinatorTestRoot 'fixtures'
    $originalPath=Join-Path $fixtureDirectory 'original-official-receipt.json'
    $copyFixture=Join-Path $fixtureDirectory 'official-queue-status.json'
    $markerFixture=Join-Path $fixtureDirectory 'finalized.json'
    Check ((Hash-Small $originalPath) -ceq '417eaf5487c180696bfa06c0fd619c1554a89a3143db06dcee40800dbb2b5fc5') 'Original receipt fixture bytes changed'
    Check ((Hash-Small $copyFixture) -ceq 'c49d9ba5cb5e40f8aa47024d4b3a5269f3922c3d91270a55506ec55a9e4e5fbf') 'Canonical receipt fixture bytes changed'
    $original=Read-Json $originalPath; $canonicalCopy=Read-Json $copyFixture; $marker=Read-Json $markerFixture
    Check ((Test-JsonValueEqual $original $canonicalCopy) -and (Hash-Small $originalPath) -cne (Hash-Small $copyFixture)) 'Regression must exhibit equal values with different actual receipt bytes'
    Check ($marker.official_queue_receipt_sha256 -ceq (Hash-Small $copyFixture) -and
        $marker.official_queue_receipt_sha256 -cne (Hash-Small $originalPath)) 'Original marker binds canonical copy, not externally formatted receipt'
    $batchPath=Join-Path $testDirectory 'batch'
    $seriesQueueRuntime=Join-Path $testDirectory 'queue'
    [void][IO.Directory]::CreateDirectory($batchPath)
    [void][IO.Directory]::CreateDirectory($seriesQueueRuntime)
    $copyPath=Join-Path $batchPath 'official-queue-status.json'; $markerPath=Join-Path $batchPath 'finalized.json'
    $statePath=Join-Path $seriesQueueRuntime 'state.json'
    function Save-TestJson([string]$Path,$Value) {
        [IO.File]::WriteAllText($Path,(($Value | ConvertTo-Json -Depth 30)+[Environment]::NewLine),$testEncoding)
    }
    function Reset-Receipt-Case {
        [IO.File]::WriteAllBytes($copyPath,[IO.File]::ReadAllBytes($copyFixture))
        [IO.File]::WriteAllBytes($markerPath,[IO.File]::ReadAllBytes($markerFixture))
        Save-TestJson $statePath ([pscustomobject]@{version=1;jobs=@((Read-Json $originalPath))})
    }
    $runJob=[pscustomobject]@{id=$original.id;receipt_path=$originalPath;receipt_sha256=(Hash-Small $originalPath)}
    Reset-Receipt-Case
    $binding=Assert-Finalized-Receipt $batchPath $runJob
    Check ($binding.receipt_values_equal -and $binding.original_receipt_matches_installed_state -and
        $binding.original_receipt_sha256 -ceq $runJob.receipt_sha256 -and
        $binding.finalized_receipt_copy_sha256 -ceq $marker.official_queue_receipt_sha256) 'Fixed canonical-copy binding must pass the original receipt case'
    $script:checks++

    # Different JSON property order is semantically equal, but the marker must
    # still match its exact copy bytes. Reformatting a copy is not silently okay.
    $reordered=Convert-ControlJson '{"b":[0,false,null,"text"],"a":"2026-09-23T13:00:39.465344+00:00"}'
    $ordered=Convert-ControlJson '{"a":"2026-09-23T13:00:39.465344+00:00","b":[0,false,null,"text"]}'
    Check (Test-JsonValueEqual $ordered $reordered) 'JSON object property order is not semantic'
    Check (-not (Test-JsonValueEqual (Convert-ControlJson '{"value":0}') (Convert-ControlJson '{"value":false}'))) 'False and zero must not compare equal'
    Check (-not (Test-JsonValueEqual (Convert-ControlJson '{"argv":["a","b"]}') (Convert-ControlJson '{"argv":["b","a"]}'))) 'Array/argv order matters'
    Save-TestJson $copyPath $canonicalCopy
    Check ((Hash-Small $copyPath) -cne $marker.official_queue_receipt_sha256) 'Synthetic reformat must change exact copy bytes'
    Refuses { Assert-Finalized-Receipt $batchPath $runJob } 'exact canonical receipt copy'
    $script:checks++

    Reset-Receipt-Case
    $changed=Read-Json $copyPath; $changed.argv[$changed.argv.Count-1]='8'
    Save-TestJson $copyPath $changed
    $changedMarker=Read-Json $markerPath; $changedMarker.official_queue_receipt_sha256=Hash-Small $copyPath
    Save-TestJson $markerPath $changedMarker
    Refuses { Assert-Finalized-Receipt $batchPath $runJob } 'copy values differ'
    $script:checks++

    Reset-Receipt-Case
    $changed=Read-Json $statePath; $changed.jobs[0].ended_at='2026-09-23T13:10:10.595922Z'
    Save-TestJson $statePath $changed
    Refuses { Assert-Finalized-Receipt $batchPath $runJob } 'Receipt differs from installed record: ended_at'
    $script:checks++

    Reset-Receipt-Case
    $changed=Read-Json $statePath; $changed.jobs[0].argv[$changed.jobs[0].argv.Count-1]='8'
    Save-TestJson $statePath $changed
    Refuses { Assert-Finalized-Receipt $batchPath $runJob } 'Receipt argv differs'
    $script:checks++

    Reset-Receipt-Case
    $badJob=[pscustomobject]@{id=$runJob.id;receipt_path=$originalPath;receipt_sha256=('f'*64)}
    Refuses { Assert-Finalized-Receipt $batchPath $badJob } 'Original run receipt bytes changed'
    $changed=Read-Json $markerPath; $changed.queue_job_id='20260923T120000000000Z-1234abcd'
    Save-TestJson $markerPath $changed
    Refuses { Assert-Finalized-Receipt $batchPath $runJob } 'exact canonical receipt copy'
    $script:checks++
} finally {
    $safeRoot=$coordinatorTestRoot.TrimEnd('\')+'\'
    $safeTarget=[IO.Path]::GetFullPath($testDirectory)
    if (-not $safeTarget.StartsWith($safeRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Synthetic cleanup escaped test folder' }
    if (Test-Path -LiteralPath $safeTarget) { Remove-Item -LiteralPath $safeTarget -Recurse -Force }
}
Write-Output ("Passed {0} bounded coordinator checks on PowerShell {1}; no real coordinator/queue execution." -f $script:checks,$PSVersionTable.PSVersion)
