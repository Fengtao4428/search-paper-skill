#!/usr/bin/env python3
"""Rebuild a local search-result catalog without moving source reports."""
import argparse
from datetime import datetime
import html
import json
import os
from pathlib import Path
from urllib.parse import quote

MARKER = '<!-- search-paper-archive:v1 -->'
LAYOUT = 'search-report-v1'
TEMPLATE = Path(__file__).resolve().parents[1] / 'assets' / 'archive-index.html'
EXCLUDED = {'data', 'state', 'sources', 'exports', 'docs', 'pdf', 'node_modules', '.git', '__pycache__'}


def inside(path, root):
    return path.resolve().is_relative_to(root)


def link(path, root, label):
    return {'label': label, 'url': quote(path.relative_to(root).as_posix(), safe='/')}


def collect(root):
    records, warnings = [], []
    for folder, dirs, names in os.walk(root, followlinks=False):
        directory = Path(folder)
        managed_tree = directory.is_relative_to(root / 'searches')
        dirs[:] = sorted(name for name in dirs if (managed_tree or (not name.startswith(('_', '.')) and name not in EXCLUDED))
                         and not (directory / name).is_symlink() and inside(directory / name, root))
        if directory == root:
            continue
        relative = directory.relative_to(root).as_posix()
        if 'manifest.json' in names:
            try:
                manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8-sig'))
                if manifest.get('layout') == LAYOUT:
                    ready = manifest.get('status') == 'ready' and (directory / 'index.html').is_file()
                    records.append({'id': manifest.get('report_id') or relative, 'kind': 'report' if ready else 'draft',
                                    'title': manifest.get('title') or manifest.get('topic') or directory.name,
                                    'topic': manifest.get('topic') or '', 'path': relative,
                                    'date': manifest.get('created_at') or '', 'paper_count': manifest.get('paper_count') if ready else None,
                                    'coverage': manifest.get('coverage_status') or 'unverified',
                                    'links': [link(directory / 'index.html', root, '打开论文库')] if ready else [],
                                    'scope': manifest.get('scope_label') or manifest.get('scope') or ''})
                    dirs[:] = []
                    continue
            except (ValueError, OSError, AttributeError) as exc:
                warnings.append({'path': relative + '/manifest.json', 'error': str(exc)})
        if 'index.html' in names and 'library.json' in names:
            try:
                library = json.loads((directory / 'library.json').read_text(encoding='utf-8-sig'))
                records.append({'id': relative, 'kind': 'legacy', 'title': library.get('title') or directory.name,
                                'topic': relative.split('/')[0], 'path': relative, 'date': library.get('retrieved_at') or '',
                                'paper_count': len(library['papers']) if isinstance(library.get('papers'), list) else None,
                                'coverage': 'unverified', 'scope': '', 'links': [link(directory / 'index.html', root, '打开原 HTML')]})
                dirs[:] = []
                continue
            except (ValueError, OSError, AttributeError) as exc:
                warnings.append({'path': relative + '/library.json', 'error': str(exc)})
        documents = [directory / name for name in sorted(names) if name.lower().endswith('.md')
                     and not name.startswith('.') and inside(directory / name, root)]
        if documents:
            records.append({'id': relative, 'kind': 'legacy', 'title': relative.replace('/', ' · '),
                            'topic': relative.split('/')[0], 'path': relative,
                            'date': datetime.fromtimestamp(max(p.stat().st_mtime for p in documents)).astimezone().isoformat(timespec='seconds'),
                            'paper_count': None, 'coverage': 'unverified', 'scope': '',
                            'links': [link(p, root, p.name) for p in documents]})
    records.sort(key=lambda item: (item['date'], item['path']), reverse=True)
    return records, warnings


def write_index(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError('Archive root does not exist: ' + str(root))
    target = root / 'index.html'
    catalog_path = root / '_catalog' / 'reports.json'
    if target.exists() and MARKER not in target.read_text(encoding='utf-8', errors='replace')[:256]:
        raise FileExistsError('Existing index.html is not owned by this catalog; it was not overwritten.')
    if catalog_path.exists():
        existing = json.loads(catalog_path.read_text(encoding='utf-8'))
        if existing.get('catalog_version') != 1:
            raise FileExistsError('Existing catalog data has an unsupported format.')
    records, warnings = collect(root)
    data = {'catalog_version': 1, 'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
            'records': records, 'warnings': warnings}
    encoded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    page = TEMPLATE.read_text(encoding='utf-8').replace('__CATALOG_DATA__', encoded).replace('__ARCHIVE_ROOT__', html.escape(str(root)))
    catalog_path.parent.mkdir(exist_ok=True)
    # Replace only this script's generated files, keeping every source report untouched.
    temp_data = catalog_path.with_suffix('.json.tmp')
    temp_data.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp_data.replace(catalog_path)
    temp_page = root / '_catalog' / 'index.html.tmp'
    temp_page.write_text(page, encoding='utf-8')
    temp_page.replace(target)
    return {'entry': str(target), 'reports': len(records), 'legacy_groups': sum(r['kind']=='legacy' for r in records), 'warnings': warnings}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('E:/paper'))
    args = parser.parse_args()
    print(json.dumps(write_index(args.root), ensure_ascii=False, indent=2))
