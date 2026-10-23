param([switch]$BoundedHostScopeAuthorized)
if (-not $BoundedHostScopeAuthorized) { throw 'Explicit Randy approval of bounded host scope is required; preparation does not authorize launch.' }
$ErrorActionPreference = 'Stop'
$taskHere = $PSScriptRoot
$taskManifestPath = Join-Path $taskHere 'launch-source-manifest-001.json'
$taskManifest = Get-Content -LiteralPath $taskManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$taskAttemptPath = Join-Path $taskHere 'elevation-attempt-001.json'
if ((Test-Path -LiteralPath $taskManifest.output) -or (Test-Path -LiteralPath $taskAttemptPath)) { throw 'Fresh output and launch-attempt paths required' }
foreach ($taskSource in $taskManifest.sourcePaths.PSObject.Properties) {
    $taskActualHash = (Get-FileHash -LiteralPath $taskSource.Value -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($taskActualHash -ne $taskManifest.sources.($taskSource.Name)) { throw "Source binding mismatch: $($taskSource.Name)" }
}
if ((Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskManifest.launcherSha256) { throw 'Launcher binding mismatch' }
if ((Get-FileHash -LiteralPath $taskManifest.testReceipt -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskManifest.testReceiptSha256) { throw 'Test receipt binding mismatch' }
$taskPython = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\venv\Scripts\python.exe'
$taskHelper = Join-Path $taskHere 'run_direct_coverage.py'
$taskArgs = @('-X','utf8','-B', ('"' + $taskHelper + '"'), '--output', ('"' + $taskManifest.output + '"'), '--source-manifest', ('"' + $taskManifestPath + '"'))
$taskAttempt = [ordered]@{ startedAtUtc = [DateTime]::UtcNow.ToString('o'); operation = 'One explicitly authorized bounded host-scope six-event closure diagnostic'; sourceBindingsVerified = $true; launchReturned = $false; helperExitCode = $null; modelCalls = 0 }
$taskWrapperExit = 1
try {
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArgs -Verb RunAs -WindowStyle Hidden -PassThru
    $taskAttempt.launchReturned = $true
    $taskAttempt.launchedPid = $taskProcess.Id
    $taskAttempt.launchedAtUtc = [DateTime]::UtcNow.ToString('o')
    $taskAttempt.exitedWithin60Seconds = $taskProcess.WaitForExit(60000)
    if ($taskAttempt.exitedWithin60Seconds) {
        $taskAttempt.helperExitCode = $taskProcess.ExitCode
        $taskWrapperExit = $taskProcess.ExitCode
    }
} catch {
    $taskAttempt.windowsMessage = $_.Exception.Message
    $taskAttempt.exceptionType = $_.Exception.GetType().FullName
} finally {
    $taskAttempt.observedAtUtc = [DateTime]::UtcNow.ToString('o')
    $taskAttempt.outputExists = Test-Path -LiteralPath $taskManifest.output
    $taskAttempt.terminalReceiptExists = Test-Path -LiteralPath (Join-Path $taskManifest.output 'receipt.json')
    $taskAttempt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $taskAttemptPath -Encoding UTF8
    $taskAttempt | ConvertTo-Json -Depth 10
}
exit $taskWrapperExit
