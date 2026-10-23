"""Optional, closed-prefix protected-canary JSON readback proof.

This is deliberately not a Python purity analyser. Accepted preceding programs
are exact reviewed ASTs or literal utility/GET recipes. Unknown execution or a
missing source/restore/lifecycle join abstains. A writable sidecar never proves
the protected child's exit. No historical assessment is changed by this reader.
"""
from __future__ import annotations

import ast
import base64
import json
import io
from pathlib import Path, PurePosixPath
import re
import shlex
import tokenize
import zipfile

from canary_exit_proof import check_document, fixture_proof, retained_file, source_proof
from completion_chronology import completion_chronology, finite_time, terminal_process_order
from empty_startup_reads import environment_proof, load_json, require, unique_object
from retained_reads import canonical, load_capture, sha
from transport_integrity import retirement_integrity

SCHEMA = 'campaign002-canary-readback-exclusivity-1'
PROOF_SCOPE = ('Source-bound protected 45 check values and actual complete semantic JSON readback; '
               'not independent redirected stdout bytes, protected child exit, or model attention.')
SOURCE_HASHES = {
    'campaign-002/harness/physical.py': 'e20030568bd5d0905092a1e76f38386e6bd463541b5ff291083867e5ec9da572',
    'campaign-002/harness/runtime.py': 'fac550bdd92e1ee35c98d21029408522c07ac8e956bdda24b8c5d4615c3d473b',
    'campaign-002/harness/executor_capture.py': '453e718d2391330f921d0123a779a5cf4e27b4013bf11485fb747df82eacf833',
    'readiness-session-10/boundary/runtime_layout.py': '525fb8ce15d3ba2cc7aa82e4aefdbbc5e43b2a09e16a8fd329268366babe1457',
    'readiness-session-10/boundary/namespace.py': '027d5ef394906ef1885b8ae8a2376031aae48ce93efe9bb90f2dc3ef9000c0f9',
    'readiness-session-10/boundary/inside.py': '6b6745e449348913e542d82aeb8b45320b6f50312540c235a3b07a66dc64faa3',
    'readiness-session-10/boundary/linux_entry.py': '785a09a92bd3c8b28e5403fa993d98725d61359e34132534b4ddc6500b3a0fb3',
    'readiness-session-10/boundary/retirement.py': 'feaa2c2ac62ce3b1950a2f52298ae64180e70c468e45727586e10dcd07ce4151',
    'readiness-session-10/boundary/unix_broker.py': '1af32d59e926053c1b8f7a90e971bd800cf02e593930083b2939b587279df97a',
    'readiness-session-10/boundary/gateway_policy.py': 'fbdef33d3753ed2cc0d92a7dc3318267237abf6c001d1fee22341197d013bb76',
    'readiness-session-10/boundary/canary.py': 'ec83d904415be556edfe2e9647903f46363908c17207058d1832586a6d2b7fa9',
    'readiness-session-10/boundary/codehost_canary.py': 'a9ed7d61cd37eb819c873cbf25c8cae69e5749c431e20e569fdb9a34c068ac16',
    'isolation-session-9/wsl/qualification.py': 'b2b67c596ea7ebf0a67b49899933b9cbf76f37b8341b46d5e118ce2b6e9b3f99',
    'runtime-template/robot.py': 'fd41a4e30df89bd8572e9fe553000eda404ef2c1e3ee5f397e2fd35fc232ee7d',
}
MAX_PROCESSES = 128
MAX_EVENTS = 20000
MAX_STREAM = 4 * 1024 * 1024
REVIEWED_RUNTIME_HASHES = {SOURCE_HASHES['campaign-002/harness/runtime.py'],
    '45e8d2e7c61ce49479632eba33554cf898adaef5c585cfea9ecd5f44d2d80307',
    '80b393d8f539e91bb7c202478372aa212274cc3773307efbc5e5fe3faf378bd5',
    'a11c34ca49cae7077d6088f3db3806b0e1550acd2ee5ea3a38ac4ef1556b04b0'}
FIXED_CANARY_PATHS = {'notes/canary-write.txt', 'notes/canary-public.tmp',
                      'notes/escape-link', 'notes/executor-canary.txt'}


def json_document(raw):
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def ordinary_path(name, *, notes=False):
    require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', name)
            and all(p not in ('.', '..') for p in name.split('/')),
            'Nonliteral/aliased workspace path')
    require(not notes or name.startswith('notes/'), 'Readback path is not a notes descendant')
    return name


def disjoint(paths):
    values = list(paths)
    require(len(values) == len(set(values)), 'Duplicate/aliased file path')
    require(all(not (a.startswith(b + '/') or b.startswith(a + '/'))
                for i, a in enumerate(values) for b in values[i+1:]), 'File/directory alias')


def python_ast(source):
    # Native stdin Python decodes its bytes before parsing. An encoding cookie
    # inside a comment could otherwise give the native interpreter different
    # code than ast.parse(str). These reviewed forms contain no comments.
    try:
        require(not any(t.type==tokenize.COMMENT for t in tokenize.generate_tokens(io.StringIO(source).readline)),
                'Python comments/encoding cookies are unsupported')
        return ast.parse(source)
    except (tokenize.TokenError, SyntaxError, IndentationError) as error:
        raise ValueError('Malformed Python heredoc') from error


def readback_recipe(argv):
    if not isinstance(argv, list) or argv[:2] != ['/usr/bin/bash', '-lc'] or len(argv) != 3:
        return None
    m = re.fullmatch(r"python3 /canary\.py > (notes/[A-Za-z0-9_./-]+)\ncanary_exit=\$\?\n"
                     r"python3 -B - \"\$canary_exit\" <<'PY'\n(.+)\nPY", argv[2], re.S)
    if not m:
        return None
    target, body = m.groups()
    ordinary_path(target, notes=True)
    try:
        tree = python_ast(body)
        require(len(tree.body) == 6, 'Readback AST statement count differs')
        sidecar = tree.body[4].value.func.value.args[0].value
        ordinary_path(sidecar, notes=True)
        expected = ("import json,sys\nfrom pathlib import Path\n"
                    f"p=Path({target!r})\nr=json.loads(p.read_text())\n"
                    f"Path({sidecar!r}).write_text(json.dumps({{'exit_code':int(sys.argv[1]),'output_file':str(p)}},indent=2)+'\\n')\n"
                    "print(json.dumps(r,indent=2))")
        require(ast.dump(tree) == ast.dump(ast.parse(expected)), 'Unreviewed readback AST/dataflow')
        disjoint([target, sidecar])
        require(not ({target, sidecar} & FIXED_CANARY_PATHS), 'Readback aliases trusted probe writes')
        return {'form': 'protected_redirect_status_capture_exact_json_readback',
                'output': target, 'sidecar': sidecar, 'ast_sha256': sha(ast.dump(tree).encode())}
    except (SyntaxError, AttributeError, IndexError, TypeError) as error:
        raise ValueError('Unreviewed readback AST') from error


# Each body is independently reviewed for ordinary JSON values only. These are
# complete ASTs; adding a statement, import, callback, dynamic path or write is
# unsupported. No operation is executed by this assessor.
READ_ONLY_BODIES = (('', "import json\ns=json.load(open('live/state.json'))\nprint(json.dumps({k:v for k,v in s.items() if k not in ('commands_recent',)},indent=2))"), ('python3 -B robot.py status > notes/resume-startup-status.json\n', "import json\ns=json.load(open('notes/resume-startup-status.json'))\np=s.get('packet',{})\nprint(json.dumps({**{k:s.get(k) for k in ('ok','owner','authority_epoch','order_version','invocation','active_command','observation_sequence','observation_age_s','history_high_water','robot_action_budget')},'packet':{k:p.get(k) for k in ('run_id','incarnation','restart_generation','capture_sim_time_s','sim_time','gripper','station','detections','joints','tcp_position_m')},'unresolved_commands':s.get('unresolved_commands')},indent=2))"), ('', "import json\nfrom pathlib import Path\nfor name in ['resume-history-interruption.json','smoke-history-startup.json']:\n h=json.load(open('notes/'+name))\n print(name, json.dumps({k:v for k,v in h.items() if k!='events'}))\n for e in h['events']:\n  p=e['payload']\n  if e['type']=='observation':\n   p={k:p.get(k) for k in ('sequence','capture_sim_time_s','incarnation','restart_generation','gripper','tcp_position_m','last_feedback')}\n  print(json.dumps({'event_id':e['event_id'],'type':e['type'],'epoch':e.get('authority_epoch'),'owner':e.get('owner'),'sim_time_s':e.get('sim_time_s'),'payload':p}))\nfor name in ['smoke-observation.json','smoke-open-preflight.json','boundary-observation.json','program-runs/b0b918879070-fb7cbe41d089.admitted.json']:\n d=json.load(open('notes/'+name))\n print(name)\n if 'status' in d and isinstance(d['status'],dict):\n  s=d['status']; p=s.get('packet',{})\n  d={**{k:v for k,v in d.items() if k!='status'},'status':{**{k:s.get(k) for k in ('owner','authority_epoch','order_version','invocation','observation_sequence')},'packet':{k:p.get(k) for k in ('gripper','joints','tcp_position_m','capture_sim_time_s','run_id')}}}\n print(json.dumps({k:v for k,v in d.items() if k not in ('source_base64','source_b64','packet','capture_packet','commands_recent')},indent=2))"))


def preceding_recipe(argv, forbidden):
    require(isinstance(argv, list) and len(argv) == 3 and argv[:2] == ['/usr/bin/bash', '-lc'],
            'Unsupported preceding interpreter')
    body = argv[2]
    require(isinstance(body, str) and len(body.encode()) <= 16384, 'Preceding script bound')
    for prefix, python_body in READ_ONLY_BODIES:
        head = prefix + "python3 -B - <<'PY'\n"
        if body.startswith(head) and body.endswith('\nPY'):
            source = body[len(head):-3]
            try:
                if ast.dump(python_ast(source)) != ast.dump(ast.parse(python_body)):
                    continue
            except SyntaxError as error:
                raise ValueError('Unsupported preceding Python AST') from error
            writes = [] if not prefix else ['notes/resume-startup-status.json']
            disjoint([*writes,*forbidden])
            return {'kind': 'reviewed_readonly_json_projection', 'writes': writes,
                    'ast_sha256': sha(ast.dump(ast.parse(source)).encode()), 'allowed_exit_codes': [0]}
    literal = {
        'ls -la /workspace',
        "pwd && rg --files -g 'RobotAgentPrompt.md' -g 'AGENTS.md' -g 'SKILL.md' -g '!node_modules' -g '!vendor' /workspace",
        'find /workspace -name AGENTS.md -o -name SKILL.md',
        "cat live/activation.json && find notes programs live -maxdepth 2 -type f -printf '%p\\n'",
    }
    if body in literal:
        return {'kind': 'literal_readonly_utility', 'writes': [],
                'allowed_exit_codes': [0, 127] if body.startswith('pwd && rg ') else [0]}
    robot = re.fullmatch(r'python3 -B robot\.py (query [A-Za-z0-9][A-Za-z0-9_.:-]{0,127}|'
                         r'history --after [0-9]+ --limit [0-9]+) > (notes/[A-Za-z0-9_./-]+)\ncat \2', body)
    if robot:
        path = ordinary_path(robot[2], notes=True)
        disjoint([path, *forbidden])
        if robot[1].startswith('history '):
            require(1 <= int(robot[1].split()[-1]) <= 200, 'Unbounded public history read')
        return {'kind': 'protected_robot_public_get_and_literal_readback', 'writes': [path],
                'allowed_exit_codes': [0]}
    # A fixed -n print range has no sed commands capable of execution/writes.
    lines = body.splitlines()
    require(1 <= len(lines) <= 2, 'Unsupported preceding shell composition')
    for index, line in enumerate(lines):
        tokens = shlex.split(line)
        if tokens[:1] == ['cat'] and len(tokens) > 1:
            require(all(re.fullmatch(r'(?:/workspace/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', p)
                        and all(s not in ('.','..') for s in p.removeprefix('/workspace/').split('/'))
                        for p in tokens[1:]), 'Nonliteral cat input')
            # Require a shell containing only those tokens, not escaped operators.
            require(not any(c in line for c in '$`;&|<>\\'), 'Unsupported cat shell operator')
        else:
            require(index == 1 and len(lines) == 2 and tokens == ['sed', '-n', '1,320p', 'robot.py'],
                    'Unsupported preceding utility')
    return {'kind': 'literal_readonly_file_projection', 'writes': [], 'allowed_exit_codes': [0]}


def wrapper_commands(script):
    """Two finite code-mode forms; no callbacks, filesystem API or other tool."""
    from prepared_result_segments import Wrapper
    import raw_tool_result_reads as raw
    p=Wrapper(script)
    def invocation():
        p.sequence('tools','.','exec_command','(','{'); options={}
        while not p.peek('}'):
            kind,key=p.pop()
            require(kind in ('name','string') and key in raw.OPTIONS and key not in options,
                    'Unknown/duplicate command option')
            p.pop(':');kind,value=p.pop()
            require(kind in ('string','integer') or kind=='name' and value in ('true','false'),
                    'Nonliteral command option')
            options[key]=(value=='true') if kind=='name' else value
            if not p.peek(','):break
            p.pop(',')
        p.sequence('}',')');raw.command_options(options,['/usr/bin/bash','-lc',options.get('cmd')])
        return options
    if p.peek('const'):
        p.pop();name=p.identifier();p.sequence('=','await','Promise','.','allSettled','(','[')
        commands=[invocation()]
        while p.peek(','):
            p.pop();commands.append(invocation());require(len(commands)<=8,'Wrapper child bound')
        p.sequence(']',')');p.semi();p.sequence('for','(','let');counter=p.identifier()
        require(name!=counter,'Wrapper variable alias')
        p.pop('=');require(p.pop()==('integer',0),'Wrapper loop must begin at zero')
        p.sequence(';',counter,'<',name,'.','length',';',counter,'++',')')
        p.print_object(counter,name,True);p.semi()
    else:
        p.sequence('text','(','await');commands=[invocation()];p.pop(')');p.semi()
    require(p.pos==len(p.items),'Additional code-mode statement')
    return commands


def app_prefix_census(events, candidate, processes):
    """Close model-side execution vocabulary and biject every wrapper child."""
    index=candidate['completion_index']
    selected_id=candidate['item_id']
    native={p['item_id']:p for p in processes if p['item_id']}
    seen={};calls={};outputs={}
    for i,event in enumerate(events):
        item=event.get('params',{}).get('item',{})
        if event.get('method') in ('item/started','item/completed') and item.get('type')=='commandExecution' and i<=index:
            require(item.get('id') in native,'Uncaptured app command')
            if event['method']=='item/started':
                require(item['id'] not in seen,'Duplicate app command')
                seen[item['id']]=i
        if event.get('method')!='rawResponseItem/completed':continue
        kind=item.get('type')
        if kind in ('custom_tool_call','function_call') and i<=index:
            require(kind=='custom_tool_call' and item.get('name')=='exec','Unreviewed model execution channel')
            identity=item.get('call_id');require(isinstance(identity,str) and identity not in calls,'Duplicate raw call')
            calls[identity]=(i,event,wrapper_commands(item.get('input')))
        elif kind in ('custom_tool_call_output','function_call_output'):
            identity=item.get('call_id')
            outputs.setdefault(identity,[]).append((i,event))
    require(set(seen)==set(native),'Native/app prefix census differs')
    matched=set();previous_end=-1;proof=[]
    for identity,(start,event,commands) in calls.items():
        matches=outputs.get(identity,[])
        require(len(matches)==1,'Unmatched/duplicate wrapper completion')
        stop,completed=matches[0]
        require(previous_end<start<stop,'Unfinished/overlapping code-mode execution')
        previous_end=stop
        require(all(event.get('params',{}).get(k)==completed.get('params',{}).get(k)
                    for k in ('threadId','turnId')),'Foreign wrapper completion')
        # The native wrapper emits its result only after allSettled resolves.
        body=completed['params']['item'].get('output')
        import raw_tool_result_reads as raw
        if isinstance(body,list):
            require(body and all(isinstance(x,dict) and set(x)=={'type','text'}
                    and x.get('type')=='input_text' and isinstance(x.get('text'),str) for x in body),
                    'Unknown wrapper output')
            body=body[0].get('text')
        require(isinstance(body,str) and raw.TERMINAL_CODE_HEADER.match(body),'Yielded/nonterminal wrapper')
        children=[p for p in native.values() if start<seen[p['item_id']]<=p['completion_index']<stop]
        require(len(children)==len(commands),'Hidden/extra/missing wrapper process')
        for options in commands:
            matches=[p for p in children if p['argv']==['/usr/bin/bash','-lc',options['cmd']]]
            require(len(matches)==1 and matches[0]['item_id'] not in matched,'Ambiguous wrapper/native signature')
            matched.add(matches[0]['item_id'])
        proof.append({'call_id':identity,'call_event_line':start+1,'completed_event_line':stop+1,
                      'script_sha256':sha(event['params']['item']['input'].encode()),
                      'process_ids':[p['item_id'] for p in children]})
    require(matched==set(native) and selected_id in matched,'Incomplete code-mode prefix coverage')
    return proof


def process_record(rows, delivered, request, events):
    """Complete process join including nonzero exits; never silently skip a start."""
    msg, p = request['message'], request['message']['params']
    pid = p.get('processId')
    require(isinstance(pid, str) and pid, 'Missing process identity')
    require(request.get('original_message_sha256') == request.get('retained_message_sha256'),
            'Redacted process request')
    require(sum(r.get('kind') == 'request' and r.get('message',{}).get('method') == 'process/start'
                and r['message']['params'].get('processId') == pid for r in rows) == 1, 'Reused process ID')
    starts = [r for r in rows if r.get('kind') == 'response' and r['message'].get('id') == msg.get('id')]
    require(len(starts) == 1 and starts[0]['message'].get('result',{}).get('processId') == pid
            and 'error' not in starts[0]['message'], 'Missing successful native start')
    stream = [r for r in rows if r.get('kind') == 'response'
              and r['message'].get('method') in ('process/output','process/exited','process/closed')
              and r['message'].get('params',{}).get('processId') == pid]
    ordering = terminal_process_order(stream)
    stdout, stderr = bytearray(), bytearray()
    for row in starts + stream:
        require(row['sequence'] > request['sequence'] and row['sequence'] in delivered
                and row.get('original_message_sha256') == row.get('retained_message_sha256'),
                'Missing/redacted/undelivered process record')
        obj = row['message']
        if obj.get('method') == 'process/output':
            params = obj['params']; raw = base64.b64decode(params['chunk'], validate=True)
            blobs = row.get('blobs', [])
            require(len(blobs) == 1 and blobs[0] == {'path':['params','chunk'],
                    'raw_sha256':sha(raw), 'retained_sha256':sha(raw),
                    'raw_bytes':len(raw), 'retained_bytes':len(raw)}, 'Incomplete/redacted process bytes')
            require(params.get('stream') in ('stdout','stderr'), 'Unknown native output stream')
            (stdout if params['stream']=='stdout' else stderr).extend(raw)
            require(len(stdout)+len(stderr) <= MAX_STREAM, 'Process stream bound exceeded')
    code = ordering['exit']['message']['params'].get('exitCode')
    require(type(code) is int, 'Missing genuine integer process exit')
    identity = (p.get('metadata') or {}).get('toolCallId')
    if identity:
        require(set(p) <= {'arg0','argv','cwd','env','envPolicy','metadata','pipeStdin','processId','sandbox','tty',
                          'enforceManagedNetwork','managedNetwork'}
                and p.get('sandbox') is None and set(p['metadata']) == {'threadId','toolCallId'},
                'Unreviewed native process option/metadata')
        require(p.get('managedNetwork') is None and p.get('enforceManagedNetwork',False) is False,
                'Unreviewed native managed network option')
        matches = [(i,e) for i,e in enumerate(events) if e.get('method') in ('item/started','item/completed')
                   and e.get('params',{}).get('item',{}).get('id') == identity]
        require([e['method'] for _,e in matches] == ['item/started','item/completed'],
                'Hidden/unmatched/duplicate model process')
        for _, event in matches:
            item = event['params']['item']
            require(item.get('type') == 'commandExecution' and shlex.split(item.get('command','')) == p['argv'],
                    'Actual native argv/tool identity differs')
            require(event['params'].get('threadId') == p['metadata'].get('threadId'), 'Foreign native thread')
        completed = matches[-1][1]; item = completed['params']['item']
        require(type(item.get('exitCode')) is int and item['exitCode'] == code
                and item.get('status') == ('completed' if code == 0 else 'failed'),
                'App exit/status differs or yielded')
        execution = environment_proof(p)
        execution.update(completion_chronology(rows, delivered, request, pid, completed.get('emittedAtMs')))
        completion_index = matches[-1][0]
    else:
        require(p == {'arg0':None,'argv':['/usr/bin/python3','-I','-B','/canary.py'],
                      'cwd':'file:///workspace','env':{'HOME':'/workspace','PATH':'/usr/bin:/bin'},
                      'processId':'canary','sandbox':None,'tty':False}, 'Unknown metadata-less process')
        require(code == 0 and not stderr, 'Trusted qualification canary failed')
        check_document(json_document(stdout))
        delivery = [r['wall_unix_s'] for r in rows if r.get('kind') == 'delivered'
                    and r.get('response_sequence') in [x['sequence'] for x in starts+stream]]
        require(request['wall_unix_s'] < ordering['closed']['wall_unix_s'] <= max(delivery), 'Probe chronology differs')
        execution = {'request_wall_unix_s': request['wall_unix_s'],
                     'evidence_complete_upper_wall_unix_s':max(delivery)}
        completion_index = None; item = None
    return {'item_id':identity, 'process_id':pid, 'argv':p['argv'], 'exit_code':code,
            'stdout':bytes(stdout), 'stderr':bytes(stderr), 'item':item,
            'completion_index':completion_index, 'execution':execution,
            'request_sequence':request['sequence'], 'closed_sequence':ordering['closed']['sequence']}


def reviewed_sources(source_zip, hashes, receipts):
    result = source_proof(source_zip, hashes, receipts)
    with zipfile.ZipFile(source_zip) as archive:
        for suffix, digest in SOURCE_HASHES.items():
            names = [n for n in archive.namelist() if n.endswith('/'+suffix)]
            require(len(names) == 1, 'Missing/ambiguous reviewed source: '+suffix)
            actual = sha(archive.read(names[0]))
            accepted = REVIEWED_RUNTIME_HASHES if suffix == 'campaign-002/harness/runtime.py' else {digest}
            require(actual in accepted, 'Changed reviewed exclusivity source: '+suffix)
            result.append({'path':names[0], 'sha256':actual})
        method='io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md'
        matches=[n for n in archive.namelist() if n.endswith('/campaign-002/'+method)]
        require(len(matches)==1 and sha(archive.read(matches[0]))==
                '80d7282dd18f6b599b0b3cc58fb216a7498f25a1c69bf4613eda3a30b9fe1892',
                'Declared exclusivity method absent/changed')
        result.append({'path':matches[0],'sha256':sha(archive.read(matches[0]))})
        for name in ('canary_readback_proof.py','canary_exit_proof.py','empty_startup_reads.py',
                     'completion_chronology.py','retained_reads.py','transport_integrity.py',
                     'prepared_result_segments.py','raw_tool_result_reads.py'):
            path=Path(__file__).with_name(name);raw=path.read_bytes()
            matches=[n for n in archive.namelist() if n.endswith('/campaign-002/assessment/'+name)]
            require(len(matches)==1 and archive.read(matches[0])==raw,
                    'Consumed readback helper absent/changed: '+name)
            result.append({'path':matches[0],'sha256':sha(raw),'bytes':len(raw)})
    require(hashes.get('robot.py') == SOURCE_HASHES['runtime-template/robot.py'], 'Workspace robot client differs')
    return result


def snapshot_files(snapshot):
    require(isinstance(snapshot,dict) and set(snapshot) == {'files','total_bytes','scope'}
            and snapshot['scope'] == 'actual file bytes; endpoint omitted'
            and isinstance(snapshot['files'],dict), 'Incomplete runtime snapshot')
    result = {}
    for name,item in snapshot['files'].items():
        ordinary_path(name)
        require(isinstance(item,dict) and set(item) == {'bytes','sha256','retained_sha256','base64'},
                'Snapshot file schema differs')
        raw = base64.b64decode(item['base64'],validate=True)
        require(type(item['bytes']) is int and item['bytes'] == len(raw)
                and item['sha256'] == item['retained_sha256'] == sha(raw), 'Redacted/changed restore bytes')
        result[name] = raw
    disjoint(result)
    require(type(snapshot['total_bytes']) is int and snapshot['total_bytes'] == sum(map(len,result.values())),
            'Snapshot total differs')
    return result


def retirement(root, location, receipts):
    captures = sorted(root.glob('executor-*-capture.jsonl'))
    require(captures and [p.name for p in captures] ==
            ['executor-'+str(i)+'-capture.jsonl' for i in range(1,len(captures)+1)],
            'Prior native executor history missing/noncontiguous')
    names = [p.name.replace('-capture.jsonl','-retirement.json') for p in captures]
    names.append('codehost-owner-retirement-v3.json')
    require({p.name for p in root.glob('*retirement*.json')} == set(names), 'Unmatched prior namespace retirement')
    result = []
    for name in names:
        value = load_json(root/name,receipts); retirement_integrity(value)
        require(value.get('identity_path','').startswith(location['run']+'/'), 'Foreign prior namespace identity')
        result.append({'file':name,'identity_path':value['identity_path'],
                       'final_observation':value['observations'][-1]})
    return result


def restoration_proof(root, hashes, target, sidecar, receipts):
    """Exact reviewed physical.py dispatch, not a fabricated direct restore receipt."""
    require(root.name == 'resume', 'Readback exclusivity currently requires fixed smoke resume dispatch')
    sequence = load_json(root.parent/'sequence-result.json',receipts)
    require(sequence.get('mode') == 'smoke' and sequence.get('orchestrator_completed') is True
            and type(sequence.get('host_exit_code')) is int and sequence['host_exit_code'] == 0
            and isinstance(sequence.get('stages'),list) and len(sequence['stages']) == 2,
            'Missing completed fixed smoke dispatch')
    previous_root = root.parent/'interrupt'
    first = load_json(previous_root/'stage-result.json',receipts)
    second = load_json(root/'stage-result.json',receipts)
    require(sequence['stages'] == [first,second] and first.get('kind') == 'interrupt'
            and second.get('kind') == 'resume' and first.get('invocation_id') != second.get('invocation_id'),
            'Restored stage dispatch/identity differs')
    require(all(first.get(k) is True for k in ('injected_interruption','durable_retention_verified',
                'old_token_denied_after_retirement','all_namespaces_retired','cleanup_clean')),
            'Prior stage did not pass fixed retirement gate')
    require(load_json(previous_root/'cleanup.json',receipts) == {'clean':True,'errors':[]},
            'Prior cleanup incomplete')
    old = load_json(previous_root/'runtime-location.json',receipts)
    new = load_json(root/'runtime-location.json',receipts)
    require(old['run'] != new['run'] and old['workspace'] == old['run']+'/workspace'
            and new['workspace'] == new['run']+'/workspace', 'Workspace was reused/aliased')
    retired = retirement(previous_root,old,receipts)
    before = load_json(previous_root/'runtime-before-close.json',receipts)
    after = load_json(previous_root/'runtime-after-close.json',receipts)
    require(before == after, 'Actual prior restore snapshot differs across cleanup')
    prior = snapshot_files(after)
    restored = {}
    for name,raw in prior.items():
        destination = 'notes/prior-local-continuity.md' if name == '.continuity/Continuity.md' else name
        if destination.startswith(('notes/','programs/')):
            require(destination not in restored, 'Aliased restore destinations')
            restored[destination] = {'sha256':sha(raw),'bytes':len(raw),'source':name}
    disjoint(restored)
    disjoint(set(hashes) | set(restored))
    require(target not in hashes and sidecar not in hashes and target not in restored and sidecar not in restored,
            'Readback paths were not fresh in complete setup plus actual restore')
    disjoint([target,sidecar,*set(hashes),*set(restored)-set(hashes)])
    require(new['run'].startswith('/var/tmp/robot-codex-session10/'), 'Unexpected fresh runtime root')
    return {'linkage':'source-derived exact physical.main smoke resume argument; not a captured restore payload',
            'prior_snapshot':str(previous_root/'runtime-after-close.json'),
            'prior_snapshot_sha256':sha((previous_root/'runtime-after-close.json').read_bytes()),
            'prior_invocation_id':first['invocation_id'],'invocation_id':second['invocation_id'],
            'prior_run':old['run'],'fresh_run':new['run'],'restored_files':restored,
            'target_initially_absent':True,'sidecar_initially_absent':True,
            'ordinary_files_recreated_by_reviewed_restore':True,'prior_retirement':retired}


def complete_census(root, events, end, receipts):
    paths = sorted(root.glob('executor-*-capture.jsonl'))
    require(1 <= len(paths) <= 16 and [p.name for p in paths] ==
            ['executor-'+str(i)+'-capture.jsonl' for i in range(1,len(paths)+1)],
            'Missing/noncontiguous executor connections')
    require({p.name for p in root.glob('executor-*-requests.jsonl')} ==
            {p.name.replace('-capture.jsonl','-requests.jsonl') for p in paths}, 'Uncaptured executor connection')
    processes, rpc_proof, connections = [], [], []
    for path in paths:
        rows, delivered, binding = load_capture(path)
        require(all(r.get('kind') in ('open','request','response','delivered','closed') for r in rows),
                'Unknown executor capture record')
        receipts.append({'path':str(path),'sha256':binding['sha256'],'bytes':path.stat().st_size})
        requests = [r for r in rows if r.get('kind') == 'request']
        raw_requests = load_json(path.with_name(path.name.replace('-capture.jsonl','-requests.jsonl')),receipts,lines=True)
        require([r['message'] for r in requests] == raw_requests, 'Executor request mirror/census differs')
        require(all(finite_time(a['wall_unix_s']) <= finite_time(b['wall_unix_s']) for a,b in zip(rows,rows[1:])),
                'Executor capture time regressed')
        request_ids = [r['message'].get('id') for r in requests if 'id' in r['message']]
        require(len(request_ids) == len(set(request_ids)), 'Reused RPC request ID')
        started = {r['message']['params'].get('processId') for r in requests
                   if r['message'].get('method') == 'process/start'}
        for row in rows:
            msg=row.get('message',{})
            if row['wall_unix_s']<=end and row.get('kind')=='response' and msg.get('method','').startswith('process/'):
                require(msg.get('method') in ('process/output','process/exited','process/closed')
                        and msg.get('params',{}).get('processId') in started,'Unmatched native process notification')
        for row in requests:
            if row['wall_unix_s'] > end:
                continue
            message = row['message']; method = message.get('method'); params = message.get('params')
            require(row.get('original_message_sha256') == row.get('retained_message_sha256'), 'Redacted prefix RPC')
            if 'id' in message:
                replies = [r for r in rows if r.get('kind') == 'response' and r['message'].get('id') == message['id']]
                require(len(replies) == 1 and replies[0]['sequence'] > row['sequence']
                        and replies[0]['sequence'] in delivered
                        and replies[0].get('original_message_sha256') == replies[0].get('retained_message_sha256'),
                        'Unmatched/redacted/undelivered prefix RPC')
            if method == 'process/start':
                record = process_record(rows,delivered,row,events)
                record.update(capture=path.name,connection_id=binding['connection_id'])
                processes.append(record)
                require(len(processes) <= MAX_PROCESSES, 'Process prefix bound exceeded')
            elif method == 'process/terminate':
                require(set(params) == {'processId'} and params['processId'] in started,
                        'Unknown process termination')
            elif method == 'fs/writeFile':
                require(binding['connection_id'] == '1' and params == {
                    'dataBase64':'c3ludGhldGljLXdyaXRlLW9ubHk=','followSymlinks':False,'sandbox':None,
                    'path':params.get('path')} and params['path'] in
                    ('file:///workspace/notes/executor-canary.txt','file:///workspace/Tools.md'),
                    'Unsupported native filesystem writer')
                reply = replies[0]['message']
                require((params['path'].endswith('Tools.md') and reply.get('error') ==
                        {'code':-32603,'message':'Read-only file system (os error 30)'})
                        or (params['path'].endswith('executor-canary.txt') and reply.get('result') == {}),
                        'Trusted probe write/denial differs')
            elif method in ('fs/getMetadata','fs/readFile'):
                require(isinstance(params,dict) and set(params) <= {'path','sandbox','followSymlinks'}
                        and isinstance(params.get('path'),str) and params.get('sandbox') is None,
                        'Unknown filesystem read mode')
            elif method == 'initialize':
                require(params in ({'clientName':'robot-codex-isolation-session9'},
                                   {'clientName':'codex-environment','resumeSessionId':None}), 'Unknown native initializer')
            elif method == 'initialized':
                require(params == {}, 'Unknown native initialization notification')
            elif method in ('environment/info','environment/status'):
                require(params is None, 'Unknown environment request')
            elif method == 'environmentConfig/read':
                require(params == {'configPaths':[['mcp_servers']],'cwd':'file:///workspace',
                                   'requirementsPaths':[['mcp_servers']]}, 'Unknown environment configuration read')
            else:
                raise ValueError('Unreviewed prefix RPC: '+str(method))
            rpc_proof.append({'capture':path.name,'sequence':row['sequence'],'method':method,
                              'request_sha256':row['retained_message_sha256']})
        if rows[0]['wall_unix_s'] <= end:
            connections.append(binding)
    identities = [p['item_id'] for p in processes if p['item_id']]
    require(len(identities) == len(set(identities)), 'Repeated cross-connection tool identity')
    return processes,rpc_proof,connections


def prefix_exclusive(processes, candidate):
    start = candidate['execution']['request_wall_unix_s']
    end = candidate['execution']['evidence_complete_upper_wall_unix_s']
    recipe = readback_recipe(candidate['argv']); forbidden=[recipe['output'],recipe['sidecar']]
    proof = []
    for process in processes:
        if process is candidate:
            continue
        require(process['execution']['evidence_complete_upper_wall_unix_s'] < start,
                'Earlier/in-flight/overlapping command can still write during readback')
        if process['item_id'] is None:
            semantic = {'kind':'source-bound trusted qualification canary','writes':sorted(FIXED_CANARY_PATHS),
                        'allowed_exit_codes':[0]}
        else:
            semantic = preceding_recipe(process['argv'],forbidden)
        require(process['exit_code'] in semantic['allowed_exit_codes'], 'Unreviewed prefix command exit')
        proof.append({'item_id':process['item_id'],'capture':process['capture'],
                      'process_id':process['process_id'],'argv_sha256':sha(canonical(process['argv'])),
                      'exit_code':process['exit_code'],'execution':process['execution'],'recipe':semantic})
    require(sum(p['item_id'] is None for p in processes) == 1, 'Missing/duplicate trusted qualification process')
    return {'complete_native_prefix':proof,'processes_including_candidate':len(processes),
            'nonzero_exit_count':sum(p['exit_code'] != 0 for p in processes),
            'candidate_interval':[start,end],'no_other_process_overlaps':True}


def canary_readback_evidence(root, source_zip):
    root = Path(root)
    audit = {'schema':SCHEMA,'verified':False,'evidence':[],'errors':[]}
    receipts = []
    try:
        hashes=load_json(root/'runtime-input-hashes.json',receipts)
        sources=reviewed_sources(source_zip,hashes,receipts)
        before=load_json(root/'runtime-before-close.json',receipts)
        after=load_json(root/'runtime-after-close.json',receipts)
        fixture=fixture_proof(root,hashes,before,after,receipts)
        events=load_json(root/'client/events.jsonl',receipts,lines=True)
        require(len(events) <= MAX_EVENTS,'Native event bound exceeded')
        candidates=[]
        for index,event in enumerate(events):
            item=event.get('params',{}).get('item',{})
            if event.get('method')=='item/completed' and item.get('type')=='commandExecution':
                argv=shlex.split(item.get('command',''))
                recipe=readback_recipe(argv)
                if recipe:
                    require(type(event.get('emittedAtMs')) is int,'Missing candidate native completion clock')
                    candidates.append((index,event,recipe))
        require(candidates,'No supported protected canary semantic-readback recipe')
        for index,event,recipe in candidates:
            try:
                item=event['params']['item']
                # First census uses app interval; actual delivery may extend the
                # conservative upper bound, so repeat with that bound if needed.
                end=(event['emittedAtMs']+1)/1000
                processes,rpcs,connections=complete_census(root,events,end,receipts)
                matches=[p for p in processes if p['item_id']==item['id']]
                require(len(matches)==1,'Missing/ambiguous candidate process')
                selected=matches[0]; upper=selected['execution']['evidence_complete_upper_wall_unix_s']
                if upper>end:
                    processes,rpcs,connections=complete_census(root,events,upper,receipts)
                    selected=next(p for p in processes if p['item_id']==item['id'])
                require(selected['exit_code']==0 and not selected['stderr'],'Readback wrapper failed or stderr is nonempty')
                require(item.get('aggregatedOutput')==selected['stdout'].decode('utf-8'), 'Incomplete actual app readback output')
                restoration=restoration_proof(root,hashes,recipe['output'],recipe['sidecar'],receipts)
                exclusive=prefix_exclusive(processes,selected)
                exclusive['code_mode_prefix']=app_prefix_census(events,selected,processes)
                note=retained_file(before,after,recipe['output'])
                actual=json_document(selected['stdout']); saved=json_document(note)
                checks=check_document(actual);check_document(saved)
                require(actual==saved,'Observed JSON differs from separately retained note')
                sidecar=retained_file(before,after,recipe['sidecar'])
                side=json_document(sidecar)
                require(side=={'exit_code':0,'output_file':recipe['output']}
                        and type(side['exit_code']) is int,'Execution sidecar corroboration differs')
                audit['evidence'].append({'item_id':item['id'],'file':recipe['output'],'recipe':recipe,
                    'saved_sha256':sha(note),'saved_bytes':len(note),
                    'actual_output_sha256':sha(selected['stdout']),'actual_output_bytes':len(selected['stdout']),
                    'canonical_json_sha256':sha(canonical(actual)),'check_values_sha256':sha(canonical(checks)),
                    'check_count':45,'semantic_json_equal':True,'byte_equal':note==selected['stdout'],
                    'protected_child_exit_independently_observed':False,'redirected_stdout_captured':False,
                    'sidecar_is_corroboration_only':True,'proof_scope':PROOF_SCOPE,
                    'source_identities':sources,'fixture':fixture,'restoration':restoration,
                    'exclusive_prefix':exclusive,'rpc_prefix':rpcs,'connections':connections,
                    'execution':selected['execution'],'inputs':receipts.copy()})
            except (ValueError,KeyError,TypeError,OSError,UnicodeError) as error:
                audit['errors'].append(str(item.get('id'))+': '+str(error))
        audit['verified']=bool(audit['evidence'])
    except (ValueError,KeyError,TypeError,OSError,UnicodeError,zipfile.BadZipFile) as error:
        audit['errors'].append(str(error))
    audit['inputs']=receipts
    return audit
