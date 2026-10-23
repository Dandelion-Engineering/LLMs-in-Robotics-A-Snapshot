param([switch]$DesktopAvailable)
if (-not $DesktopAvailable) { throw 'Randy requested deferral of UAC until a session when he is at the desktop.' }
$ErrorActionPreference = 'Stop'
$taskHere = $PSScriptRoot
$taskRoot = Join-Path (Split-Path $taskHere -Parent) 'shutdown-diagnostic-005'
$taskBinding = Get-Content -LiteralPath (Join-Path $taskRoot 'observer-preparation.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$taskControl = 'C:\Users\cresp\Documents\Campaign002 TCP Trace\native-closure-20260930-001'
if ($taskBinding.run -ne 'RCI001-C02-shutdown-diagnostic-005' -or $taskBinding.revision -ne 'RCI001-C02-dev-097' -or $taskBinding.control_root -cne $taskControl) { throw 'Fixed diagnostic identity differs' }
foreach ($taskSource in $taskBinding.sources.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath $taskSource.Name -Algorithm SHA256).Hash.ToLowerInvariant() -cne $taskSource.Value) { throw 'Observer source binding changed' }
}
if ($taskBinding.sources.($PSCommandPath) -cne (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()) { throw 'Launcher source binding missing or changed' }
if ((Get-FileHash -LiteralPath (Join-Path $taskControl 'config.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $taskBinding.config_sha256) { throw 'Observer config binding differs' }
if ((Get-ChildItem -LiteralPath $taskControl -Force).Count -ne 1) { throw 'Only the fresh configuration may exist before elevation' }
function Write-TaskExclusiveJson($taskPath, $taskValue) {
    $taskBytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($taskValue | ConvertTo-Json -Depth 10) + [Environment]::NewLine)
    $taskStream = [System.IO.File]::Open($taskPath,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::Read)
    try { $taskStream.Write($taskBytes,0,$taskBytes.Length); $taskStream.Flush($true) } finally { $taskStream.Dispose() }
}
$taskIntent = [ordered]@{ run = $taskBinding.run; revision = $taskBinding.revision; createdAtUtc = [DateTime]::UtcNow.ToString('o'); configSha256 = $taskBinding.config_sha256; operation = 'One bounded native closure observer; no model launched by helper'; desktopAvailable = $true }
Write-TaskExclusiveJson (Join-Path $taskRoot 'observer-elevation-intent.json') $taskIntent
$taskPython = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\venv\Scripts\python.exe'
$taskHelper = Join-Path $taskHere 'collect_window.py'
$taskArguments = @('-X','utf8','-B', ('"' + $taskHelper + '"'), '--control', ('"' + $taskControl + '"'), '--config-sha256', $taskBinding.config_sha256)
$taskReceipt = [ordered]@{ run = $taskBinding.run; launchReturned = $false; helperExitCode = $null; complete = $false }
$taskExit = 1
try {
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArguments -Verb RunAs -WindowStyle Hidden -PassThru
    $taskReceipt.launchReturned = $true
    $taskReceipt.pid = $taskProcess.Id
    Write-TaskExclusiveJson (Join-Path $taskRoot 'observer-launched.json') ([ordered]@{ pid = $taskProcess.Id; launchedAtUtc = [DateTime]::UtcNow.ToString('o'); configSha256 = $taskBinding.config_sha256 })
    Write-Output 'Observer launched; waiting for its own bounded completion. Separate queue launch requires authenticated helper readiness.'
    $taskDeadline = [DateTime]::UtcNow.AddSeconds(960)
    while (-not $taskProcess.WaitForExit(1000)) {
        if ([DateTime]::UtcNow -gt $taskDeadline) { throw 'Observer process exceeded its lifecycle wait; no foreign process or session was stopped' }
    }
    $taskReceipt.helperExitCode = $taskProcess.ExitCode
    $taskReceipt.complete = $true
    $taskExit = $taskProcess.ExitCode
} catch {
    $taskReceipt.error = $_.Exception.Message
    $taskReceipt.exceptionType = $_.Exception.GetType().FullName
} finally {
    $taskReceipt.observedAtUtc = [DateTime]::UtcNow.ToString('o')
    Write-TaskExclusiveJson (Join-Path $taskRoot 'observer-elevation-receipt.json') $taskReceipt
    $taskReceipt | ConvertTo-Json -Depth 10
}
exit $taskExit
