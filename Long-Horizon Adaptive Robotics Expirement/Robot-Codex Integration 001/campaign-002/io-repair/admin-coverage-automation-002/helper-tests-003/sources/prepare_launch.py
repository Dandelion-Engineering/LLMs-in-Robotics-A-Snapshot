"""Prepare one exact UAC launch after source-bound local checks; never elevates."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import run_coverage as runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tests', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads((args.tests/'receipt.json').read_text(encoding='utf-8'))
    if receipt['passed'] is not True or receipt['tests'] < 12 or receipt['failures'] or receipt['errors']:
        raise RuntimeError('Complete local helper checks are required')
    sources = {'run_coverage.py': runner.HERE/'run_coverage.py',
               'owned_process.py': runner.HERE/'owned_process.py', 'coverage_fixture.py': runner.FIXTURE}
    hashes = {name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sources.items()}
    if any(receipt['sources'][name] != value for name,value in hashes.items()):
        raise RuntimeError('Helper sources changed after tests')
    output = runner.validate_output(args.output)
    binding = runner.HERE/'launch-source-manifest-001.json'
    runner.save(binding, {'output':str(output), 'sources':hashes, 'model_calls':0,
        'test_receipt':str((args.tests/'receipt.json').resolve()),
        'test_receipt_sha256':hashlib.sha256((args.tests/'receipt.json').read_bytes()).hexdigest(),
        'scope':'One synthetic FIN/RST coverage collection; no model and no qualification promotion.'})
    def ps_quote(value):
        return "'"+str(value).replace("'", "''")+"'"
    script = '\n'.join([
        "$ErrorActionPreference = 'Stop'",
        '$taskPython = '+ps_quote(runner.PYTHON),
        '$taskHelper = '+ps_quote(runner.HERE/'run_coverage.py'),
        '$taskOutput = '+ps_quote(output),
        '$taskBinding = '+ps_quote(binding),
        "$taskArgs = @('-X','utf8','-B', ('\"' + $taskHelper + '\"'), '--output', ('\"' + $taskOutput + '\"'), '--source-manifest', ('\"' + $taskBinding + '\"'))",
        '$taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArgs -Verb RunAs -WindowStyle Hidden -PassThru',
        '$taskReceipt = [ordered]@{ launchedPid = $taskProcess.Id; launchedAt = [DateTime]::UtcNow.ToString("o"); output = $taskOutput; sourceManifest = $taskBinding; windowStyle = "Hidden"; operation = "One bounded synthetic coverage helper" }',
        '$taskReceipt | ConvertTo-Json | Set-Content -LiteralPath '+ps_quote(runner.HERE/'elevation-launch-receipt.json')+' -Encoding utf8',
        '$taskReceipt | ConvertTo-Json',
        ''
    ])
    with (runner.HERE/'launch_elevated.ps1').open('x', encoding='utf-8') as stream:
        stream.write(script)
    print(json.dumps({'prepared':True, 'output':str(output), 'script':str(runner.HERE/'launch_elevated.ps1'), 'sources':hashes}, indent=2))


if __name__ == '__main__':
    main()
