#!/usr/bin/env python3
"""Add CCF labels from a specified, verified catalog snapshot; never fetch or guess."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import sys
import unicodedata
from urllib.parse import urlparse


DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / 'references' / 'ccf-2026-verified.json'
EXCLUDED_TRACKS = {'findings', 'workshop'}
EXCLUDED_TYPES = {'short_paper', 'demo', 'technical_brief', 'summary', 'findings', 'workshop'}


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).casefold().split())


def web_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {'https', 'http'} and bool(parsed.hostname)


def official_url(value):
    if not web_url(value):
        return False
    host = urlparse(value).hostname.casefold()
    return host == 'ccf.org.cn' or host.endswith('.ccf.org.cn')


def catalog_index(catalog):
    """Validate metadata and reject ambiguous venue keys before writing output."""
    if not isinstance(catalog, dict):
        raise ValueError('Catalog must be an object.')
    for key in ('catalog_version', 'checked_on', 'source_url'):
        if not isinstance(catalog.get(key), str) or not catalog[key].strip():
            raise ValueError(f'Catalog requires {key}.')
    date.fromisoformat(catalog['checked_on'])
    if not official_url(catalog['source_url']):
        raise ValueError('Catalog source_url must be an official ccf.org.cn URL.')
    entries = catalog.get('entries')
    absences = catalog.get('verified_absences', [])
    if not isinstance(entries, list) or not isinstance(absences, list):
        raise ValueError('entries and verified_absences must be arrays.')
    index = {}
    absent = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('rank') not in {'A', 'B', 'C'}:
            raise ValueError('Each catalog entry needs rank A, B, or C.')
        if entry.get('venue_type') not in {'conference', 'journal'} or not normalized(entry.get('venue')):
            raise ValueError('Each catalog entry needs a venue and venue_type.')
        if 'source_url' in entry and not official_url(entry['source_url']):
            raise ValueError('Entry source_url must be an official CCF URL.')
        page = entry.get('pdf_page')
        if page is not None and (type(page) is not int or page < 1):
            raise ValueError('pdf_page must be a positive one-based page number.')
        aliases = entry.get('aliases', [])
        if not isinstance(aliases, list) or any(not isinstance(item, str) for item in aliases):
            raise ValueError('aliases must be an array of strings.')
        names = [entry['venue'], entry.get('full_name'), *aliases]
        for name in {normalized(name) for name in names if normalized(name)}:
            key = (name, entry['venue_type'])
            if key in index:
                raise ValueError(f'Ambiguous catalog alias: {name}')
            index[key] = entry
    for item in absences:
        if not isinstance(item, dict) or item.get('venue_type') not in {'conference', 'journal'}:
            raise ValueError('A verified absence needs venue_type conference or journal.')
        if not normalized(item.get('venue')) or not normalized(item.get('reason')):
            raise ValueError('A verified absence needs venue and an explicit verification reason.')
        key = (normalized(item['venue']), item['venue_type'])
        if key in index or key in absent:
            raise ValueError(f'Conflicting catalog entry/absence: {item["venue"]}')
        absent[key] = item
    return index, absent


def annotate_record(paper, catalog, index, absent):
    if not isinstance(paper, dict):
        raise ValueError('Each paper must be an object.')
    key = (normalized(paper.get('venue')), normalized(paper.get('venue_type')))
    entry = index.get(key)
    absence = absent.get(key)
    status = normalized(paper.get('publication_status'))
    track = normalized(paper.get('track'))
    kind = normalized(paper.get('publication_type'))
    scope_evidence = web_url(paper.get('publication_scope_source'))
    venue_evidence = web_url(paper.get('venue_source'))
    result = {
        'venue_rank': entry['rank'] if entry else None,
        'paper_label': 'CCF待核实',
        'applicability': 'pending',
        'reason': '尚无足够的目录及正式发表范围证据。',
        'catalog_status': 'listed' if entry else ('not_listed' if absence else 'unverified'),
        'catalog_version': catalog['catalog_version'],
        'catalog_checked_on': catalog['checked_on'],
        'catalog_source_url': entry.get('source_url', catalog['source_url']) if entry else catalog['source_url'],
        'catalog_page': entry.get('pdf_page') if entry else None,
        'catalog_basis': 'specified_snapshot',
        'venue_source': paper.get('venue_source'),
        'publication_scope_source': paper.get('publication_scope_source'),
    }
    if scope_evidence and (track in EXCLUDED_TRACKS or kind in EXCLUDED_TYPES or status in {'preprint', 'submitted'}):
        result.update(paper_label='CCF不适用', applicability='not_applicable',
                      reason='该记录为排除的文章形式/伴随会议，或尚未正式发表的预印本/投稿；不继承父会议等级。')
    elif absence and venue_evidence:
        result.update(paper_label='CCF未收录', applicability='not_applicable',
                      reason=f'已核对指定版完整目录：{absence["reason"]}')
    elif not entry:
        result['reason'] = '指定快照没有已核验的匹配条目；局部快照未匹配不代表官方目录未收录。'
    elif not venue_evidence or not scope_evidence:
        result['reason'] = '已匹配 venue 等级，但缺少正式 venue 或论文类型/发表状态的证据链接。'
    elif status != 'published':
        result['reason'] = '已录用但待正式发表。' if status == 'accepted' else '正式发表状态未核实。'
    elif (key[1] == 'conference' and track == 'main' and kind in {'full_paper', 'regular_paper'}) or (
        key[1] == 'journal' and kind == 'journal_article' and track not in EXCLUDED_TRACKS
    ):
        result.update(paper_label=f'CCF-{entry["rank"]}', applicability='eligible',
                      reason='根据提供的出版证据，属于指定版目录中该 venue 的适用论文类型。')
    else:
        result['reason'] = '已匹配 venue 等级，但 track 或文章类型尚未确认属于适用范围。'
    output = deepcopy(paper)
    output['ccf'] = result
    return output


def annotate_document(document, catalog):
    index, absent = catalog_index(catalog)
    if isinstance(document, list):
        return [annotate_record(paper, catalog, index, absent) for paper in document]
    if isinstance(document, dict) and isinstance(document.get('papers'), list):
        output = deepcopy(document)
        output['papers'] = [annotate_record(paper, catalog, index, absent) for paper in document['papers']]
        return output
    raise ValueError('Input must be a paper array or an object containing a papers array.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--catalog', type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.input.read_text(encoding='utf-8-sig'))
        catalog = json.loads(args.catalog.read_text(encoding='utf-8-sig'))
        annotated = annotate_document(document, catalog)
        payload = json.dumps(annotated, ensure_ascii=False, indent=2) + '\n'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(payload)
        print(f'Wrote {args.output} using {catalog["catalog_version"]}; no live catalog lookup performed.')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
