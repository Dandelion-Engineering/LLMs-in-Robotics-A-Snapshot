$ErrorActionPreference = 'Stop'
$taskRepo = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$taskIo = Join-Path $taskRepo 'Long-Horizon Adaptive Robotics Expirement\Robot-Codex Integration 001\campaign-002\io-repair'
$taskPrepared = Join-Path $taskIo 'admin-coverage-automation-002'
$taskPacket = Join-Path $taskIo 'admin-coverage-resumption-001'
$taskManifestPath = Join-Path $taskPrepared 'launch-source-manifest-001.json'
$taskManifest = Get-Content -LiteralPath $taskManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$taskAttemptPath = Join-Path $taskPacket 'elevation-attempt-002.json'
$taskPreflightPath = Join-Path $taskPacket 'preflight-001.json'
$taskLauncher = Join-Path $taskPrepared 'launch_elevated.ps1'
foreach ($taskAbsent in @($taskManifest.output, $taskAttemptPath, $taskPreflightPath, (Join-Path $taskPrepared 'elevation-launch-receipt.json'))) {
    if (Test-Path -LiteralPath $taskAbsent) { throw "Required fresh path exists: $taskAbsent" }
}
$taskChecks = @()
foreach ($taskSource in $taskManifest.sources.PSObject.Properties) {
    $taskSourcePath = if ($taskSource.Name -eq 'coverage_fixture.py') {
        Join-Path $taskIo 'smoke027-os-trace-readiness-001\coverage_fixture.py'
    } else { Join-Path $taskPrepared $taskSource.Name }
    $taskActualHash = (Get-FileHash -LiteralPath $taskSourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($taskActualHash -ne $taskSource.Value) { throw "Source binding mismatch: $($taskSource.Name)" }
    $taskChecks += [ordered]@{ path = $taskSourcePath; sha256 = $taskActualHash; expected = $taskSource.Value; matches = $true }
}
$taskTestHash = (Get-FileHash -LiteralPath $taskManifest.test_receipt -Algorithm SHA256).Hash.ToLowerInvariant()
if ($taskTestHash -ne $taskManifest.test_receipt_sha256) { throw 'Test receipt binding mismatch' }
$taskPreflight = [ordered]@{
    verifiedAtUtc = [DateTime]::UtcNow.ToString('o')
    authorization = 'Randy project chat 2026-09-29 20:21 PDT: exact prepared one-shot RunAs/UAC helper'
    sources = $taskChecks
    testReceiptSha256 = $taskTestHash
    manifestSha256 = (Get-FileHash -LiteralPath $taskManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    exactLauncherSha256 = (Get-FileHash -LiteralPath $taskLauncher -Algorithm SHA256).Hash.ToLowerInvariant()
    priorElevationAttemptSha256 = (Get-FileHash -LiteralPath (Join-Path $taskPrepared 'elevation-attempt-001.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    output = $taskManifest.output
    outputAbsent = $true
    modelCalls = 0
}
$taskPreflight | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $taskPreflightPath -Encoding UTF8
$taskPreflight | ConvertTo-Json -Depth 10
$taskAttempt = [ordered]@{ startedAtUtc = [DateTime]::UtcNow.ToString('o'); launchReturned = $false; helperExitCode = $null; modelCalls = 0 }
$taskWrapperExit = 1
try {
    # Execute the exact, unchanged Session17 launcher in this scope so its
    # retained process handle can supply the real elevated process exit code.
    . $taskLauncher
    $taskAttempt.launchReturned = $true
    $taskAttempt.launchedPid = $taskProcess.Id
    $taskAttempt.processExitedWithinFirst60Seconds = $taskProcess.WaitForExit(60000)
    if ($taskAttempt.processExitedWithinFirst60Seconds) {
        $taskAttempt.helperExitCode = $taskProcess.ExitCode
        $taskWrapperExit = $taskProcess.ExitCode
    }
} catch {
    $taskAttempt.windowsMessage = $_.Exception.Message
    $taskAttempt.exceptionType = $_.Exception.GetType().FullName
} finally {
    $taskAttempt.observedAtUtc = [DateTime]::UtcNow.ToString('o')
    $taskAttempt.launchReceiptExists = Test-Path -LiteralPath (Join-Path $taskPrepared 'elevation-launch-receipt.json')
    $taskAttempt.intendedOutputExists = Test-Path -LiteralPath $taskManifest.output
    $taskAttempt.terminalReceiptExists = Test-Path -LiteralPath (Join-Path $taskManifest.output 'receipt.json')
    $taskAttempt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $taskAttemptPath -Encoding UTF8
    $taskAttempt | ConvertTo-Json -Depth 10
}
exit $taskWrapperExit
