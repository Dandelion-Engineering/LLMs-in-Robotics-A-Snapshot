# External coordinator only: every evidence derivation is a separate installed-queue job.
# No queue CLI calls while any worker/child is alive; no kill, cancel, repair or queue writes.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Screen,
    [Parameter(Mandatory=$true)][string]$ScreenReceipt,
    [ValidatePattern('^[0-9]{3}$')][string]$Suffix = '002',
    [ValidateRange(60,14400)][int]$JobWaitSeconds = 3600
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$deriveExperiment = Split-Path -Parent $PSScriptRoot
$deriveProject = Split-Path -Parent $deriveExperiment
$derivePython = Join-Path $deriveProject 'venv\Scripts\python.exe'
$deriveQueue = 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py'
$deriveQueueRuntime = Join-Path (Split-Path -Parent $deriveQueue) 'runtime'
$deriveTerminal = @('succeeded','failed','canceled','interrupted','worker_start_failed')
$deriveEncoding = [Text.UTF8Encoding]::new($false)

function Read-Json([string]$Path) {
    return ([IO.File]::ReadAllText($Path) | ConvertFrom-Json)
}
function Write-New([string]$Path, [string]$Text) {
    $bytes = $deriveEncoding.GetBytes($Text)
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}
function Full-Local([string]$Path) {
    if ($Path -notmatch '^[A-Za-z]:[\\/]') { throw "Absolute local drive path required: $Path" }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\','/')
    # Refuse reparse ancestors rather than redirect writes/inputs through a junction.
    $part = $full
    while ($part) {
        if (Test-Path -LiteralPath $part) {
            if ((Get-Item -LiteralPath $part -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Reparse path is unsupported: $part"
            }
        }
        $part = Split-Path -Parent $part
    }
    return $full
}
function Sources {
    $result = [ordered]@{}
    foreach ($path in $deriveSources) {
        $result[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $result
}
function Assert-Sources {
    $now = Sources
    foreach ($path in $deriveSources) {
        if ($now[$path] -cne $deriveBefore[$path]) { throw "Source/input changed; stopping: $path" }
    }
}
function Assert-Job($Job, [string]$Identity, [string[]]$Command) {
    if ($Job.id -cne $Identity -or $Job.submitting_project -cne 'LLMs-in-Robotics' -or
        $Job.cwd -ine $deriveProject -or $Job.resolved_executable -ine $derivePython -or
        $Job.argv.Count -ne $Command.Count) { throw 'Queue job identity differs' }
    for ($i=0; $i -lt $Command.Count; $i++) {
        if ($Job.argv[$i] -cne $Command[$i]) { throw "Queue argv differs at $i" }
    }
}
function Wait-Idle([string]$OwnJob = '', [string[]]$Command = @()) {
    $deadline = [DateTime]::UtcNow.AddSeconds($JobWaitSeconds)
    $observedPids = [Collections.Generic.HashSet[int]]::new()
    foreach ($knownPid in $script:derivePrecedingPids) { [void]$observedPids.Add($knownPid) }
    $nextProgress = [DateTime]::UtcNow
    while ([DateTime]::UtcNow -lt $deadline) {
        # Read-only file/OS observations: deliberately no installed queue command here.
        $state = Read-Json (Join-Path $deriveQueueRuntime 'state.json')
        if ($state.version -ne 1) { throw 'Unknown queue state version' }
        $active = @($state.jobs | Where-Object { $_.state -notin $deriveTerminal })
        if (@($active | Where-Object { $_.id -cne $OwnJob }).Count) {
            throw 'Another pending/active queue job exists; no further queue calls are permitted'
        }
        $own = $null
        if ($OwnJob) {
            $matches = @($state.jobs | Where-Object { $_.id -ceq $OwnJob })
            if ($matches.Count -ne 1) { throw 'Submitted job disappeared or is ambiguous' }
            $own = $matches[0]
            Assert-Job $own $OwnJob $Command
            foreach ($value in @($own.worker_pid, $own.child_pid)) {
                if ($null -ne $value) {
                    if ($value -isnot [int] -and $value -isnot [long]) { throw 'Invalid queue PID' }
                    if ($value -le 0) { throw 'Invalid queue PID' }
                    [void]$observedPids.Add([int]$value)
                }
            }
        }
        $leasePath = Join-Path $deriveQueueRuntime 'worker.json'
        if (Test-Path -LiteralPath $leasePath) {
            $lease = Read-Json $leasePath
            if (($lease.pid -isnot [int] -and $lease.pid -isnot [long]) -or $lease.pid -le 0) { throw 'Invalid worker lease PID' }
            [void]$observedPids.Add([int]$lease.pid)
        }
        # Targeted read-only CIM queries; no process enumeration and no kill-style probe.
        # Any still-live observed PID blocks progress, including PID reuse.
        $filter = (($observedPids | ForEach-Object { 'ProcessId = ' + $_ }) -join ' OR ')
        if (-not $filter) { throw 'No retained predecessor PID identity for safe exit observation' }
        $liveOwned = @(Get-CimInstance Win32_Process -Filter $filter -ErrorAction Stop)
        $locksAbsent = -not (Test-Path -LiteralPath $leasePath) -and
                       -not (Test-Path -LiteralPath (Join-Path $deriveQueueRuntime 'state.lock'))
        if (($null -eq $own -or $own.state -in $deriveTerminal) -and
            -not $liveOwned.Count -and $locksAbsent) {
            if ($null -ne $own) { $script:derivePrecedingPids = @([int]$own.worker_pid, [int]$own.child_pid) }
            return $own
        }
        if ([DateTime]::UtcNow -ge $nextProgress) {
            $liveIds = @($liveOwned | ForEach-Object { $_.ProcessId })
            Write-Host ("Waiting for natural queue exit: job={0}; live retained PIDs={1}; locks absent={2}" -f $OwnJob, ($liveIds -join ','), $locksAbsent)
            $nextProgress = [DateTime]::UtcNow.AddSeconds(30)
        }
        Start-Sleep -Seconds 10
    }
    throw 'Timed out observing natural exit; no status/submit/kill/repair was attempted'
}
function Queue-Command([string[]]$Arguments, [string]$CapturePath) {
    # Preserve the official failure receipt even if another helper source changed.
    # Never execute a changed queue CLI to obtain it.
    if ((Get-FileHash -LiteralPath $deriveQueue -Algorithm SHA256).Hash.ToLowerInvariant() -cne $deriveBefore[$deriveQueue]) {
        throw 'Installed queue source changed; no further queue call permitted'
    }
    $stderrPath = Join-Path $OutputRoot ([IO.Path]::GetFileName($CapturePath) + '.stderr.txt')
    $text = (& $derivePython -X utf8 -B $deriveQueue @Arguments 2> $stderrPath | Out-String)
    $exitCode = $LASTEXITCODE
    Write-New $CapturePath $text
    if ($exitCode -ne 0) { throw "Queue CLI failed ($exitCode); capture: $CapturePath" }
    return ($text | ConvertFrom-Json)
}
function Run-Derivation([string]$Name, [string]$Script, [string[]]$Arguments) {
    [void](Wait-Idle)
    Assert-Sources
    $command = @($derivePython, '-X', 'utf8', '-B', $Script) + $Arguments
    $submitArgs = @('submit','--project','LLMs-in-Robotics','--cwd',$deriveProject,'--') + $command
    $submitted = Queue-Command $submitArgs (Join-Path $OutputRoot ($Name + '-submission.json'))
    if ($submitted.id -notmatch '^\d{8}T\d{12}Z-[a-f0-9]{8}$') { throw 'Unexpected submitted job ID' }
    Assert-Job $submitted $submitted.id $command
    Write-Host "$Name submitted: $($submitted.id)"
    $terminal = Wait-Idle $submitted.id $command
    $receiptPath = Join-Path $deriveReceipts ($submitted.id + '.json')
    $official = Queue-Command @('status',$submitted.id) $receiptPath
    Assert-Job $official $submitted.id $command
    foreach ($key in @('state','worker_pid','child_pid','started_at','ended_at','exit_status')) {
        if ($official.$key -cne $terminal.$key) { throw "Official receipt changed: $key" }
    }
    Assert-Sources
    if ($official.state -cne 'succeeded' -or $null -eq $official.exit_status -or $official.exit_status -ne 0) {
        throw "$Name failed; official receipt retained at $receiptPath"
    }
    Write-Host "$Name completed: $($official.id)"
    return $receiptPath
}

$Screen = Full-Local $Screen
$ScreenReceipt = Full-Local $ScreenReceipt
$deriveAllowed = Full-Local 'D:\CodexEvidence\LLMs-in-Robotics'
$OutputRoot = Full-Local (Join-Path $deriveAllowed ('recovery-final-derivation-' + $Suffix))
if (-not $OutputRoot.StartsWith($deriveAllowed + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $OutputRoot -ieq $Screen -or $OutputRoot.StartsWith($Screen+'\', [StringComparison]::OrdinalIgnoreCase) -or
    $Screen.StartsWith($OutputRoot+'\', [StringComparison]::OrdinalIgnoreCase) -or
    $ScreenReceipt.StartsWith($OutputRoot+'\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Fresh output must be under the D-drive evidence root and separate from the screen/receipt'
}
if (Test-Path -LiteralPath $OutputRoot) { throw 'Output root already exists; no automatic resume or overwrite' }
$screenTerminal = Read-Json $ScreenReceipt
if ($screenTerminal.state -cne 'succeeded' -or $null -eq $screenTerminal.exit_status -or $screenTerminal.exit_status -ne 0) {
    throw 'Completed official succeeded/0 screen receipt required'
}
$script:derivePrecedingPids = @()
foreach ($value in @($screenTerminal.worker_pid, $screenTerminal.child_pid)) {
    if (($value -isnot [int] -and $value -isnot [long]) -or $value -le 0) { throw 'Screen receipt lacks valid worker/child PID identity' }
    $script:derivePrecedingPids += [int]$value
}
$deriveExtractor = Join-Path $deriveExperiment 'Batch 01\Recovery Qualification\extract_screen.py'
$deriveCompact = Join-Path $PSScriptRoot 'compact_construction_corridors.py'
$deriveTools = Join-Path $deriveExperiment 'Batch 01\Restart Qualification Tools'
$deriveBundle = Join-Path $deriveTools 'bundle_construction.py'
$deriveSources = @($PSCommandPath,$deriveQueue,$deriveExtractor,$deriveCompact,$deriveBundle,
    (Join-Path $deriveTools 'assess_validation.py'),(Join-Path $deriveTools 'compatibility.py'),
    (Join-Path $deriveExperiment 'Runtime\release_runner.py'),$ScreenReceipt)
$deriveBefore = Sources
$deriveOutputs = [ordered]@{
    extract = Join-Path $deriveAllowed ('recovery-final-construction-extraction-' + $Suffix)
    'compact-parking1' = Join-Path $deriveAllowed ('recovery-final-compact-parking1-' + $Suffix)
    'compact-parking2' = Join-Path $deriveAllowed ('recovery-final-compact-parking2-' + $Suffix)
    'dossier-parking1' = Join-Path $deriveAllowed ('recovery-final-construction-dossier-parking1-' + $Suffix)
    'dossier-parking2' = Join-Path $deriveAllowed ('recovery-final-construction-dossier-parking2-' + $Suffix)
}
foreach ($path in $deriveOutputs.Values) {
    [void](Full-Local $path)
    if (Test-Path -LiteralPath $path) { throw "Derived output already exists: $path" }
}
[void](Wait-Idle)
[void][IO.Directory]::CreateDirectory($OutputRoot)
$deriveReceipts = Join-Path $deriveExperiment 'Evidence\queue-receipts'
if (-not (Test-Path -LiteralPath $deriveReceipts -PathType Container)) { throw 'Existing official receipt directory required' }
Write-New (Join-Path $OutputRoot 'sources-before.json') (($deriveBefore | ConvertTo-Json -Depth 6) + "`n")
$deriveResults = [ordered]@{}
try {
    $extraction = $deriveOutputs['extract']
    $extractReceipt = Run-Derivation 'extract' $deriveExtractor @('--screen',$Screen,'--queue-receipt',$ScreenReceipt,'--output',$extraction)
    $deriveResults['extract'] = $extractReceipt
    $extractionJson = Join-Path $extraction 'extraction.json'
    foreach ($destination in @('parking1','parking2')) {
        $name = 'compact-' + $destination
        $deriveResults[$name] = Run-Derivation $name $deriveCompact @('--construction-extraction',$extractionJson,
            '--screen-receipt',$ScreenReceipt,'--extraction-receipt',$extractReceipt,
            '--destination',$destination,'--output',$deriveOutputs[$name])
    }
    foreach ($destination in @('parking1','parking2')) {
        $name = 'dossier-' + $destination
        $deriveResults[$name] = Run-Derivation $name $deriveBundle @('--construction-extraction',$extractionJson,
            '--destination',$destination,'--output',$deriveOutputs[$name])
    }
    Assert-Sources
    Write-New (Join-Path $OutputRoot 'coordinator-complete.json') (([ordered]@{
        schema_version='construction-derivation-coordinator-1'; completed_at=[DateTime]::UtcNow.ToString('o');
        screen=$Screen; screen_receipt=$ScreenReceipt; official_receipts=$deriveResults; outputs=$deriveOutputs;
        sources_before=$deriveBefore; sources_after=(Sources); qualification_granted=$false;
        scope='Five official successful queue jobs; inspect derivative completeness, blockers and unknowns separately'
    } | ConvertTo-Json -Depth 8) + "`n")
} catch {
    Write-New (Join-Path $OutputRoot 'coordinator-stopped.json') (([ordered]@{
        stopped_at=[DateTime]::UtcNow.ToString('o'); error=$_.Exception.Message;
        completed_receipts=$deriveResults; no_cancellation_or_repair_attempted=$true
    } | ConvertTo-Json -Depth 6) + "`n")
    throw
}
