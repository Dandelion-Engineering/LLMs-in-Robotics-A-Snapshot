from attempts import register
register('qualification003','qualify_workspace.py',
    'Qualify the complete matrix after correcting the proc stat/cmdline exit race exposed during qualification002 cleanup. Empty exiting cmdline remains alive until absence or zombie is observed.',
    ['same fixed matrix as qualification001','same bounded deadlines and all evidence gates','original failures preserved'],prior='APARTMENT-s38-qualification002')
