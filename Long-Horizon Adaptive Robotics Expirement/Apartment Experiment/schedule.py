"""Protected matched assignment schedule. Never imported or mounted by Robot Codex."""
import argparse
import hashlib
import random
from pathlib import Path
from common import canonical, save, read

def build(seed):
    rng = random.Random(seed)
    kinds = ['bedroom', 'kitchen', 'throwing'] * 7
    rng.shuffle(kinds)
    kitchen_drawers=['A']*3+['B']*4;rng.shuffle(kitchen_drawers)
    assignments = []
    for position, kind in enumerate(kinds):
        # Every potential object position has a wide approach corridor and no occluder.
        slots = [(2.5, 6.0), (3.4, 6.4), (4.3, 6.0), (4.6, 7.1), (3.2, 7.4), (2.4, 7.4)]
        rng.shuffle(slots)
        assignments.append(dict(position=position, kind=kind, drawer=kitchen_drawers.pop() if kind=='kitchen' else 'A',
                                toys=[[x + rng.uniform(-.12, .12), y + rng.uniform(-.12, .12)] for x, y in slots[:4]],
                                sensor_seed=rng.randrange(2**31)))
    return dict(schema='apartment-schedule-1', seed=seed, assignments=assignments)

def validate(value):
    assert value['schema'] == 'apartment-schedule-1'
    rows = value['assignments']
    assert len(rows) == 21 and [x['position'] for x in rows] == list(range(21))
    assert all(sum(x['kind'] == kind for x in rows) == 7 for kind in ('bedroom', 'kitchen', 'throwing'))
    assert all(x['drawer'] in ('A', 'B') and len(x['toys']) == 4 for x in rows)
    return hashlib.sha256(canonical(value)).hexdigest()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--seed', type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to replace an existing schedule')
    value = build(args.seed)
    validate(value)
    save(args.output, value)
