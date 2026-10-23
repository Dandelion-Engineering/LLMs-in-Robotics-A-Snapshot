"""Add per-path links to exact historical content; never edit evidence files."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from urllib.parse import quote

def main(root):
    manifest=json.loads((root/'manifest.json').read_bytes())
    versions=json.loads((root/'versions.json').read_bytes())
    for condition in ('baseline','maps'):
        views=[x for x in manifest['parts'] if x['parts'][0]['path'].startswith(condition+'/version-transitions/')]
        assert len(views)==1
        paths=defaultdict(list)
        for part in views[0]['parts']:
            for line in (root/part['path']).read_bytes().splitlines():
                row=json.loads(line);items=paths[row['path']]
                if not items or items[-1]['sha256']!=row['sha256']:items.append(row)
        folder=root/condition/'file-history';folder.mkdir(exist_ok=False)
        index=['# Historical versions by original path','',
          'Each link opens the exact bytes of a retained file version. The table identifies the first journal witness of that content transition. Repeated unchanged content carried into a later session is omitted here. Deletions, renames, all metadata and exact read events remain in the full session journals.','',
          '| Original path | Content transitions |','|---|---:|']
        for number,(path,rows) in enumerate(sorted(paths.items()),1):
            name=f'file-{number:04d}.md'
            index.append(f'| [{path}]({name}) | {len(rows)} |')
            body=[f'# {path}','', '[All paths](README.md)','',
              '| Session | Journal sequence | Exact content | Bytes |','|---|---:|---|---:|']
            for row in rows:
                target=versions[row['sha256']]['path']
                body.append(f'| [{row["session"]}](../history/{row["session"]}/README.md) | {row["sequence"]} | [{row["sha256"][:12]}](../../{target}) | {row["bytes"]:,} |')
            (folder/name).write_text('\n'.join(body)+'\n',encoding='utf-8')
        (folder/'README.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
        readme=root/condition/'README.md'
        with readme.open('a',encoding='utf-8') as f:f.write('\n## Browse a file across time\n\n[Historical versions by original path](file-history/README.md) provides direct links to each exact retained content version.\n')
    # Verify every local Markdown link in generated navigation, not historical guest text.
    import re
    from urllib.parse import unquote
    generated=[root/'README.md']
    for c in ('baseline','maps'):
        generated += [root/c/'README.md'] + list((root/c/'file-history').glob('*.md'))
        generated += list((root/c/'history').glob('*/README.md'))
    for p in generated:
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            assert (p.parent/unquote(target)).exists(),(p,target)
    print(json.dumps({'passed':True,'generated_navigation_files_checked':len(generated)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();main(a.root)
