"""Closed literal syntax reader. No eval, exec, shell, imports or historical code execution."""
import ast
import re
import shlex
from pathlib import PurePosixPath


def workspace_path(value):
    value = value.removeprefix('file://').removeprefix('/workspace/')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Outside retained workspace')
    return str(p)


def python_literals(source, known):
    """Interpret only observed Path/read_text/string edits, never an executable Python language."""
    env, writes = {}, []

    def expression(node):
        if isinstance(node, ast.Constant) and type(node.value) in (str, int):
            return node.value
        if isinstance(node, ast.Name):
            return env[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            a, b = expression(node.left), expression(node.right)
            if type(a) is not str or type(b) is not str:
                raise ValueError('Only string concatenation')
            return a + b
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            if node.slice.step is not None:
                raise ValueError('No stride')
            return expression(node.value)[expression(node.slice.lower) if node.slice.lower else None:
                expression(node.slice.upper) if node.slice.upper else None]
        if isinstance(node, ast.Call) and not node.keywords:
            args = [expression(a) for a in node.args]
            if isinstance(node.func, ast.Name) and node.func.id == 'Path' and len(args) == 1:
                return ('path', workspace_path(args[0]))
            if isinstance(node.func, ast.Attribute):
                value, method = expression(node.func.value), node.func.attr
                if type(value) is tuple and method == 'read_text' and not args:
                    return known[value[1]].decode('utf-8')
                if type(value) is str and method in ('replace', 'index'):
                    if method == 'replace' and len(args) == 2:
                        return value.replace(*args)
                    if method == 'index' and len(args) == 1:
                        return value.index(*args)
        raise ValueError('Unsupported literal expression')

    for node in ast.parse(source).body:
        if isinstance(node, ast.ImportFrom) and node.module == 'pathlib' and [(a.name,a.asname) for a in node.names] == [('Path',None)]:
            continue  # Recognized syntax only; no import executes.
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0],ast.Name):
            env[node.targets[0].id] = expression(node.value)
        elif isinstance(node, ast.Assert):
            test = node.test
            if not (isinstance(test,ast.Compare) and len(test.ops)==1 and isinstance(test.ops[0],ast.In)
                    and expression(test.left) in expression(test.comparators[0])):
                raise ValueError('Unsupported or false retained assertion')
        elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='write_text':
            target = expression(node.value.func.value)
            if type(target) is not tuple or len(node.value.args)!=1 or node.value.keywords:
                raise ValueError('Unsupported write')
            raw = expression(node.value.args[0]).encode('utf-8')
            known[target[1]]=raw
            writes.append((target[1],raw,'literal_python_string_edit'))
        else:
            raise ValueError('Unsupported retained statement')
    return writes


def mutations(command, known):
    """Read a closed set of heredocs, literal cp/mv, sed substitutions and Path string edits."""
    writes, operations, gaps = [], [], []
    processed_sed=set()

    def sed_edit(line):
        tokens=shlex.split(line)
        if len(tokens)!=4:
            raise ValueError('Unsupported sed argument shape')
        path=workspace_path(tokens[3])
        if path not in known:
            gaps.append({'path':path,'reason':'Sed before-content unknown'})
            return
        text=known[path].decode('utf-8')
        deletion=re.fullmatch(r'/\^([^/]+)/d',tokens[2])
        if deletion:
            prefix=deletion.group(1)
            if re.search(r'[\[\]*\\.$]',prefix): raise ValueError('Nonliteral line-delete prefix')
            text=''.join(s for s in text.splitlines(keepends=True) if not s.startswith(prefix))
        else:
            for subst in re.split(r'(?<=/); (?=s/)',tokens[2]):
                match=re.fullmatch(r's/([^/]+)/([^/]*)/',subst)
                if not match: raise ValueError('Unsupported sed literal substitution')
                old,new=match.groups()
                if re.search(r'(?<!\\)[\[\]*^$]',old) or '\\' in old.replace('\\.','') or '\\' in new:
                    raise ValueError('Nonliteral sed expression')
                old=old.replace('\\.','.')
                text='\n'.join(s.replace(old,new,1) for s in text.split('\n'))
        known[path]=text.encode('utf-8')
        writes.append((path,known[path],'literal_sed_string_edit'))
    # Remove heredoc bodies before inspecting other command syntax.
    pattern = re.compile(r"cat\s+(>{1,2})\s+(\S+)\s+<<'([^']+)'\n([\s\S]*?)\n\3(?=\n|$)")
    pos = 0
    for m in pattern.finditer(command):
        # Literal copies before an append matter; process prefix without executing it.
        pre = command[pos:m.start()]
        for line in pre.splitlines():
            if line.startswith('sed -i '):
                sed_edit(line)
                processed_sed.add(line)
        for copy in re.finditer(r'\b(cp|mv) (notes/[^\s;&]+) (notes/[^\s;&]+)',pre):
            op, a, b = copy.groups()
            a,b=workspace_path(a),workspace_path(b)
            operations.append({'operation':op,'from':a,'to':b})
            if a in known:
                known[b]=known[a]
                writes.append((b,known[b],'literal_'+op))
                if op=='mv':
                    known.pop(a,None)
            else:
                gaps.append({'path':b,'reason':'Copy source content not independently retained at this point'})
        path=workspace_path(m.group(2))
        raw=(m.group(4)+'\n').encode('utf-8')
        if m.group(1)=='>>':
            if path not in known:
                gaps.append({'path':path,'reason':'Append before-content unknown; literal suffix retained in tool call'})
                pos=m.end()
                continue
            raw=known[path]+raw
        known[path]=raw
        writes.append((path,raw,'literal_heredoc_append' if m.group(1)=='>>' else 'literal_heredoc_write'))
        pos=m.end()
    cleaned=pattern.sub('[literal-heredoc]',command)
    for line in cleaned.splitlines():
        if line.startswith('sed -i ') and line not in processed_sed:
            sed_edit(line)
        if 'python3 -c ' in line and ('write_text' in line):
            tokens=shlex.split(line.split(' && ')[0])
            if tokens[:2]!=['python3','-c'] or len(tokens)!=3:
                raise ValueError('Unrecognized Python edit form')
            writes.extend(python_literals(tokens[2],known))
        if line.startswith(('cp ','mv ')):
            tokens=shlex.split(line.split(' && ')[0])
            if len(tokens)==3:
                a,b=map(workspace_path,tokens[1:])
                if any(o=={'operation':tokens[0],'from':a,'to':b} for o in operations): continue
                operations.append({'operation':tokens[0],'from':a,'to':b})
                if a in known:
                    known[b]=known[a]
                    if tokens[0]=='mv': known.pop(a)
                    writes.append((b,known[b],'literal_'+tokens[0]))
                else:
                    gaps.append({'path':b,'reason':'Rename source bytes unknown'})
    return writes,operations,gaps


def leading_reads(command):
    """Only leading cat commands; a transformed print is not exact file serialization."""
    result=[]
    for segment in re.split(r'\n|\s+&&\s+',command):
        if not segment.startswith('cat ') or '>' in segment or '|' in segment:
            break
        try:
            tokens=shlex.split(segment)
            result.extend(workspace_path(p) for p in tokens[1:] if not p.startswith('-'))
        except ValueError:
            break
    return result
