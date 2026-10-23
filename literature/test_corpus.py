"""Small structural/maintenance regression suite; all fixtures are synthetic.

Run from the repository root: python -X utf8 -B literature/test_corpus.py
No scientific findings, source authenticity or discovery adequacy are tested.
Adapted from [private project name redacted]; source hashes are in tool-reference-notes.md.
"""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import corpus
from validate_corpus import ROBOTICS_FIELDS, validate


def paper(number=1):
    return {
        'id': f'doi:10.1234/fixture.{number}',
        'identifier_aliases': [f'pmid:{90000000 + number}'],
        'title': f'Synthetic validation fixture {number}',
        'authors': ['Fixture A'], 'authors_complete': True, 'year': 2000,
        'venue': None, 'doi': f'10.1234/fixture.{number}',
        'url': f'https://example.org/fixture/{number}', 'open_access_url': None,
        'categories': ['planning_reasoning_skills'],
        'tags': ['synthetic-test'], 'paper_type': 'method',
        'review_status': 'abstract_reviewed', 'basis_for_summary': ['Synthetic fixture'],
        'central_idea': 'A fixture for validation, not a scientific claim.',
        'efficiency_targets': [], 'representation_or_method': 'Synthetic method',
        'task_or_domain': 'Software testing', 'evidence_or_evaluation': 'No empirical data',
        'main_limitations': 'Synthetic fixture only', 'project_relevance': 'Validator test',
        'importance': 'low',
        'sources': [{'url': 'https://example.org/source',
                     'material_reviewed': 'Synthetic fixture', 'accessed_date': '2000-01-01'}],
        'metadata_notes': None, 'discovery_lane': 'test', 'provenance_notes': {},
    }


def search():
    return {
        'search_id': 'fixture-search', 'lane': 'test', 'date': '2000-01-01',
        'source': 'synthetic', 'queries': [{'q': 'fixture', 'domains': ['example.org']}],
        'categories': ['planning_reasoning_skills'], 'purpose': 'Software testing',
        'phase': None, 'original_log': None, 'original_record_number': None,
        'details': {'selected_paper_ids': [paper()['id']]},
    }


class CorpusContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='robotics-literature-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'literature'
        self.root.mkdir()
        self.papers = self.root / 'papers.jsonl'
        self.searches = self.root / 'searches.jsonl'

    def write(self, records=None, logs=None):
        records = [paper()] if records is None else records
        logs = [search()] if logs is None else logs
        for path, rows in [(self.papers, records), (self.searches, logs)]:
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        return records

    def result(self, records=None, logs=None, views=False):
        self.write(records, logs)
        return validate(self.papers, self.searches, check_views=views)

    def assert_rejected(self, records=None, logs=None):
        result = self.result(records, logs)
        self.assertFalse(result['passed'])
        self.assertTrue(result['errors'])
        return result

    def test_empty_efficiency_targets_are_valid_and_coverage_separate(self):
        result = self.result()
        self.assertTrue(result['passed'], result['errors'])
        self.assertEqual(result['reviewed_papers'], 1)
        self.assertEqual(result['profile'], 'llm-robotics-1.0')
        self.assertEqual(result['core_version'], '1.0')
        self.assertEqual(len(corpus.FIELDS), 27)
        self.assertEqual(len(corpus.CATEGORIES), 12)
        self.assertIn('memory_continuity', result['discovery_coverage']['unrepresented_categories'])
        self.assertEqual(result['corpus_sha256'], hashlib.sha256(self.papers.read_bytes()).hexdigest())

    def test_discovered_records_do_not_count_as_reviewed(self):
        record = paper()
        record['review_status'] = 'discovered'
        result = self.result([record])
        self.assertTrue(result['passed'], result['errors'])
        self.assertEqual(result['unique_papers'], 1)
        self.assertEqual(result['reviewed_papers'], 0)

    def test_missing_and_extra_fields_rejected(self):
        for mutation in ['missing', 'extra']:
            with self.subTest(mutation=mutation):
                record = paper()
                if mutation == 'missing':
                    del record['metadata_notes']
                else:
                    record['unapproved_field'] = 'value'
                self.assert_rejected([record])

    def test_bad_paper_types_return_errors_without_crashing(self):
        changes = {
            'id': [], 'title': {}, 'authors': 'Name', 'authors_complete': 1,
            'year': True, 'identifier_aliases': {'pmid': 1}, 'categories': [None],
            'tags': None, 'basis_for_summary': [], 'efficiency_targets': 'phase reset',
            'paper_type': [], 'review_status': {}, 'importance': [], 'sources': [None],
            'provenance_notes': [], 'venue': 10, 'url': {'address': 'x'},
        }
        for key, value in changes.items():
            with self.subTest(field=key):
                record = paper()
                record[key] = value
                self.assert_rejected([record])

    def test_invalid_source_and_source_dates(self):
        for key, value in [('url', 'file:///private/data'), ('material_reviewed', ''),
                           ('accessed_date', '2000-02-30'), ('accessed_date', []),
                           ('accessed_date', (date.today() + timedelta(days=1)).isoformat())]:
            with self.subTest(field=key, value=value):
                record = paper()
                record['sources'][0][key] = value
                self.assert_rejected([record])

    def test_malformed_url_does_not_crash(self):
        for key in ['url', 'open_access_url']:
            with self.subTest(field=key):
                record = paper()
                record[key] = 'https://[invalid-address'
                self.assert_rejected([record])
        record = paper()
        record['sources'][0]['url'] = 'https://[invalid-address'
        self.assert_rejected([record])

    def test_duplicate_id_title_and_alias_collisions(self):
        for mutation in ['id', 'title', 'alias', 'doi-url', 'arxiv-version']:
            with self.subTest(mutation=mutation):
                first, second = paper(1), paper(2)
                if mutation == 'id':
                    second['id'] = first['id']
                elif mutation == 'title':
                    second['title'] = first['title'].upper() + '!!!'
                elif mutation == 'alias':
                    second['identifier_aliases'] = ['PMID:90000001']
                elif mutation == 'doi-url':
                    second['url'] = 'https://doi.org/10.1234/fixture.1'
                else:
                    first['identifier_aliases'].append('arxiv:2007.07797v1')
                    second['url'] = 'https://arxiv.org/abs/2007.07797v2'
                result = self.assert_rejected([first, second])
                self.assertTrue(result['duplicate_identifiers'] or result['duplicate_titles'])

    def test_domain_context_and_material_use_shape(self):
        cases = [
            {'robotics_context': []},
            {'robotics_context': {'action_interface': []}},
            {'robotics_context': {'transfer_limits': []}},
            {'robotics_context': {'not_a_field': 'x'}},
            {'robotics_context': {'action_interface': ['../outside.md']}},
            {'material_uses': {}},
            {'material_uses': [{'date': 'bad', 'agent': 'test', 'use': 'x', 'changes': 'x'}]},
            {'material_uses': [{'date': '2000-01-01', 'agent': 'test', 'use': 'x', 'changes': 'x',
                                'project_artifact': []}]},
        ]
        for value in cases:
            with self.subTest(value=value):
                record = paper()
                record['provenance_notes'] = value
                self.assert_rejected([record])

    def test_search_shape_types_references_and_duplicate_ids(self):
        changes = {
            'search_id': [], 'lane': None, 'date': '2000-13-01', 'source': 1,
            'queries': 'q', 'categories': ['not-a-category'], 'purpose': [],
            'phase': {}, 'original_log': 'old.jsonl', 'original_record_number': True,
            'details': [],
        }
        for key, value in changes.items():
            with self.subTest(field=key):
                log = search()
                log[key] = value
                self.assert_rejected(logs=[log])
        for query in [None, {'q': ''}, {'q': 'ok', 'domains': 'example.org'},
                      {'q': 'ok', 'unexpected': True}]:
            with self.subTest(query=query):
                log = search()
                log['queries'] = [query]
                self.assert_rejected(logs=[log])
        log = search()
        log['details']['selected_paper_ids'] = ['doi:10.1234/unknown']
        self.assert_rejected(logs=[log])
        log['details']['selected_paper_ids'] = {'id': paper()['id']}
        self.assert_rejected(logs=[log])
        self.assert_rejected(logs=[search(), search()])
        log = search()
        del log['phase']
        self.assert_rejected(logs=[log])

    def test_nonobject_invalid_json_and_bad_encoding_return_errors(self):
        for payload in [b'[]\n', b'null\n', b'{broken}\n', b'\xff\n', b'\xef\xbb\xbf{}\n']:
            with self.subTest(payload=payload):
                self.write()
                self.papers.write_bytes(payload)
                result = validate(self.papers, self.searches, check_views=False)
                self.assertFalse(result['passed'])
                self.assertTrue(result['errors'])
        self.write()
        self.searches.write_text('[]\n', encoding='utf-8')
        self.assertFalse(validate(self.papers, self.searches, check_views=False)['passed'])

    def test_missing_file_and_missing_final_newline_fail(self):
        self.write()
        self.papers.unlink()
        self.assertFalse(validate(self.papers, self.searches, check_views=False)['passed'])
        self.write()
        self.papers.write_text(json.dumps(paper()), encoding='utf-8')
        self.assertFalse(validate(self.papers, self.searches, check_views=False)['passed'])

    def test_stale_catalog_and_metrics_fail_then_cli_build_repairs(self):
        records = self.write()
        discovery = self.root / 'Discovery Map.md'
        preserved = 'Historical fixture note remains here.'
        discovery.write_text('# Fixture\n' + corpus.BEGIN + '\nold\n' + corpus.END +
                             '\n' + preserved + '\n', encoding='utf-8')
        self.assertFalse(validate(self.papers, self.searches)['passed'])
        proc = subprocess.run([sys.executable, '-B', str(corpus.ROOT / 'corpus.py'),
                               '--corpus', str(self.papers), 'build'],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(validate(self.papers, self.searches)['passed'])
        self.assertIn(preserved, discovery.read_text(encoding='utf-8'))
        records[0]['central_idea'] = 'A changed fixture requires a new corpus hash.'
        self.write(records)
        stale = validate(self.papers, self.searches)
        self.assertFalse(stale['passed'])
        self.assertTrue(any('stale' in error for error in stale['errors']))

    def test_lookup_supports_identity_text_category_tag_and_status(self):
        first, second = paper(1), paper(2)
        second['review_status'] = 'discovered'
        second['tags'] = ['different']
        second['project_relevance'] = 'Needle applicability note'
        rows = [first, second]
        self.assertEqual(corpus.lookup(rows, exact_id='PMID:90000001'), [first])
        self.assertEqual(corpus.lookup(rows, text='needle'), [second])
        self.assertEqual(corpus.lookup(rows, tag='synthetic-test', status='abstract_reviewed'), [first])
        self.assertEqual(corpus.lookup(rows, category='planning_reasoning_skills'), rows)
        self.assertEqual(corpus.lookup(rows, exact_id='pmid:00000000'), [])

    def test_cli_build_rejects_reversed_markers_before_writing(self):
        self.write()
        discovery = self.root / 'Discovery Map.md'
        before = '# Fixture\n' + corpus.END + '\nEditorial text\n' + corpus.BEGIN + '\n'
        discovery.write_text(before, encoding='utf-8')
        proc = subprocess.run([sys.executable, '-B', str(corpus.ROOT / 'corpus.py'),
                               '--corpus', str(self.papers), 'build'],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(discovery.read_text(encoding='utf-8'), before)
        self.assertFalse((self.root / 'Catalog.md').exists())

    def test_robotics_profile_accepts_optional_strings_nulls_and_real_use(self):
        artifact = self.root.parent / 'report.md'
        artifact.write_text('Synthetic project artifact', encoding='utf-8')
        record = paper()
        record['provenance_notes'] = {
            'robotics_context': {key: None for key in ROBOTICS_FIELDS},
            'material_uses': [{'date': '2000-01-01', 'agent': 'test',
                               'use': 'Fixture use', 'changes': 'Fixture changes',
                               'project_artifact': 'report.md'}],
        }
        record['provenance_notes']['robotics_context']['execution_loop'] = 'Instruction to controller to feedback'
        result = self.result([record])
        self.assertTrue(result['passed'], result['errors'])
        self.assertEqual(result['searches_sha256'], hashlib.sha256(self.searches.read_bytes()).hexdigest())
        for target in ['../outside.md', '/absolute.md', 'C:\\absolute.md', 'missing.md', '']:
            with self.subTest(target=target):
                record['provenance_notes']['material_uses'][0]['project_artifact'] = target
                self.assert_rejected([record])

    def test_dates_require_hyphenated_calendar_form_in_every_event(self):
        for bad in ['20000101', '2000-W01-1', '2000-1-1', '2000-01-01T00:00:00', True]:
            with self.subTest(date=bad):
                record = paper()
                record['sources'][0]['accessed_date'] = bad
                self.assert_rejected([record])
                log = search()
                log['date'] = bad
                self.assert_rejected(logs=[log])
                record = paper()
                record['provenance_notes']['material_uses'] = [
                    {'date': bad, 'agent': 'test', 'use': 'use', 'changes': 'changes'}]
                self.assert_rejected([record])

    def test_arbitrary_alias_and_versioned_arxiv_lookup_and_collisions(self):
        first, second = paper(1), paper(2)
        first['identifier_aliases'] += ['publisher:stable-fixture', 'arxiv:2401.01234v1']
        rows = [first, second]
        self.assertEqual(corpus.lookup(rows, exact_id='PUBLISHER:stable-fixture'), [first])
        self.assertEqual(corpus.lookup(rows, exact_id='https://arxiv.org/html/2401.01234v3'), [first])
        self.assertEqual(corpus.lookup(rows, exact_id='10.1234/fixture.1'), [first])
        self.assertEqual(corpus.lookup(rows, exact_id='doi:10.1234/fixture'), [])
        second['identifier_aliases'] = ['publisher:stable-fixture']
        self.assert_rejected([first, second])

    def test_strict_json_rejects_duplicate_keys_nonfinite_values_and_blank_lines(self):
        for payload in ['{"id": "one", "id": "two"}\n',
                        '{"nested": {"date": "one", "date": "two"}}\n',
                        '{"number": NaN}\n', '{"number": Infinity}\n', '\n']:
            with self.subTest(payload=payload):
                self.write()
                self.papers.write_text(payload, encoding='utf-8')
                self.assertFalse(validate(self.papers, self.searches, check_views=False)['passed'])

    def test_build_preserves_editorial_bytes_and_is_repeatable(self):
        self.write()
        discovery = self.root / 'Discovery Map.md'
        prefix = '# Current orientation\r\nManual: café and feedback → action.\r\n'
        suffix = '\r\n## Historical checkpoint\r\nDated human notes stay unchanged.\r\n'
        discovery.write_bytes((prefix + corpus.BEGIN + '\r\nold\r\n' + corpus.END + suffix).encode('utf-8'))
        cmd = [sys.executable, '-X', 'utf8', '-B', str(corpus.ROOT / 'corpus.py'),
               '--corpus', str(self.papers), 'build']
        first = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        content = discovery.read_bytes()
        self.assertTrue(content.startswith(prefix.encode('utf-8')))
        self.assertTrue(content.endswith(suffix.encode('utf-8')))
        second = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(content, discovery.read_bytes())
        self.assertTrue(validate(self.papers, self.searches)['passed'])

    def test_build_rejects_missing_or_repeated_markers_without_mutating_views(self):
        self.write()
        discovery = self.root / 'Discovery Map.md'
        catalog = self.root / 'Catalog.md'
        catalog.write_text('Previous catalog', encoding='utf-8')
        for content in ['No markers', corpus.BEGIN + corpus.END + corpus.BEGIN,
                        corpus.BEGIN + corpus.END + corpus.END]:
            with self.subTest(content=content):
                discovery.write_text(content, encoding='utf-8')
                proc = subprocess.run([sys.executable, '-B', str(corpus.ROOT / 'corpus.py'),
                                       '--corpus', str(self.papers), 'build'],
                                      capture_output=True, text=True, encoding='utf-8')
                self.assertNotEqual(proc.returncode, 0)
                self.assertEqual(discovery.read_text(encoding='utf-8'), content)
                self.assertEqual(catalog.read_text(encoding='utf-8'), 'Previous catalog')

    def test_cli_json_lookup_and_no_match_exit_status(self):
        self.write([paper(1), paper(2)])
        cmd = [sys.executable, '-X', 'utf8', '-B', str(corpus.ROOT / 'corpus.py'),
               '--corpus', str(self.papers), 'lookup']
        proc = subprocess.run(cmd + ['--tag', 'synthetic-test', '--json', '--limit', '1'],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual((body['total_matches'], body['returned']), (2, 1))
        self.assertEqual(body['records'][0]['id'], paper()['id'])
        proc = subprocess.run(cmd + ['--id', 'publisher:unrepresented', '--json'],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['records'], [])

    def test_empty_corpus_is_structurally_valid_with_explicit_coverage_gaps(self):
        result = self.result([], [])
        self.assertTrue(result['passed'], result['errors'])
        self.assertEqual(result['unique_papers'], 0)
        self.assertEqual(len(result['discovery_coverage']['unrepresented_categories']), 12)

    def test_forthcoming_year_is_dynamic_and_bare_doi_is_checked(self):
        record = paper()
        record['year'] = date.today().year + 1
        self.assertTrue(self.result([record])['passed'])
        record['year'] += 1
        self.assert_rejected([record])
        record = paper()
        record['doi'] = 'not a DOI'
        self.assert_rejected([record])


if __name__ == '__main__':
    unittest.main(verbosity=2)
