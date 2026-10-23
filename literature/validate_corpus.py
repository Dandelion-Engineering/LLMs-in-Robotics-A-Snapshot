"""Validate Vision core 1.0 with the llm-robotics-1.0 profile; standard library only.

Structural validity is separate from conceptual coverage, reading authenticity,
scientific accuracy, source rights and replication.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path, PureWindowsPath
import re
from urllib.parse import urlparse

from corpus import (ROOT, PROFILE, CORE_VERSION, CATEGORIES, DEPTHS, FIELDS,
                    SEARCH_FIELDS, BEGIN, END, read_jsonl, normal_title, identities,
                    metrics, render_catalog, render_metrics, file_hash)

ROBOTICS_FIELDS = set('llm_role execution_loop embodiment observations_and_privileged_inputs '
                      'action_interface memory_mechanism learning_dependencies human_assistance '
                      'evaluation_and_comparisons cost_and_latency reuse_and_licensing transfer_limits'.split())


def string(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, nonempty=False):
    return isinstance(value, list) and (bool(value) or not nonempty) and all(string(v) for v in value)


def url(value):
    if not string(value) or any(c.isspace() for c in value):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme in ('http', 'https') and bool(parsed.hostname)
    except ValueError:
        return False


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return False
    try:
        return date.fromisoformat(value) <= date.today()
    except ValueError:
        return False


def artifact_exists(value, project_root):
    if not string(value) or ':' in value or '?' in value or '#' in value:
        return False
    relative = Path(value.replace('\\', '/'))
    if relative.is_absolute() or PureWindowsPath(value).is_absolute() or '..' in relative.parts:
        return False
    target = (project_root / relative).resolve()
    return target.is_relative_to(project_root.resolve()) and target.is_file()


def validate(corpus, searches, check_views=True):
    corpus, searches = Path(corpus), Path(searches)
    rows, errors = read_jsonl(corpus)
    logs, search_errors = read_jsonl(searches)
    errors += search_errors

    def fail(where, message):
        errors.append(f'{where}: {message}')

    titles, ids = defaultdict(set), defaultdict(set)
    usable = []
    for number, row in enumerate(rows, 1):
        at = f'paper {number}'
        before = len(errors)
        if set(row) != FIELDS:
            fail(at, f'field difference {sorted(set(row) ^ FIELDS)}')
        for key in ('id', 'title', 'central_idea', 'representation_or_method', 'task_or_domain',
                    'evidence_or_evaluation', 'main_limitations', 'project_relevance', 'discovery_lane'):
            if not string(row.get(key)):
                fail(at, f'invalid {key}')
        for key in ('authors', 'categories', 'tags', 'basis_for_summary'):
            if not strings(row.get(key), True):
                fail(at, f'invalid {key}')
        for key in ('identifier_aliases', 'efficiency_targets'):
            if not strings(row.get(key)):
                fail(at, f'invalid {key}')
        for key in ('venue', 'doi', 'open_access_url', 'metadata_notes'):
            if row.get(key) is not None and not string(row[key]):
                fail(at, f'invalid nullable {key}')
        if type(row.get('authors_complete')) is not bool:
            fail(at, 'authors_complete must be bool')
        if type(row.get('year')) is not int or not 1800 <= row['year'] <= date.today().year + 1:
            fail(at, 'invalid year')
        for key, allowed in [('paper_type', {'method', 'experimental', 'theoretical', 'review', 'benchmark'}),
                             ('review_status', set(DEPTHS)), ('importance', {'high', 'medium', 'low'})]:
            if not isinstance(row.get(key), str) or row[key] not in allowed:
                fail(at, f'invalid {key}')
        if strings(row.get('categories')):
            if set(row['categories']) - CATEGORIES.keys():
                fail(at, 'unknown category')
            if len(row['categories']) != len(set(row['categories'])):
                fail(at, 'repeated category')
        if not url(row.get('url')):
            fail(at, 'invalid URL')
        if row.get('open_access_url') is not None and not url(row['open_access_url']):
            fail(at, 'invalid open URL')
        if row.get('doi') is not None and (not string(row['doi']) or not re.fullmatch(r'10\.\d{4,9}/\S+', row['doi'])):
            fail(at, 'doi must be bare DOI or null')
        sources = row.get('sources')
        if not isinstance(sources, list) or not sources:
            fail(at, 'missing sources')
        else:
            for source in sources:
                if (not isinstance(source, dict) or not url(source.get('url'))
                        or not string(source.get('material_reviewed'))
                        or not valid_date(source.get('accessed_date'))):
                    fail(at, 'invalid source provenance')
        provenance = row.get('provenance_notes')
        if not isinstance(provenance, dict):
            fail(at, 'provenance_notes must be object')
        else:
            robotics = provenance.get('robotics_context', {})
            if not isinstance(robotics, dict):
                fail(at, 'robotics_context must be object')
            else:
                if set(robotics) - ROBOTICS_FIELDS:
                    fail(at, 'unknown robotics_context field')
                for key, value in robotics.items():
                    if value is not None and not string(value):
                        fail(at, f'invalid robotics_context.{key}')
            uses = provenance.get('material_uses', [])
            if not isinstance(uses, list):
                fail(at, 'material_uses must be list')
            else:
                for use in uses:
                    if (not isinstance(use, dict) or not valid_date(use.get('date'))
                            or not all(string(use.get(k)) for k in ('agent', 'use', 'changes'))):
                        fail(at, 'invalid material use')
                    elif 'project_artifact' in use and not artifact_exists(use['project_artifact'], corpus.parent.parent):
                        fail(at, 'invalid material-use artifact')
        if len(errors) == before:
            usable.append(row)
        if string(row.get('title')):
            titles[normal_title(row['title'])].add(number)
        for identity in identities(row):
            ids[identity].add(number)
    duplicates = {key: sorted(value) for key, value in sorted(ids.items()) if len(value) > 1}
    duplicate_titles = {key: sorted(value) for key, value in sorted(titles.items()) if len(value) > 1}
    if duplicates or duplicate_titles:
        fail('identity', 'duplicate normalized title or identifier/alias')
    search_ids = set()
    canonical_ids = {row.get('id') for row in rows if isinstance(row.get('id'), str)}
    for number, entry in enumerate(logs, 1):
        at = f'search {number}'
        if set(entry) != SEARCH_FIELDS:
            fail(at, f'search field difference {sorted(set(entry) ^ SEARCH_FIELDS)}')
        for key in ('search_id', 'lane', 'source', 'purpose'):
            if not string(entry.get(key)):
                fail(at, f'invalid {key}')
        sid = entry.get('search_id')
        if string(sid):
            if sid in search_ids:
                fail(at, 'duplicate search ID')
            search_ids.add(sid)
        if not valid_date(entry.get('date')):
            fail(at, 'invalid date')
        if not strings(entry.get('categories')) or (strings(entry.get('categories')) and set(entry['categories']) - CATEGORIES.keys()):
            fail(at, 'invalid categories')
        for key in ('phase', 'original_log'):
            if entry.get(key) is not None and not string(entry[key]):
                fail(at, f'invalid {key}')
        if entry.get('original_record_number') is not None and (type(entry['original_record_number']) is not int or entry['original_record_number'] < 1):
            fail(at, 'invalid original record number')
        if (entry.get('original_log') is None) != (entry.get('original_record_number') is None):
            fail(at, 'original log and record number must be paired')
        queries = entry.get('queries')
        if not isinstance(queries, list):
            fail(at, 'queries must be list')
        else:
            for query in queries:
                if (not isinstance(query, dict) or not string(query.get('q'))
                        or set(query) - {'q', 'domains'}
                        or ('domains' in query and not strings(query['domains'], True))):
                    fail(at, 'invalid query')
        details = entry.get('details')
        if not isinstance(details, dict):
            fail(at, 'details must be object')
        else:
            for key in ('selected_paper_ids', 'origin_paper_ids'):
                refs = details.get(key, [])
                if not strings(refs):
                    fail(at, f'invalid {key}')
                elif set(refs) - canonical_ids:
                    fail(at, f'unknown paper references in {key}: {sorted(set(refs) - canonical_ids)}')
    measured = metrics(usable, corpus)
    reviewed_categories = Counter(c for row in usable if row['review_status'] != 'discovered' for c in row['categories'])
    if check_views and not errors:
        catalog, discovery = corpus.parent / 'Catalog.md', corpus.parent / 'Discovery Map.md'
        try:
            if catalog.read_text(encoding='utf-8') != render_catalog(rows, corpus):
                fail('views', 'Catalog stale')
        except (OSError, UnicodeError) as exc:
            fail('views', f'Catalog missing or unreadable: {exc}')
        try:
            content = discovery.read_text(encoding='utf-8')
            if (content.count(BEGIN) != 1 or content.count(END) != 1
                    or content.index(BEGIN) >= content.index(END)
                    or render_metrics(rows, corpus) not in content):
                fail('views', 'Discovery Map metrics stale or malformed')
        except (OSError, UnicodeError) as exc:
            fail('views', f'Discovery Map missing or unreadable: {exc}')
    return {
        'schema_version': CORE_VERSION, 'core_version': CORE_VERSION, 'profile': PROFILE,
        'generated_at': datetime.now(timezone.utc).isoformat(), 'corpus_file': corpus.name,
        **measured, 'parsed_records': len(rows), 'structurally_usable_records': len(usable),
        'search_records': len(logs), 'searches_sha256': file_hash(searches),
        'discovery_coverage': {
            'status': 'requires editorial judgment; no numeric completion gate',
            'unrepresented_categories': [c for c in CATEGORIES if measured['category_counts_nonexclusive'][c] == 0],
            'categories_without_reviewed_papers': [c for c in CATEGORIES if reviewed_categories[c] == 0],
            'reviewed_category_counts_nonexclusive': {c: reviewed_categories[c] for c in CATEGORIES},
            'limitations': [
                'Category counts overlap and do not measure architectural diversity or adequacy.',
                'Search recurrence and source-access gaps require the maintained Discovery Map discussion.',
                'Reading-depth labels and contextual claims are recorded assertions, not independently authenticated.',
            ],
        },
        'authors_incomplete': [row['id'] for row in usable if not row['authors_complete']],
        'missing_doi_count': sum(row['doi'] is None for row in usable),
        'missing_venue_count': sum(row['venue'] is None for row in usable),
        'missing_open_access_url_count': sum(row['open_access_url'] is None for row in usable),
        'duplicate_identifiers': duplicates, 'duplicate_titles': duplicate_titles,
        'derived_views_checked': check_views, 'errors': errors, 'passed': not errors,
        'limits': 'Structure, recorded identities/provenance and generated-view consistency only. Does not authenticate reading, scientific accuracy, licensing rights, replication, exhaustive coverage, full author lists or all edition equivalences. Counts use structurally usable records; duplicate collisions still fail validation.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=ROOT / 'papers.jsonl')
    parser.add_argument('--searches', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = validate(args.corpus, args.searches or args.corpus.parent / 'searches.jsonl')
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered, encoding='utf-8', newline='\n')
    print(rendered)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
