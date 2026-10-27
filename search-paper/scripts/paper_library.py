#!/usr/bin/env python3
"""Build a fixed offline paper library, or serve it with a loopback-only Zotero bridge."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading
import unicodedata
from urllib import error, parse, request
import uuid
import webbrowser

TEMPLATE = Path(__file__).resolve().parents[1] / 'assets' / 'paper-library.html'
VERSION = 'paper-library-v5'
ZOTERO_URL = 'http://127.0.0.1:23119'
BRIDGE_MARKER = '<script id="bridge-config" type="application/json">null</script>'
STORAGE_LAYOUT = 'search-report-v1'


def text(value):
    return str(value).strip() if value is not None else ''


def line(value):
    return re.sub(r'[\r\n\x00-\x1f]+', ' ', text(value)).strip()


def url(value):
    value = text(value)
    try:
        parts = parse.urlsplit(value)
        return value if parts.scheme in ('http', 'https') and parts.hostname and not parts.username else ''
    except ValueError:
        return ''


def json_script(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def author_name(author):
    if isinstance(author, dict):
        return text(author.get('name')) or ' '.join(filter(None, [text(author.get('given') or author.get('firstName')), text(author.get('family') or author.get('lastName'))]))
    return text(author)


def normalize_paper(source, position):
    if not isinstance(source, dict):
        raise ValueError('Each paper must be an object.')
    title = text(source.get('title_en') or source.get('title'))
    if not title:
        raise ValueError(f'Paper {position} has no title.')
    authors = source.get('authors') or source.get('creators') or []
    if isinstance(authors, str):
        authors = [authors]  # Do not guess author boundaries from commas.
    if not isinstance(authors, list):
        raise ValueError(f'Paper {position}: authors must be an array or string.')
    ccf = source.get('ccf') if isinstance(source.get('ccf'), dict) else {}
    labels = {'CCF-A', 'CCF-B', 'CCF-C', 'CCF未收录', 'CCF不适用', 'CCF待核实'}
    label = ccf.get('paper_label') if ccf.get('paper_label') in labels else 'CCF待核实'
    if label in {'CCF-A', 'CCF-B', 'CCF-C'} and not (
        ccf.get('applicability') == 'eligible' and ccf.get('catalog_status') == 'listed'
        and ccf.get('venue_rank') == label[-1] and ccf.get('catalog_version')
        and url(ccf.get('catalog_source_url')) and url(source.get('venue_source') or ccf.get('venue_source'))
        and url(source.get('publication_scope_source') or ccf.get('publication_scope_source'))
    ):
        label = 'CCF待核实'
        ccf = dict(ccf, applicability='unknown', reason='等级所需的目录或论文适用性证据不完整，待补充核验。')
    ccf = dict(ccf, paper_label=label)
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', text(source.get('doi') or source.get('DOI')), flags=re.I).strip()
    links = source.get('sources') if isinstance(source.get('sources'), dict) else {}
    original = url(source.get('url') or source.get('source_url') or source.get('venue_source') or links.get('paper') or links.get('url'))
    if not original and doi:
        original = 'https://doi.org/' + parse.quote(doi, safe='/():;._-')
    keywords = source.get('keywords') or []
    if isinstance(keywords, str):
        keywords = [part.strip() for part in re.split(r'[,，;；]', keywords) if part.strip()]
    relevance = source.get('relevance')
    reason = text(source.get('relevance_reason') or source.get('screening_reason'))
    if isinstance(relevance, dict):
        reason = text(relevance.get('reason')) or reason
        relevance = relevance.get('level') or relevance.get('label')
    fingerprint = hashlib.sha256((('doi:' + doi.casefold()) if doi else 'title:' + unicodedata.normalize('NFKC', title).casefold() + '|' + text(source.get('year')) + '|' + '|'.join(author_name(a) for a in authors)).encode('utf-8')).hexdigest()
    return {
        'paper_id': text(source.get('paper_id')) or fingerprint[:20], 'fingerprint': fingerprint,
        'title_en': title, 'title_zh': text(source.get('title_zh')), 'authors': authors,
        'author_display': ', '.join(filter(None, [author_name(a) for a in authors])),
        'year': text(source.get('year')), 'venue': text(source.get('venue')),
        'venue_type': text(source.get('venue_type')), 'track': text(source.get('track')),
        'publication_type': text(source.get('publication_type')), 'publication_status': text(source.get('publication_status')),
        'presentation_groups': source.get('presentation_groups') or [],
        'doi': doi, 'url': original, 'pdf_url': url(source.get('pdf_url') or links.get('pdf')),
        'abstract_en': text(source.get('abstract_en')), 'abstract_zh': text(source.get('abstract_zh')),
        'abstract_source_url': url(source.get('abstract_source_url') or links.get('abstract')),
        'venue_source': url(source.get('venue_source') or ccf.get('venue_source')),
        'publication_scope_source': url(source.get('publication_scope_source') or ccf.get('publication_scope_source')),
        'summary_zh': text(source.get('summary_zh')), 'summary_basis': text(source.get('summary_basis')),
        'relevance': text(relevance) or '未分级',
        'relevance_reason': reason, 'keywords': [text(k) for k in keywords] if isinstance(keywords, list) else [],
        'ccf': ccf, 'volume': text(source.get('volume')), 'issue': text(source.get('issue')),
        'pages': text(source.get('pages')), 'publisher': text(source.get('publisher')),
    }


def make_ris(paper):
    """Create one RIS record; sanitize line breaks so metadata cannot inject fields."""
    kind = 'JOUR' if paper['venue_type'] == 'journal' else ('CONF' if paper['venue_type'] == 'conference' else 'GEN')
    fields = [('TY', kind), ('TI', paper['title_en'])]
    for author in paper['authors']:
        if isinstance(author, dict) and (author.get('family') or author.get('lastName')):
            name = ', '.join(filter(None, [text(author.get('family') or author.get('lastName')), text(author.get('given') or author.get('firstName'))]))
        else:
            name = author_name(author)
        if name:
            fields.append(('AU', name))
    fields += [('PY', paper['year']), ('T2', paper['venue']), ('DO', paper['doi']), ('UR', paper['url']),
               ('AB', paper['abstract_en'] or paper['abstract_zh']), ('VL', paper['volume']),
               ('IS', paper['issue']), ('SP', paper['pages']), ('PB', paper['publisher'])]
    ccf = paper['ccf']
    tags = ['PaperLibrary', ccf['paper_label']]
    if ccf.get('catalog_version'):
        tags.append('CCF目录:' + text(ccf['catalog_version']))
    if paper['venue']:
        tags.append('Venue:' + paper['venue'])
    tags += paper['keywords'][:20]
    for tag in dict.fromkeys(line(tag)[:200] for tag in tags if line(tag)):
        fields.append(('KW', tag))
    note = {
        '中文标题': paper['title_zh'], '中文摘要': paper['abstract_zh'],
        'AI阅读提示': paper['summary_zh'], '主题相关性': paper['relevance_reason'],
        'CCF标签': ccf['paper_label'], 'Venue等级': ccf.get('venue_rank'),
        'CCF适用性': ccf.get('reason'), 'CCF目录版本': ccf.get('catalog_version'),
        'CCF官方来源': ccf.get('catalog_source_url'), 'CCF目录PDF页码': ccf.get('catalog_page'),
        'CCF核验日期': ccf.get('catalog_checked_on'), 'Track': paper['track'],
        '文章类型': paper['publication_type'], '发表状态': paper['publication_status'],
        '摘要来源': paper.get('abstract_source_url'), 'Venue依据': paper.get('venue_source'),
        '论文类型依据': paper.get('publication_scope_source'),
        'PDF链接': paper['pdf_url'], '来源ID': paper['paper_id'],
    }
    # RIS notes may be interpreted as HTML by translators: escape values.
    fields.append(('N1', ' | '.join(html.escape(f'{key}: {line(value)}') for key, value in note.items() if text(value))))
    return '\r\n'.join(f'{tag}  - {line(value)}' for tag, value in fields if line(value)) + '\r\nER  -\r\n'


def folder_name(value, fallback='未命名'):
    value = unicodedata.normalize('NFKC', text(value))
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '-', value)
    value = re.sub(r'\s+', '-', value).strip(' .-')[:48].rstrip(' .') or fallback
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', value, re.I):
        value = '_' + value
    return value


def new_report(root, topic, scope='跨来源'):
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError('Archive root does not exist: ' + str(root))
    now = datetime.now().astimezone()
    parent = root / 'searches' / folder_name(topic)
    parent.mkdir(parents=True, exist_ok=True)
    base = now.strftime('%Y%m%d-%H%M%S') + '_' + folder_name(scope)
    for number in range(1, 1000):
        target = parent / (base if number == 1 else f'{base}_{number:02d}')
        try:
            target.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError('Could not allocate a unique report folder.')
    (target / 'data').mkdir()
    (target / '_work').mkdir()
    manifest = {'layout': STORAGE_LAYOUT, 'report_id': uuid.uuid4().hex, 'status': 'draft',
                'topic': text(topic), 'scope_label': text(scope), 'created_at': now.isoformat(timespec='seconds')}
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target


def build(input_path, output_dir, coverage_path=None, title=None, demo=False, continue_from=None):
    input_path = Path(input_path).resolve()
    source_bytes = input_path.read_bytes()
    source = json.loads(source_bytes.decode('utf-8-sig'))
    records = source if isinstance(source, list) else source.get('papers')
    if not isinstance(records, list):
        raise ValueError('Input must be an array or an object containing papers.')
    meta = source if isinstance(source, dict) else {}
    papers = [normalize_paper(paper, i + 1) for i, paper in enumerate(records)]
    if len({paper['paper_id'] for paper in papers}) != len(papers):
        raise ValueError('Duplicate paper_id values; deduplicate before rendering.')
    for paper in papers:
        paper['ris'] = make_ris(paper)
    coverage_bytes = Path(coverage_path).read_bytes() if coverage_path else None
    coverage = json.loads(coverage_bytes.decode('utf-8-sig')) if coverage_bytes is not None else meta.get('coverage', {})
    if not isinstance(coverage, dict):
        raise ValueError('Coverage must be a JSON object.')
    data = {
        'template_version': VERSION, 'title': title or text(meta.get('title')) or '论文检索结果',
        'scope': meta.get('scope', {}), 'retrieved_at': text(meta.get('retrieved_at')),
        'ccf_catalog_policy': meta.get('ccf_catalog_policy', ''), 'coverage': coverage,
        'demo': demo, 'papers': papers,
    }
    output_dir = Path(output_dir).resolve()
    filenames = ['index.html', 'library.json', 'data/library.json', '打开论文库.cmd', 'state/library.sqlite3']
    if any((output_dir / name).exists() for name in filenames):
        raise FileExistsError('Report files already exist; use a new output directory.')
    manifest_path = output_dir / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {}
    if manifest and (manifest.get('layout') != STORAGE_LAYOUT or manifest.get('status') != 'draft'):
        raise FileExistsError('Existing manifest is not an unfinished report.')
    # Preflight every canonical input before creating output files.
    saved_coverage = coverage_bytes or (json.dumps(coverage, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    for relative, content in [('data/papers.json', source_bytes), ('data/coverage.json', saved_coverage)]:
        destination = output_dir / relative
        if destination.exists() and destination.read_bytes() != content:
            raise FileExistsError('Refusing to replace different source data: ' + str(destination))
    previous = Path(continue_from).resolve() if continue_from else None
    if previous:
        if previous == output_dir or not any((previous / name).is_file() for name in ['data/library.json', 'library.json']):
            raise ValueError('continue-from must name a different existing report.')
        previous_database = previous / ('state/library.sqlite3' if (previous / 'data/library.json').is_file() else '_work/zotero-imports.sqlite3')
    else:
        previous_database = None
    template = TEMPLATE.read_text(encoding='utf-8')
    rendered = template.replace('__LIBRARY_TITLE__', html.escape(data['title'])).replace('__LIBRARY_DATA__', json_script(data))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'data').mkdir(exist_ok=True)
    (output_dir / 'data' / 'papers.json').write_bytes(source_bytes)
    (output_dir / 'data' / 'coverage.json').write_bytes(saved_coverage)
    (output_dir / 'index.html').write_text(rendered, encoding='utf-8')
    (output_dir / 'data' / 'library.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    launch = '@echo off\r\nchcp 65001 >nul\r\n' + f'"{sys.executable}" -B -X utf8 "{Path(__file__).resolve()}" serve --report "%~dp0." --open\r\n' + 'if errorlevel 1 pause\r\n'
    (output_dir / '打开论文库.cmd').write_bytes(launch.encode('utf-8'))
    if previous_database and previous_database.is_file():
        (output_dir / 'state').mkdir(exist_ok=True)
        source_db = sqlite3.connect(previous_database.as_uri() + '?mode=ro', uri=True)
        target_db = sqlite3.connect(output_dir / 'state' / 'library.sqlite3')
        try:
            source_db.backup(target_db)
        finally:
            target_db.close()
            source_db.close()
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    manifest.update({
        'layout': STORAGE_LAYOUT, 'report_id': manifest.get('report_id') or uuid.uuid4().hex,
        'status': 'ready', 'title': data['title'], 'topic': manifest.get('topic') or (data['scope'].get('topic') if isinstance(data['scope'], dict) else '') or data['title'],
        'created_at': manifest.get('created_at') or now, 'built_at': now,
        'template_version': VERSION, 'paper_count': len(papers), 'scope': data['scope'], 'demo': demo,
        'coverage_status': coverage.get('coverage_status') or (coverage.get('summary') or {}).get('coverage_status') or 'unverified',
        'paths': {'entry': 'index.html', 'launcher': '打开论文库.cmd', 'papers': 'data/papers.json',
                  'coverage': 'data/coverage.json', 'library': 'data/library.json',
                  'state': 'state/library.sqlite3', 'sources': 'sources/', 'exports': 'exports/', 'work': '_work/'},
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
    })
    if previous:
        manifest['continued_from'] = str(previous)
        manifest['state_snapshot_copied'] = bool(previous_database and previous_database.is_file())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output_dir / 'index.html'


class ZoteroError(Exception):
    pass


class ZoteroClient:
    def __init__(self, base_url=ZOTERO_URL):
        parsed = parse.urlsplit(base_url)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1':
            raise ValueError('Zotero bridge only supports 127.0.0.1.')
        self.base_url = base_url.rstrip('/')
        self.opener = request.build_opener(request.ProxyHandler({}))

    def call(self, route, data=None, content_type='application/json', timeout=5):
        payload = None
        if data is not None:
            payload = json.dumps(data).encode('utf-8') if content_type == 'application/json' else data.encode('utf-8')
        headers = {'User-Agent': 'PaperLibrary/1.0', 'X-Zotero-Connector-API-Version': '3',
                   'Zotero-Allowed-Request': '1', 'Content-Type': content_type}
        req = request.Request(self.base_url + route, data=payload, headers=headers)
        try:
            with self.opener.open(req, timeout=timeout) as response:
                body = response.read().decode('utf-8')
                return json.loads(body) if body.strip() else None
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ZoteroError(str(exc)) from exc

    def target(self):
        value = self.call('/connector/getSelectedCollection', {})
        if not isinstance(value, dict) or 'libraryID' not in value:
            raise ZoteroError('Invalid target response.')
        collection_id = value.get('id')
        return {
            'id': f'C{collection_id}' if collection_id else f'L{value["libraryID"]}',
            'library_id': str(value['libraryID']), 'library_name': text(value.get('libraryName')),
            'name': text(value.get('name') or value.get('libraryName')),
            'editable': bool(value.get('libraryEditable')) and value.get('editable', True) is not False,
        }

    def import_ris(self, ris, session):
        return self.call('/connector/import?' + parse.urlencode({'session': session}), ris, 'text/plain', 45)


class Bridge:
    def __init__(self, report, client=None):
        self.report = Path(report).resolve()
        modern = (self.report / 'data' / 'library.json').is_file()
        library_path = self.report / ('data/library.json' if modern else 'library.json')
        self.data = json.loads(library_path.read_text(encoding='utf-8'))
        self.papers = {p['paper_id']: p for p in self.data['papers']}
        self.client = client or ZoteroClient()
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        work = self.report / ('state' if modern else '_work')
        work.mkdir(exist_ok=True)
        self.db_path = work / ('library.sqlite3' if modern else 'zotero-imports.sqlite3')
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS receipts (fingerprint TEXT, library_id TEXT, state TEXT, session TEXT, target TEXT, result TEXT, PRIMARY KEY(fingerprint, library_id))')
            db.execute('CREATE TABLE IF NOT EXISTS favorites (fingerprint TEXT PRIMARY KEY)')

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.db_path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def status(self):
        try:
            target = self.client.target()
        except ZoteroError:
            return {'connected': False, 'message': '请打开 Zotero 桌面版，然后点击“刷新连接”。'}
        with self.db() as db:
            receipts = {row[0]: {'state': row[1], 'target': row[2]} for row in db.execute('SELECT fingerprint, state, target FROM receipts WHERE library_id=?', (target['library_id'],))}
        return {'connected': True, 'target': target, 'receipts': receipts, 'demo': bool(self.data.get('demo'))}

    def favorites(self):
        with self.db() as db:
            return {'favorites': [row[0] for row in db.execute('SELECT fingerprint FROM favorites ORDER BY fingerprint')]}

    def set_favorite(self, paper_id, favorite):
        paper = self.papers.get(paper_id)
        if paper is None:
            return 404, {'message': '没有找到这篇论文，请重新打开报告。'}
        if not isinstance(favorite, bool):
            return 400, {'message': '收藏状态无效。'}
        with self.db() as db:
            if favorite:
                db.execute('INSERT OR IGNORE INTO favorites VALUES (?)', (paper['fingerprint'],))
            else:
                db.execute('DELETE FROM favorites WHERE fingerprint=?', (paper['fingerprint'],))
        return 200, {'fingerprint': paper['fingerprint'], 'favorite': favorite}

    def import_paper(self, paper_id, expected_target):
        if self.data.get('demo'):
            return 403, {'message': '模板示例不会写入 Zotero。'}
        paper = self.papers.get(paper_id)
        if paper is None:
            return 404, {'message': '没有找到这篇论文，请重新打开报告。'}
        if not paper['url'] and not paper['doi']:
            return 422, {'message': '缺少可核验的论文链接或 DOI，先补全来源再导入。'}
        with self.lock:
            try:
                target = self.client.target()
            except ZoteroError:
                return 503, {'message': '未连接 Zotero，请打开桌面版后刷新。'}
            if not target['editable']:
                return 403, {'message': '当前 Zotero 保存位置不可写，请切换到可编辑的文献库。'}
            if not expected_target or target['id'] != expected_target:
                return 409, {'message': 'Zotero 保存位置已改变，请刷新连接后再添加。'}
            key = (paper['fingerprint'], target['library_id'])
            target_name = target['library_name'] + (' / ' + target['name'] if target['name'] != target['library_name'] else '')
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT state, target FROM receipts WHERE fingerprint=? AND library_id=?', key).fetchone()
                if row:
                    if row[0] == 'saved':
                        return 200, {'state': 'saved', 'duplicate': True, 'message': '本报告已添加到 ' + row[1] + '，未重复导入。'}
                    return 409, {'state': 'uncertain', 'message': '上次导入结果待核实。请先在 Zotero 中检查此论文，程序不会自动重复写入。'}
                session = 'paper-library-' + uuid.uuid4().hex
                db.execute('INSERT INTO receipts VALUES (?, ?, ?, ?, ?, ?)', (*key, 'pending', session, target_name, ''))
            try:
                items = self.client.import_ris(make_ris(paper), session)
                if not isinstance(items, list) or not items:
                    raise ZoteroError('Import returned no item records.')
                # The connector chooses the currently selected destination; verify it did not change.
                after = self.client.target()
                if after['id'] != target['id']:
                    raise ZoteroError('Destination changed during import.')
            except ZoteroError:
                with self.db() as db:
                    db.execute('UPDATE receipts SET state=? WHERE fingerprint=? AND library_id=?', ('uncertain', *key))
                return 502, {'state': 'uncertain', 'message': 'Zotero 未返回可确认的结果，或保存位置已变化。请在 Zotero 检查，勿重复导入；也可保留 RIS 备用。'}
            with self.db() as db:
                db.execute('UPDATE receipts SET state=?, result=? WHERE fingerprint=? AND library_id=?', ('saved', json.dumps(items, ensure_ascii=False), *key))
            return 200, {'state': 'saved', 'message': '已添加到 ' + target_name}


def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed(self, api=False):
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                return False
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + expected:
                return False
            return not api or secrets.compare_digest(self.headers.get('X-Paper-Library-Token', ''), bridge.token)

        def send(self, status, payload, content_type='application/json; charset=utf-8'):
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8') if isinstance(payload, dict) else payload
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = parse.urlsplit(self.path).path
            if not self.allowed(api=path.startswith('/api/')):
                return self.send(403, {'message': '请求来源无效，请从本地报告页面操作。'})
            if path in ('/', '/index.html'):
                page = (bridge.report / 'index.html').read_text(encoding='utf-8')
                config = '<script id="bridge-config" type="application/json">' + json_script({'token': bridge.token}) + '</script>'
                page = page.replace(BRIDGE_MARKER, config, 1)
                return self.send(200, page.encode('utf-8'), 'text/html; charset=utf-8')
            if path == '/api/status':
                return self.send(200, bridge.status())
            if path == '/api/favorites':
                try:
                    return self.send(200, bridge.favorites())
                except (OSError, sqlite3.Error):
                    return self.send(500, {'message': '收藏记录暂时无法读取，请重新打开页面重试。'})
            return self.send(404, {'message': 'Not found'})

        def do_POST(self):
            if not self.allowed(api=True):
                return self.send(403, {'message': '请求来源无效。'})
            if self.path not in ('/api/import', '/api/favorites'):
                return self.send(404, {'message': 'Not found'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size < 8192 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Invalid body')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict) or not isinstance(data.get('paper_id'), str):
                    raise ValueError('Invalid paper')
                if self.path == '/api/favorites':
                    status, result = bridge.set_favorite(data['paper_id'], data.get('favorite'))
                else:
                    status, result = bridge.import_paper(data['paper_id'], data.get('expected_target'))
                self.send(status, result)
            except (ValueError, TypeError):
                self.send(400, {'message': '请求格式无效。'})
            except (OSError, sqlite3.Error):
                if self.path == '/api/favorites':
                    self.send(500, {'message': '收藏保存失败，请重新打开页面核对后重试。'})
                else:
                    self.send(500, {'state': 'uncertain', 'message': '本地导入记录无法写入，请检查 Zotero 后再处理。'})

    return Handler


def serve(report, port=0, open_browser=False):
    bridge = Bridge(report)
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(bridge))
    address = f'http://127.0.0.1:{server.server_port}/'
    print(address, flush=True)
    print('Keep this window open while using Zotero buttons. Ctrl+C stops the local bridge.', flush=True)
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('new', help='Create a dated report folder under root/searches/topic.')
    command.add_argument('--root', type=Path, default=Path('E:/paper'))
    command.add_argument('--topic', required=True)
    command.add_argument('--scope', default='跨来源')
    command = sub.add_parser('build')
    command.add_argument('input', type=Path)
    command.add_argument('--output', type=Path, required=True)
    command.add_argument('--coverage', type=Path)
    command.add_argument('--title')
    command.add_argument('--demo', action='store_true')
    command.add_argument('--continue-from', type=Path, help='Copy a previous report state snapshot; preserve the original.')
    command = sub.add_parser('serve')
    command.add_argument('--report', type=Path, required=True)
    command.add_argument('--port', type=int, default=0)
    command.add_argument('--open', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            print(build(args.input, args.output, args.coverage, args.title, args.demo, args.continue_from))
        elif args.command == 'new':
            print(new_report(args.root, args.topic, args.scope))
        else:
            serve(args.report, args.port, args.open)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
