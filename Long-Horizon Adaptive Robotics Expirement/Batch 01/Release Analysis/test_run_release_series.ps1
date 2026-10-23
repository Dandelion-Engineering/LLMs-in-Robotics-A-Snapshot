# DEFERRED synthetic checks. Never dot-source/execute the coordinator's main body.
# No actual queue, native model, CIM, sleep, seeded manifest, or retained evidence calls.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'run_release_series.ps1'
$tokens=$null; $parseErrors=$null
$tree=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$parseErrors)
if (@($parseErrors).Count) { throw ($parseErrors | Out-String) }
foreach ($name in @('Is-Integer','Is-True','Optional','Assert-Success','Assert-Job','Wait-Idle','Get-Schedule-State')) {
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
Write-Output ("Passed {0} bounded synthetic coordinator checks; no real coordinator/queue execution." -f $script:checks)

