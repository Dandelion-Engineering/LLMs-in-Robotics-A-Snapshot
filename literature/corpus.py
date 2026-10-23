"""Small standard-library lookup and derived-view generator for the robotics map.

Adapted from [private project name redacted]'s portable Vision 1.0 helpers; see
agents/Codex/research/tool-reference-notes.md for reference hashes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
PROFILE = 'llm-robotics-1.0'
CORE_VERSION = '1.0'
CATEGORIES = {
    'robotics_stack_architectures': 'Robotics stack architectures',
    'planning_reasoning_skills': 'Planning, reasoning and skills',
    'code_generation_tools': 'Code generation and tools',
    'perception_state_grounding': 'Perception, state and grounding',
    'memory_continuity': 'Memory and continuity',
    'closed_loop_adaptation': 'Closed-loop adaptation',
    'learning_and_skill_acquisition': 'Learning and skill acquisition',
    'embodiment_transfer': 'Embodiment transfer',
    'world_models_prediction': 'World models and prediction',
    'deployment_evaluation_safety': 'Deployment, evaluation and safety',
    'human_lab_assistance': 'Human and laboratory assistance',
    'neuroscience_cognitive_connections': 'Neuroscience and cognitive connections',
}
DEPTHS = {'discovered': 'D', 'abstract_reviewed': 'A', 'full_text_skimmed': 'S',
          'full_text_reviewed': 'F', 'deep_read': 'R'}
FIELDS = set('id identifier_aliases title authors authors_complete year venue doi url '
             'open_access_url categories tags paper_type review_status basis_for_summary '
             'central_idea efficiency_targets representation_or_method task_or_domain '
             'evidence_or_evaluation main_limitations project_relevance importance sources '
             'metadata_notes discovery_lane provenance_notes'.split())
SEARCH_FIELDS = set('search_id lane date source queries categories purpose phase '
                    'original_log original_record_number details'.split())
BEGIN = '<!-- BEGIN GENERATED CURRENT METRICS -->'
END = '<!-- END GENERATED CURRENT METRICS -->'


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate object key: {key}')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'non-JSON numeric constant: {value}')


def read_jsonl(path):
    """Return parsed objects and errors, including malformed physical lines."""
    path = Path(path)
    rows, errors = [], []
    try:
        raw = path.read_bytes()
        content = raw.decode('utf-8')
    except (OSError, UnicodeError) as exc:
        return [], [f'{path.name}: {exc}']
    if raw.startswith(b'\xef\xbb\xbf'):
        errors.append(f'{path.name}: UTF-8 BOM is not allowed')
    if raw and not content.endswith('\n'):
        errors.append(f'{path.name}: missing final newline')
    if '\ufffd' in content:
        errors.append(f'{path.name}: replacement character')
    for number, line in enumerate(content.splitlines(), 1):
        try:
            row = json.loads(line, object_pairs_hook=_unique_object,
                             parse_constant=_invalid_constant)
            if not isinstance(row, dict):
                raise ValueError('record must be an object')
            rows.append(row)
        except (ValueError, TypeError) as exc:
            errors.append(f'{path.name}:{number}: {exc}')
    return rows, errors


def normal_title(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold()
                   if c.isalnum())


def identity_tokens(value):
    """Normalize known identities; retain arbitrary stable IDs/aliases exactly."""
    if not isinstance(value, str) or not value.strip():
        return set()
    value = value.casefold().strip().rstrip('/')
    found = {value}
    if re.match(r'^10\.\d{4,9}/', value):
        found.add('doi:' + value)
    for doi in re.findall(r'(?:doi:|doi\.org/)(10\.\d{4,9}/[^\s?#]+)', value):
        found.add('doi:' + doi)
    for pmid in re.findall(r'(?:pmid:|pubmed\.ncbi\.nlm\.nih\.gov/|europepmc\.org/article/med/)(\d+)', value):
        found.add('pmid:' + pmid)
    for pmc in re.findall(r'(?:pmcid:|/articles/)(pmc\d+)', value):
        found.add('pmcid:' + pmc)
    for aid in re.findall(r'(?:arxiv:|arxiv\.org/(?:abs|pdf|html)/)(\d{4}\.\d{4,5}|[a-z.-]+/\d{7})(?:v\d+)?', value):
        found.add('arxiv:' + aid)
    return found


def identities(row):
    found = set()
    values = [row.get(key) for key in ('id', 'doi', 'url', 'open_access_url')]
    aliases = row.get('identifier_aliases', [])
    values += aliases if isinstance(aliases, list) else []
    for value in values:
        found.update(identity_tokens(value))
    return found


def file_hash(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def metrics(rows, corpus_path):
    category_counts = Counter(c for row in rows for c in row['categories'])
    review_counts = Counter(row['review_status'] for row in rows)
    accesses = [s['accessed_date'] for row in rows for s in row['sources']]
    return {
        'unique_papers': len(rows),
        'reviewed_papers': sum(row['review_status'] != 'discovered' for row in rows),
        'category_counts_nonexclusive': {key: category_counts[key] for key in CATEGORIES},
        'review_depth': {key: review_counts[key] for key in DEPTHS},
        'importance': dict(sorted(Counter(row['importance'] for row in rows).items())),
        'year_range': [min((r['year'] for r in rows), default=None),
                       max((r['year'] for r in rows), default=None)],
        'latest_recorded_source_access': max(accesses, default=None),
        'corpus_sha256': file_hash(corpus_path),
    }


def render_metrics(rows, corpus_path):
    m = metrics(rows, corpus_path)
    lines = [BEGIN,
             f"**Current corpus: {m['unique_papers']} unique papers; {m['reviewed_papers']} abstract-or-deeper reviewed.**",
             '', 'Review depth: ' + '; '.join(f'{k}: {v}' for k, v in m['review_depth'].items()) + '.',
             '', f"Latest recorded paper-source access: {m['latest_recorded_source_access'] or 'none'}.",
             '', '| Area | Papers (overlap allowed) |', '|---|---:|']
    lines += [f'| {label} | {m["category_counts_nonexclusive"][key]} |'
              for key, label in CATEGORIES.items()]
    lines += ['', f'Canonical SHA-256: `{m["corpus_sha256"]}`.', END]
    return '\n'.join(lines)


def render_catalog(rows, corpus_path):
    lines = ['# LLMs in Robotics literature catalog', '',
             f'Generated from `papers.jsonl`: **{len(rows)} unique papers**; category membership overlaps.',
             f'Corpus SHA-256: `{file_hash(corpus_path)}`.', '',
             'D = discovered; A = abstract reviewed; S = selected full text; F = full text reviewed; R = deep read.',
             'Importance is reading priority, not endorsement. See [Schema](Schema.md) and [Discovery Map](Discovery%20Map.md).', '']
    order = {'high': 0, 'medium': 1, 'low': 2}
    for category, label in CATEGORIES.items():
        group = sorted((r for r in rows if category in r['categories']),
                       key=lambda r: (order[r['importance']], r['year'], r['title'].casefold()))
        lines += [f'## {label} ({len(group)})', '',
                  '| Year | Paper | Importance | Review |', '|---:|---|---|---|']
        for row in group:
            title = ' '.join(row['title'].split()).replace('\\', '\\\\').replace('|', '\\|').replace('[', '\\[').replace(']', '\\]')
            target = row['url'].replace('<', '%3C').replace('>', '%3E').replace('|', '%7C')
            lines.append(f"| {row['year']} | [{title}](<{target}>) | {row['importance']} | {DEPTHS[row['review_status']]} |")
        lines.append('')
    return '\n'.join(lines)


def lookup(rows, *, text=None, exact_id=None, category=None, tag=None, status=None):
    hits = []
    for row in rows:
        if exact_id and not identity_tokens(exact_id).intersection(identities(row)):
            continue
        if category and category not in row.get('categories', []):
            continue
        if tag and tag not in row.get('tags', []):
            continue
        if status and status != row.get('review_status'):
            continue
        if text and text.casefold() not in json.dumps(row, ensure_ascii=False).casefold():
            continue
        hits.append(row)
    return hits


def replace_metrics(content, replacement):
    """Return changed text only after checking one ordered marker pair."""
    if content.count(BEGIN) != 1 or content.count(END) != 1:
        raise ValueError('Discovery Map needs exactly one generated-metrics marker pair')
    start, stop = content.index(BEGIN), content.index(END)
    if start >= stop:
        raise ValueError('Discovery Map markers are reversed')
    return content[:start] + replacement + content[stop + len(END):]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=ROOT / 'papers.jsonl')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('build', help='Regenerate Catalog and only marked current metrics')
    query = sub.add_parser('lookup', help='Combine exact filters and literal text with AND')
    query.add_argument('text', nargs='?')
    query.add_argument('--id', dest='exact_id')
    query.add_argument('--category', choices=CATEGORIES)
    query.add_argument('--tag')
    query.add_argument('--status', choices=DEPTHS)
    query.add_argument('--limit', type=int, default=10)
    query.add_argument('--json', action='store_true')
    args = parser.parse_args()
    rows, errors = read_jsonl(args.corpus)
    if errors:
        parser.error('; '.join(errors))
    if args.command == 'build':
        from validate_corpus import validate
        result = validate(args.corpus, args.corpus.parent / 'searches.jsonl', check_views=False)
        if result['errors']:
            parser.error('; '.join(result['errors']))
        discovery = args.corpus.parent / 'Discovery Map.md'
        try:
            # Preserve every byte outside the block, including existing newlines.
            with discovery.open(encoding='utf-8', newline='') as stream:
                current = stream.read()
            updated = replace_metrics(current, render_metrics(rows, args.corpus))
            catalog = render_catalog(rows, args.corpus)
        except (OSError, UnicodeError, ValueError) as exc:
            parser.error(str(exc))
        discovery.write_text(updated, encoding='utf-8', newline='')
        (args.corpus.parent / 'Catalog.md').write_text(catalog, encoding='utf-8', newline='\n')
        print(f'Regenerated catalog and current metrics for {len(rows)} papers')
        return 0
    if args.limit < 1:
        parser.error('--limit must be positive')
    hits = lookup(rows, text=args.text, exact_id=args.exact_id, category=args.category,
                  tag=args.tag, status=args.status)
    if args.json:
        print(json.dumps({'total_matches': len(hits), 'returned': min(len(hits), args.limit),
                          'records': hits[:args.limit]}, ensure_ascii=False, indent=2))
    else:
        print(f'{len(hits)} matches; showing {min(len(hits), args.limit)}')
        for row in hits[:args.limit]:
            print(f"{row.get('id')} | {row.get('year')} | {row.get('review_status')} | {row.get('title')}\n"
                  f"  {row.get('project_relevance')}\n  {row.get('url')}")
    return 0 if hits else 1


if __name__ == '__main__':
    raise SystemExit(main())
