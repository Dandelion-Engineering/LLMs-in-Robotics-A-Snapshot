# External coordinator. No release creation, seed access, retry, incident review or source edits.
# Version 002: same stored-schedule/incident policy, repaired receipt binding and string timestamps.
# Every run and finalize operation uses the root-selected Runtime location through the installed queue.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ReleaseDir,
    [Parameter(Mandatory=$true)][string]$ResourcePolicy,
    [Parameter(Mandatory=$true)][string]$RetentionSummary,
    [Parameter(Mandatory=$true)][string]$RetentionReceipt,
    [Parameter(Mandatory=$true)][string]$AfterQueueReceipt,
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [ValidateRange(1,16)][int]$Limit = 4,
    [ValidateRange(300,86400)][int]$JobWaitSeconds = 43200
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Resolve this host's own utility module, not an inherited Core/legacy search
# path. In Windows PowerShell 5.1 Get-FileHash is a nested script function.
Import-Module -Name (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force -Global -ErrorAction Stop
$seriesExperiment = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$seriesProject = Split-Path -Parent $seriesExperiment
$seriesRuntime = Join-Path $seriesExperiment 'Runtime 004'
$seriesPython = Join-Path $seriesProject 'venv\Scripts\python.exe'
$seriesRunner = Join-Path $seriesRuntime 'release_runner.py'
$seriesQueue = 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py'
$seriesQueueRuntime = Join-Path (Split-Path -Parent $seriesQueue) 'runtime'
$seriesTerminalStates = @('succeeded','failed','canceled','interrupted','worker_start_failed')
$seriesEncoding = [Text.UTF8Encoding]::new($false)
$seriesReserve = [decimal]53687091200
$seriesSources = @()
$seriesSourceBefore = $null
$script:seriesPrecedingPids = @()
$seriesReceipts = Join-Path $seriesExperiment 'Evidence\queue-receipts'
$seriesCompletedBatches = @()
$seriesOutputCreated = $false
$seriesPhase = 'initialization'

function Full-Local([string]$Path) {
    if ($Path -notmatch '^[A-Za-z]:[\\/]') { throw "Absolute local drive path required: $Path" }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\','/')
    $part = $full
    while ($part) {
        if (Test-Path -LiteralPath $part) {
            if ((Get-Item -LiteralPath $part -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse path unsupported: $part" }
        }
        $part = Split-Path -Parent $part
    }
    return $full
}
function Small-File([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -or $item.Length -gt 8MB) { throw "Expected control/journal file of at most 8 MiB: $Path" }
    return $item
}
function Convert-ControlJson([string]$Text) {
    # PowerShell 7.5+ can explicitly retain strings; Windows PowerShell 5.1
    # already retains ISO strings. Reject auto-converting intermediate versions
    # rather than silently lose subsecond precision or change timezone meaning.
    $jsonCommand = Get-Command ConvertFrom-Json -CommandType Cmdlet
    if ($jsonCommand.Parameters.ContainsKey('DateKind')) {
        return (ConvertFrom-Json -InputObject $Text -DateKind String)
    }
    if ($PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1) {
        return (ConvertFrom-Json -InputObject $Text)
    }
    throw ("Unsupported PowerShell JSON timestamp conversion: {0}; use Windows PowerShell 5.1 or PowerShell 7.5+ with DateKind String" -f $PSVersionTable.PSVersion)
}
function Read-Json([string]$Path) {
    [void](Small-File $Path)
    return (Convert-ControlJson ([IO.File]::ReadAllText($Path)))
}
function Hash-Small([string]$Path) {
    [void](Small-File $Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Write-Text-New([string]$Path,[string]$Text) {
    $bytes = $seriesEncoding.GetBytes($Text)
    $stream = [IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try { $stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() }
}
function Write-New([string]$Path,$Value) {
    Write-Text-New $Path (($Value | ConvertTo-Json -Depth 30)+[Environment]::NewLine)
}
function Is-Integer($Value) { return ($Value -is [int] -or $Value -is [long]) }
function Is-True($Value) { return ($Value -is [bool] -and $Value) }
function Optional($Object,[string]$Name,$Default=$null) {
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}
function Assert-Success($Receipt) {
    if ($Receipt.id -notmatch '^\d{8}T\d{12}Z-[a-f0-9]{8}$' -or $Receipt.state -cne 'succeeded' -or
        -not (Is-Integer $Receipt.exit_status) -or $Receipt.exit_status -ne 0) {
        throw 'Real successful integer-exit-0 official receipt required'
    }
}
function Assert-Receipt-In-State($Receipt) {
    Assert-Success $Receipt
    $state = Read-Json (Join-Path $seriesQueueRuntime 'state.json')
    if ($state.version -ne 1) { throw 'Unknown installed queue state version' }
    $matches = @($state.jobs | Where-Object { $_.id -ceq $Receipt.id })
    if ($matches.Count -ne 1) { throw 'Receipt job missing/ambiguous in installed queue state' }
    foreach ($key in @('id','state','exit_status','worker_pid','child_pid','started_at','ended_at','cwd','resolved_executable','submitting_project')) {
        if ($matches[0].$key -cne $Receipt.$key) { throw "Receipt differs from installed record: $key" }
    }
    if (@($matches[0].argv).Count -ne @($Receipt.argv).Count) { throw 'Receipt argv length differs' }
    for ($i=0; $i -lt $Receipt.argv.Count; $i++) {
        if ($matches[0].argv[$i] -cne $Receipt.argv[$i]) { throw 'Receipt argv differs' }
    }
}
function Resolve-Ref($Reference,[string]$Base) {
    if ($Reference.sha256 -notmatch '^[a-f0-9]{64}$' -or -not $Reference.path) { throw 'Malformed direct file reference' }
    $path = $Reference.path
    if (-not [IO.Path]::IsPathRooted($path)) { $path = Join-Path $Base $path }
    $path = Full-Local $path
    if ((Hash-Small $path) -cne $Reference.sha256) { throw "Direct identity differs: $path" }
    return $path
}
function Require-Readiness-Ref([string]$Path) {
    $matches = @($script:seriesReadiness.evidence_refs | Where-Object {
        $candidate = $_.path
        if (-not [IO.Path]::IsPathRooted($candidate)) { $candidate = Join-Path $script:seriesReadinessBase $candidate }
        [IO.Path]::GetFullPath($candidate) -ieq $Path
    })
    if ($matches.Count -ne 1) { throw "Exactly one direct readiness evidence reference required: $Path" }
    if ((Resolve-Ref $matches[0] $script:seriesReadinessBase) -ine $Path) { throw 'Readiness reference resolved elsewhere' }
}
function Sources {
    $result = [ordered]@{}
    foreach ($path in $seriesSources) { $result[$path] = Hash-Small $path }
    return $result
}
function Assert-Sources {
    $runtimeNow = @(Get-ChildItem -LiteralPath $seriesRuntime -Filter '*.py' -File | ForEach-Object { $_.FullName } | Sort-Object)
    if (($runtimeNow -join [Environment]::NewLine) -cne ($script:seriesRuntimeInventory -join [Environment]::NewLine)) { throw 'Runtime Python inventory changed' }
    $now = Sources
    foreach ($path in $seriesSources) {
        if ($now[$path] -cne $seriesSourceBefore[$path]) { throw "Frozen/control source changed: $path" }
    }
}
function Assert-Job($Job,[string]$Identity,[string[]]$Command) {
    if ($Job.id -cne $Identity -or $Job.submitting_project -cne 'LLMs-in-Robotics' -or
        $Job.cwd -ine $seriesProject -or $Job.resolved_executable -ine $seriesPython -or
        @($Job.argv).Count -ne $Command.Count) { throw 'Queue job identity differs' }
    for ($i=0; $i -lt $Command.Count; $i++) {
        if ($Job.argv[$i] -cne $Command[$i]) { throw "Queue argv differs at $i" }
    }
}
function Python-Entrypoint($Job) {
    $argv = @($Job.argv); $i=1
    if ($argv.Count -lt 2) { throw 'Receipt has no explicit Python entrypoint' }
    while ($i -lt $argv.Count) {
        $value=$argv[$i]
        if ($value -ceq '--') { $i++; break }
        if ($value -cin @('-X','-W')) { $i+=2; continue }
        if ($value -cin @('-B','-E','-I','-O','-OO','-P','-q','-s','-S','-u','-v','-x') -or
            $value.StartsWith('-X') -or $value.StartsWith('-W')) { $i++; continue }
        if ($value.StartsWith('-')) { throw 'Receipt does not directly execute a Python script' }
        break
    }
    if ($i -ge $argv.Count) { throw 'Receipt lacks a Python script' }
    $path=$argv[$i]
    if (-not [IO.Path]::IsPathRooted($path)) { $path=Join-Path $Job.cwd $path }
    return (Full-Local $path)
}
function Argument-Path($Job,[string]$Flag) {
    $positions=@(for ($i=0; $i -lt $Job.argv.Count; $i++) { if ($Job.argv[$i] -ceq $Flag) { $i } })
    if ($positions.Count -ne 1 -or $positions[0]+1 -ge $Job.argv.Count) { throw "Missing/ambiguous receipt argument: $Flag" }
    $path=$Job.argv[$positions[0]+1]
    if (-not [IO.Path]::IsPathRooted($path)) { $path=Join-Path $Job.cwd $path }
    return (Full-Local $path)
}
function Wait-Idle([string]$OwnJob='', [string[]]$Command=@()) {
    $deadline = [DateTime]::UtcNow.AddSeconds($JobWaitSeconds)
    $observedPids = [Collections.Generic.HashSet[int]]::new()
    foreach ($knownPid in $script:seriesPrecedingPids) { [void]$observedPids.Add($knownPid) }
    $nextProgress = [DateTime]::UtcNow
    while ([DateTime]::UtcNow -lt $deadline) {
        # Read-only state and targeted PID observations; never queue CLI polling.
        $state = Read-Json (Join-Path $seriesQueueRuntime 'state.json')
        if ($state.version -ne 1) { throw 'Unknown queue state version' }
        $active = @($state.jobs | Where-Object { $_.state -notin $seriesTerminalStates })
        if (@($active | Where-Object { $_.id -cne $OwnJob }).Count) { throw 'Another pending/active queue job exists; no further queue call permitted' }
        $own = $null
        if ($OwnJob) {
            $matches = @($state.jobs | Where-Object { $_.id -ceq $OwnJob })
            if ($matches.Count -ne 1) { throw 'Submitted job missing or ambiguous' }
            $own = $matches[0]; Assert-Job $own $OwnJob $Command
            foreach ($value in @($own.worker_pid,$own.child_pid)) {
                if ($null -ne $value) {
                    if (-not (Is-Integer $value) -or $value -le 0) { throw 'Invalid queue PID' }
                    [void]$observedPids.Add([int]$value)
                }
            }
        }
        $leasePath = Join-Path $seriesQueueRuntime 'worker.json'
        if (Test-Path -LiteralPath $leasePath) {
            $lease = Read-Json $leasePath
            if (-not (Is-Integer $lease.pid) -or $lease.pid -le 0) { throw 'Invalid worker lease PID' }
            [void]$observedPids.Add([int]$lease.pid)
        }
        $filter = (($observedPids | ForEach-Object { 'ProcessId = ' + $_ }) -join ' OR ')
        if (-not $filter) { throw 'Retained predecessor PID identity required' }
        $liveOwned = @(Get-CimInstance Win32_Process -Filter $filter -ErrorAction Stop)
        $locksAbsent = -not (Test-Path -LiteralPath $leasePath) -and
                       -not (Test-Path -LiteralPath (Join-Path $seriesQueueRuntime 'state.lock'))
        # Every clause matters. Absent worker.json alone never means completion.
        if (($null -eq $own -or $own.state -in $seriesTerminalStates) -and -not $liveOwned.Count -and $locksAbsent) {
            if ($null -ne $own) { $script:seriesPrecedingPids = @([int]$own.worker_pid,[int]$own.child_pid) }
            return $own
        }
        if ([DateTime]::UtcNow -ge $nextProgress) {
            $liveIds = @($liveOwned | ForEach-Object { $_.ProcessId })
            Write-Host ("Waiting for natural exit: job={0}; retained PIDs={1}; locks absent={2}" -f $OwnJob,($liveIds -join ','),$locksAbsent)
            $nextProgress = [DateTime]::UtcNow.AddSeconds(30)
        }
        Start-Sleep -Seconds 10
    }
    throw 'Natural-exit observation timed out; no status, cancellation, retry or repair attempted'
}
function Queue-Command([string[]]$Arguments,[string]$CapturePath,[string]$Label) {
    # Keep a terminal receipt even if another source changed; never run a changed queue CLI.
    if ((Hash-Small $seriesQueue) -cne $seriesSourceBefore[$seriesQueue]) { throw 'Installed queue CLI changed' }
    $stderr = Join-Path $OutputRoot ($Label+'.stderr.txt')
    $text = (& $seriesPython -X utf8 -B $seriesQueue @Arguments 2> $stderr | Out-String)
    $code = $LASTEXITCODE
    Write-Text-New $CapturePath $text
    if ($code -ne 0) { throw "Queue CLI failed ($code); exact output retained: $CapturePath" }
    return (Convert-ControlJson $text)
}
function Run-Queued([string]$Label,[string[]]$Arguments) {
    [void](Wait-Idle); Assert-Sources
    $command = @($seriesPython,'-X','utf8','-B',$seriesRunner)+$Arguments
    $submitted = Queue-Command (@('submit','--project','LLMs-in-Robotics','--cwd',$seriesProject,'--')+$command) (Join-Path $OutputRoot ($Label+'-submission.json')) ($Label+'-submit')
    if ($submitted.id -notmatch '^\d{8}T\d{12}Z-[a-f0-9]{8}$') { throw 'Unexpected submitted job ID' }
    Assert-Job $submitted $submitted.id $command
    Write-Host "$Label submitted: $($submitted.id)"
    $terminal = Wait-Idle $submitted.id $command
    $receiptPath = Join-Path $seriesReceipts ($submitted.id+'.json')
    $official = Queue-Command @('status',$submitted.id) $receiptPath ($Label+'-status')
    Assert-Job $official $submitted.id $command
    foreach ($key in @('state','worker_pid','child_pid','started_at','ended_at','exit_status')) {
        if ($official.$key -cne $terminal.$key) { throw "Official terminal receipt changed: $key" }
    }
    Assert-Sources; Assert-Success $official
    return [pscustomobject]@{id=$official.id; receipt_path=$receiptPath; receipt_sha256=(Hash-Small $receiptPath)}
}


function Test-JsonValueEqual($Left,$Right) {
    if ($null -eq $Left -or $null -eq $Right) { return ($null -eq $Left -and $null -eq $Right) }
    if ($Left -is [array] -or $Right -is [array]) {
        if ($Left -isnot [array] -or $Right -isnot [array] -or $Left.Count -ne $Right.Count) { return $false }
        for ($i=0; $i -lt $Left.Count; $i++) {
            if (-not (Test-JsonValueEqual $Left[$i] $Right[$i])) { return $false }
        }
        return $true
    }
    if ($Left -is [pscustomobject] -or $Right -is [pscustomobject]) {
        if ($Left -isnot [pscustomobject] -or $Right -isnot [pscustomobject]) { return $false }
        $leftProperties=@($Left.PSObject.Properties); $rightProperties=@($Right.PSObject.Properties)
        if ($leftProperties.Count -ne $rightProperties.Count) { return $false }
        foreach ($property in $leftProperties) {
            $matches=@($rightProperties | Where-Object { $_.Name -ceq $property.Name })
            if ($matches.Count -ne 1 -or -not (Test-JsonValueEqual $property.Value $matches[0].Value)) { return $false }
        }
        return $true
    }
    if (Is-Integer $Left) { return ((Is-Integer $Right) -and $Left -eq $Right) }
    if ($Left.GetType() -ne $Right.GetType()) { return $false }
    if ($Left -is [string]) { return [string]::Equals($Left,$Right,[StringComparison]::Ordinal) }
    return ($Left -ceq $Right)
}
function Assert-Finalized-Receipt([string]$BatchPath,$RunJob) {
    $originalPath = Full-Local $RunJob.receipt_path
    if ((Hash-Small $originalPath) -cne $RunJob.receipt_sha256) { throw 'Original run receipt bytes changed after official verification' }
    $original = Read-Json $originalPath
    Assert-Receipt-In-State $original
    if ($original.id -cne $RunJob.id) { throw 'Original run receipt job differs' }
    $copyPath = Full-Local (Join-Path $BatchPath 'official-queue-status.json')
    $copy = Read-Json $copyPath; Assert-Success $copy
    if (-not (Test-JsonValueEqual $original $copy)) { throw 'Finalized receipt copy values differ from original official receipt' }
    $copyHash = Hash-Small $copyPath
    $markerPath = Full-Local (Join-Path $BatchPath 'finalized.json')
    $marker = Read-Json $markerPath
    if ($marker.queue_job_id -cne $RunJob.id -or $marker.official_queue_receipt_sha256 -cne $copyHash) {
        throw 'Finalization marker differs from exact canonical receipt copy'
    }
    return [pscustomobject]@{original_receipt_path=$originalPath; original_receipt_sha256=$RunJob.receipt_sha256;
        finalized_receipt_copy=$copyPath; finalized_receipt_copy_sha256=$copyHash;
        receipt_values_equal=$true; original_receipt_matches_installed_state=$true}
}

function Get-Schedule-State {
    # Only public release references and terminal journals; never open runs/*.json.
    $batchById = @{}
    $finalizedIds = @{}
    $batchesPath = Join-Path $ReleaseDir 'batches'
    if (Test-Path -LiteralPath $batchesPath) {
        foreach ($folder in @(Get-ChildItem -LiteralPath $batchesPath -Force)) {
            if (-not $folder.PSIsContainer) { throw 'Unexpected file in release batches' }
            [void](Full-Local $folder.FullName)
            $markerPath = Join-Path $folder.FullName 'finalized.json'
            if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) { throw "Prior batch not finalized: $($folder.Name)" }
            $planned = Read-Json (Join-Path $folder.FullName 'planned.json')
            $finished = Read-Json (Join-Path $folder.FullName 'finished.json')
            $marker = Read-Json $markerPath
            $officialPath = Join-Path $folder.FullName 'official-queue-status.json'
            $official = Read-Json $officialPath; Assert-Success $official
            if ($planned.queue_job_id -cne $folder.Name -or $finished.queue_job_id -cne $folder.Name -or
                $marker.queue_job_id -cne $folder.Name -or $official.id -cne $folder.Name -or
                $planned.release_sha256 -cne $script:seriesReleaseHash -or
                $marker.official_queue_receipt_sha256 -cne (Hash-Small $officialPath)) { throw 'Finalized batch identity differs' }
            if ($null -ne $finished.stop_reason -or @($finished.unlaunched_selected_run_ids).Count) {
                throw "Prior incident/unlaunched disposition needs explicit root handling: $($folder.Name)"
            }
            if ((@($marker.run_ids) -join [Environment]::NewLine) -cne (@($finished.terminal_run_ids) -join [Environment]::NewLine) -or
                (@($planned.selected_run_ids) -join [Environment]::NewLine) -cne (@($finished.terminal_run_ids) -join [Environment]::NewLine)) { throw 'Finalized batch accounting differs' }
            if ((@($finished.terminal_refs | ForEach-Object { $_.run_id }) -join [Environment]::NewLine) -cne
                (@($finished.terminal_run_ids) -join [Environment]::NewLine)) { throw 'Finalized terminal reference inventory differs' }
            foreach ($ref in @($finished.terminal_refs)) {
                if (-not $script:seriesById.ContainsKey($ref.run_id) -or $finalizedIds.ContainsKey($ref.run_id)) { throw 'Unplanned or duplicate finalized attempt' }
                $expectedTerminal = Join-Path (Join-Path (Join-Path $ReleaseDir 'attempts') $ref.run_id) 'terminal.json'
                if ((Resolve-Ref $ref $ReleaseDir) -ine $expectedTerminal) { throw 'Missing or redirected finalized original terminal' }
                $finalizedIds[$ref.run_id] = $folder.Name
            }
            $batchById[$folder.Name] = $finished
        }
    }
    $attempts = Join-Path $ReleaseDir 'attempts'; $completed = @{}
    if (Test-Path -LiteralPath $attempts) {
        foreach ($folder in @(Get-ChildItem -LiteralPath $attempts -Force)) {
            if (-not $folder.PSIsContainer -or -not $script:seriesById.ContainsKey($folder.Name)) { throw 'Unplanned release attempt path' }
            [void](Full-Local $folder.FullName)
            $terminalPath = Join-Path $folder.FullName 'terminal.json'
            if (-not (Test-Path -LiteralPath $terminalPath -PathType Leaf)) { throw "Unresolved claimed/started attempt: $($folder.Name)" }
            $terminal = Read-Json $terminalPath
            if ($terminal.run_id -cne $folder.Name -or $terminal.release_sha256 -cne $script:seriesReleaseHash -or
                -not $batchById.ContainsKey($terminal.queue_job_id) -or
                $finalizedIds[$folder.Name] -cne $terminal.queue_job_id) { throw 'Terminal lacks finalized release batch binding' }
            $refs = @($batchById[$terminal.queue_job_id].terminal_refs | Where-Object { $_.run_id -ceq $folder.Name })
            if ($refs.Count -ne 1 -or (Resolve-Ref $refs[0] $ReleaseDir) -ine $terminalPath) { throw 'Terminal byte reference differs' }
            $result = $terminal.result
            if (-not (Is-True $terminal.post_run_integrity.passed) -or $terminal.integrity_breach -isnot [bool] -or
                $terminal.integrity_breach -or $result.validity -cne 'valid' -or
                (Is-True (Optional $result 'infrastructure_invalid')) -or $result.execution_status -ceq 'aborted') {
                throw "Incident/invalidity blocks automatic continuation: $($folder.Name)"
            }
            foreach ($flag in @('integrity_breach','source_integrity_breach','readiness_integrity_breach','evidence_integrity_breach','evaluator_integrity_breach','oracle_exposure')) {
                if ((Is-True (Optional $terminal $flag)) -or (Is-True (Optional $result $flag))) { throw "Integrity flag blocks series: $($folder.Name)" }
            }
            if ((Optional $result 'failure_class') -in @('source_hash_mismatch','readiness_failure','evidence_integrity_failure','evaluator_corruption','oracle_exposure','integrity_failure','infrastructure_failure')) {
                throw "Execution/integrity failure blocks series: $($folder.Name)"
            }
            if ($result.execution_status -notin @('completed','failed','timed_out')) { throw 'Unknown terminal execution status' }
            $completed[$folder.Name] = $true
        }
    }
    if ($completed.Count -ne $finalizedIds.Count) { throw 'A finalized original attempt directory is missing; never retry its manifest' }
    $remaining = @($script:seriesSchedule | Where-Object { -not $completed.ContainsKey($_.run_id) })
    [long]$seconds = 0
    foreach ($row in $remaining) { $seconds += $row.cap_s }
    return [pscustomobject]@{completed_count=$completed.Count; remaining_count=$remaining.Count;
        remaining_task_cap_s=$seconds; next_run_ids=@($remaining | Select-Object -First $Limit | ForEach-Object { $_.run_id })}
}
function Capacity($State) {
    $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($ReleaseDir))
    if (-not $drive.IsReady -or $drive.Name -ine 'C:\') { throw 'Scored storage must be the ready C volume' }
    [decimal]$required = [Math]::Ceiling($script:seriesPlanningRate * [decimal]1048576 * [decimal]$State.remaining_task_cap_s) + $seriesReserve
    [long]$free = $drive.AvailableFreeSpace
    return [ordered]@{measured_at_utc=[DateTime]::UtcNow.ToString('o'); release_sha256=$script:seriesReleaseHash;
        completed_attempts=$State.completed_count; remaining_attempts=$State.remaining_count;
        remaining_original_task_cap_s=$State.remaining_task_cap_s; planning_rate_mib_per_task_second=$script:seriesPlanningRate;
        retention_summary=$RetentionSummary; retention_summary_sha256=(Hash-Small $RetentionSummary);
        reserve_bytes=[long]$seriesReserve; required_bytes=[long]$required; available_c_bytes=$free;
        capacity_sufficient=([decimal]$free -ge $required);
        scope='All remaining original task caps times frozen measured planning rate plus 50 GiB; estimate, not a future-rate bound'}
}

try {
    $ReleaseDir = Full-Local $ReleaseDir; $ResourcePolicy = Full-Local $ResourcePolicy
    $RetentionSummary = Full-Local $RetentionSummary; $RetentionReceipt = Full-Local $RetentionReceipt
    $AfterQueueReceipt = Full-Local $AfterQueueReceipt; $OutputRoot = Full-Local $OutputRoot
    $releaseBase = Full-Local (Join-Path $seriesExperiment 'Evidence\releases')
    $outputBase = Full-Local (Join-Path $seriesExperiment 'Evidence\release-series')
    if (-not $ReleaseDir.StartsWith($releaseBase+'\', [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetPathRoot($ReleaseDir) -ine 'C:\') { throw 'Existing protected C release directory required' }
    if (-not $OutputRoot.StartsWith($outputBase+'\', [StringComparison]::OrdinalIgnoreCase) -or
        (Test-Path -LiteralPath $OutputRoot) -or -not (Test-Path -LiteralPath (Split-Path -Parent $OutputRoot) -PathType Container)) {
        throw 'Fresh series output under an existing Evidence\release-series parent required'
    }
    $releasePath = Join-Path $ReleaseDir 'release.json'; $release = Read-Json $releasePath
    if ($release.schema_version -cne 'robot-evaluation-release-1.0' -or
        $release.release_id -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$') { throw 'Existing protocol release required' }
    $freezePath = Resolve-Ref $release.freeze_manifest $ReleaseDir
    $readinessPath = Resolve-Ref $release.readiness $ReleaseDir
    $freeze = Read-Json $freezePath
    $script:seriesReadiness = Read-Json $readinessPath
    $script:seriesReadinessBase = Split-Path -Parent $readinessPath
    if ($freeze.release_id -cne $release.release_id -or $script:seriesReadiness.release_id -cne $release.release_id -or
        -not (Is-True $script:seriesReadiness.scored_ready) -or $script:seriesReadiness.freeze_sha256 -cne (Hash-Small $freezePath) -or
        -not (Is-Integer $freeze.maximum_retries) -or $freeze.maximum_retries -ne 0) { throw 'Release/freeze/readiness or zero-retry policy differs' }
    foreach ($direct in @($PSCommandPath,$ResourcePolicy,$RetentionSummary,$RetentionReceipt)) { Require-Readiness-Ref (Full-Local $direct) }
    $retention = Read-Json $RetentionSummary; $retentionOfficial = Read-Json $RetentionReceipt
    Assert-Receipt-In-State $retentionOfficial
    if ($retention.schema_version -cne 'robot-retention-inventory-1.0' -or
        $retention.derivation_queue_job_id -cne $retentionOfficial.id -or $retention.reserve_bytes -ne 53687091200) {
        throw 'Retention inventory/official job/reserve differs'
    }
    $measurementScript = Full-Local (Join-Path $seriesExperiment 'Batch 01\Release Analysis\measure_retention.py')
    if ((Resolve-Ref $retention.measurement_source (Split-Path -Parent $RetentionSummary)) -ine $measurementScript -or
        (Split-Path -Leaf $RetentionSummary) -cne 'summary.json') { throw 'Retention measurement helper/output identity differs' }
    if ($retentionOfficial.submitting_project -cne 'LLMs-in-Robotics' -or
        $retentionOfficial.cwd -ine $seriesProject -or $retentionOfficial.resolved_executable -ine $seriesPython -or
        (Python-Entrypoint $retentionOfficial) -ine $measurementScript -or
        (Argument-Path $retentionOfficial '--output') -ine (Split-Path -Parent $RetentionSummary)) { throw 'Retention receipt entrypoint/output differs' }
    $captured = [DateTimeOffset]::Parse($retention.captured_at)
    if ($captured -lt [DateTimeOffset]::Parse($retentionOfficial.started_at) -or
        $captured -gt [DateTimeOffset]::Parse($retentionOfficial.ended_at)) { throw 'Retention capture is outside official job interval' }
    $maxRate = [double]$retention.maximum_measured_mib_per_task_second
    $rate = [double]$retention.planning_rate_mib_per_task_second
    if ([double]::IsNaN($maxRate) -or [double]::IsInfinity($maxRate) -or $maxRate -le 0 -or
        [double]::IsNaN($rate) -or [double]::IsInfinity($rate) -or $rate -lt [Math]::Max(3.0,$maxRate)) { throw 'Invalid/understated frozen retention rate' }
    $script:seriesPlanningRate = [decimal]$retention.planning_rate_mib_per_task_second
    $preceding = Read-Json $AfterQueueReceipt; Assert-Receipt-In-State $preceding
    foreach ($value in @($preceding.worker_pid,$preceding.child_pid)) {
        if (-not (Is-Integer $value) -or $value -le 0) { throw 'Completed predecessor receipt lacks positive PID identities' }
        $script:seriesPrecedingPids += [int]$value
    }
    if (-not (Test-Path -LiteralPath $seriesReceipts -PathType Container)) { throw 'Existing official receipt directory required' }
    $script:seriesReleaseHash = Hash-Small $releasePath
    $script:seriesSchedule = @(); $script:seriesById = @{}; $indices = @{}
    $pattern = '^'+[regex]::Escape($release.release_id)+'-C(?<case>[0-9]{2})-rep[12]-(baseline|A1|A2|A3)-(persistent|no-persistence)$'
    foreach ($ref in @($release.manifest_refs | Sort-Object scheduled_index)) {
        $match = [regex]::Match($ref.run_id,$pattern)
        if (-not $match.Success) { throw 'Unknown public run identity; seed manifests are never used to infer caps' }
        $caseNumber = [int]$match.Groups['case'].Value
        if ($caseNumber -lt 1 -or $caseNumber -gt 24 -or -not (Is-Integer $ref.scheduled_index) -or
            $ref.scheduled_index -lt 1 -or $ref.scheduled_index -gt 264 -or
            $script:seriesById.ContainsKey($ref.run_id) -or $indices.ContainsKey($ref.scheduled_index) -or
            $ref.path -cne ('runs/'+$ref.run_id+'.json') -or $ref.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Public schedule identity differs' }
        $cap = if ($caseNumber -le 8) {300} elseif ($caseNumber -le 16) {600} else {900}
        $row = [pscustomobject]@{run_id=$ref.run_id; scheduled_index=$ref.scheduled_index; cap_s=$cap}
        $script:seriesSchedule += $row; $script:seriesById[$row.run_id]=$row; $indices[$row.scheduled_index]=$true
    }
    if ($script:seriesSchedule.Count -ne 264 -or
        ($script:seriesSchedule | Measure-Object cap_s -Sum).Sum -ne 156600) { throw 'Unchanged 264-attempt/156600-second public schedule required' }
    $script:seriesRuntimeInventory = @(Get-ChildItem -LiteralPath $seriesRuntime -Filter '*.py' -File | ForEach-Object { $_.FullName } | Sort-Object)
    $seriesSources = @(@($PSCommandPath,$seriesQueue,$releasePath,$freezePath,$readinessPath,
        $ResourcePolicy,$RetentionSummary,$RetentionReceipt,$AfterQueueReceipt,$measurementScript,
        (Join-Path $seriesExperiment 'Architecture Map\map.py')) + $script:seriesRuntimeInventory | Sort-Object -Unique)
    $seriesSourceBefore = Sources
    [void](Wait-Idle)
    [void][IO.Directory]::CreateDirectory($OutputRoot); $seriesOutputCreated=$true
    Write-New (Join-Path $OutputRoot 'started.json') ([ordered]@{
        schema_version='frozen-release-series-1'; started_at=[DateTime]::UtcNow.ToString('o'); release_dir=$ReleaseDir;
        release_id=$release.release_id; release_sha256=$script:seriesReleaseHash; limit=$Limit;
        after_queue_receipt=$AfterQueueReceipt; resource_policy=$ResourcePolicy;
        retention_summary=$RetentionSummary; retention_receipt=$RetentionReceipt;
        sources_before=$seriesSourceBefore; no_seed_manifests_opened=$true; automatic_retries=0;
        incident_reviews_created=0; frozen_sources_changed=$false;
        scope='Stored original schedule only; ordinary valid task failures retained; every incident stops'})
    for ($batchNumber=1; $batchNumber -le 265; $batchNumber++) {
        $seriesPhase='pre_batch'; [void](Wait-Idle); Assert-Sources
        $state = Get-Schedule-State
        if ($state.remaining_count -eq 0) {
            if ($state.completed_count -ne 264) { throw 'No remaining schedule but terminal coverage is not 264' }
            Write-New (Join-Path $OutputRoot 'complete.json') ([ordered]@{
                schema_version='frozen-release-series-1'; completed_at=[DateTime]::UtcNow.ToString('o');
                release_dir=$ReleaseDir; release_sha256=$script:seriesReleaseHash; finalized_terminal_attempts=264;
                batches=$seriesCompletedBatches; sources_after=(Sources); task_success_claimed=$false;
                scope='All original attempts finalized with valid terminal dispositions; planned analysis still required'})
            Write-Host 'All 264 original attempts finalized; no policy success/scientific conclusion inferred.'
            break
        }
        if ($batchNumber -gt 264) { throw 'Series batch bound reached; no automatic extension' }
        $label = 'batch-'+$batchNumber.ToString('000')
        $capacity = Capacity $state
        Write-New (Join-Path $OutputRoot ($label+'-capacity.json')) $capacity
        if (-not $capacity.capacity_sufficient) { throw 'Remaining full caps plus reserve exceed current C capacity; no run submitted' }
        $seriesPhase=$label+'-run'
        $runJob = Run-Queued ($label+'-run') @('run','--release-dir',$ReleaseDir,'--limit',[string]$Limit)
        $batchPath = Join-Path (Join-Path $ReleaseDir 'batches') $runJob.id
        $planned = Read-Json (Join-Path $batchPath 'planned.json')
        if ((@($planned.selected_run_ids) -join [Environment]::NewLine) -cne (@($state.next_run_ids) -join [Environment]::NewLine) -or
            $planned.release_sha256 -cne $script:seriesReleaseHash) { throw 'Runner selected a different stored-schedule slice' }
        $seriesPhase=$label+'-finalize'
        # Finalization hashes map revision attachments; keep growing map work queued too.
        $finalizeJob = Run-Queued ($label+'-finalize') @('finalize','--release-dir',$ReleaseDir,
            '--verified-queue-job-id',$runJob.id,'--queue-status',$runJob.receipt_path)
        $receiptBinding = Assert-Finalized-Receipt $batchPath $runJob
        $markerPath = Join-Path $batchPath 'finalized.json'
        $entry = [ordered]@{run_job=$runJob; finalize_job=$finalizeJob; receipt_binding=$receiptBinding; finalized_marker=$markerPath;
            finalized_marker_sha256=(Hash-Small $markerPath); original_selected_run_ids=@($planned.selected_run_ids)}
        Write-New (Join-Path $OutputRoot ($label+'-complete.json')) $entry
        $seriesCompletedBatches += $entry
        [void](Get-Schedule-State)
    }
} catch {
    if ($seriesOutputCreated) {
        Write-New (Join-Path $OutputRoot 'stopped.json') ([ordered]@{
            schema_version='frozen-release-series-1'; stopped_at=[DateTime]::UtcNow.ToString('o');
            phase=$seriesPhase; error=$_.Exception.Message; completed_batches=$seriesCompletedBatches;
            automatic_retry_attempted=$false; cancellation_attempted=$false; incident_review_created=$false;
            originals_changed=$false; instruction='Retain outputs. Root must resolve this concrete stop before further launch.'})
    }
    throw
}
