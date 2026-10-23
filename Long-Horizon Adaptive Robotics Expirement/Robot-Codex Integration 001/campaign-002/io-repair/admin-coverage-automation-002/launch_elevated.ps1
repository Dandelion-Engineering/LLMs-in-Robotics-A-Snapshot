$ErrorActionPreference = 'Stop'
$taskPython = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\venv\Scripts\python.exe'
$taskHelper = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Robot-Codex Integration 001\campaign-002\io-repair\admin-coverage-automation-002\run_coverage.py'
$taskOutput = 'C:\Users\cresp\Documents\Campaign002 TCP Trace\coverage-managed-20260929-001'
$taskBinding = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Robot-Codex Integration 001\campaign-002\io-repair\admin-coverage-automation-002\launch-source-manifest-001.json'
$taskArgs = @('-X','utf8','-B', ('"' + $taskHelper + '"'), '--output', ('"' + $taskOutput + '"'), '--source-manifest', ('"' + $taskBinding + '"'))
$taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArgs -Verb RunAs -WindowStyle Hidden -PassThru
$taskReceipt = [ordered]@{ launchedPid = $taskProcess.Id; launchedAt = [DateTime]::UtcNow.ToString("o"); output = $taskOutput; sourceManifest = $taskBinding; windowStyle = "Hidden"; operation = "One bounded synthetic coverage helper" }
$taskReceipt | ConvertTo-Json | Set-Content -LiteralPath 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Robot-Codex Integration 001\campaign-002\io-repair\admin-coverage-automation-002\elevation-launch-receipt.json' -Encoding utf8
$taskReceipt | ConvertTo-Json
