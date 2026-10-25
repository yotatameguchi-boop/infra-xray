"""Safe static report renderers. Raw Terraform JSON is never accepted here."""
import html
import json
import re
import secrets
from pathlib import Path
from .review import ReviewError

STATIC = Path(__file__).parent / 'static'

def json_text(report):
    return json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'

def escape(value):
    text = html.escape(str(value), quote=True).replace('@', '&#64;')
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', text).replace('\n', '<br>')

def markdown(report, details=True, max_bytes=60000):
    s = report['summary']
    lines = ['## Infra X-Ray review', '', '**' + escape(report['target']) + '** · ' + escape(report['check']['status']),
             '', '- Commit: ' + escape(report['commit'] or '未指定'),
             '- PR / run: ' + escape(str(report['pr'] or '—') + ' / ' + str(report['run_id'] or '—')),
             '- Analyzed: ' + escape(report['analyzed_at']),
             '- Tool / schema: ' + escape(report['tool_version']) + ' / ' + str(report['schema_version']),
             '- Rules: ' + escape(', '.join(report['enabled_rules'])),
             '- Config: ' + report['config_fingerprint'],
             '- Changes: ' + ', '.join(k + '=' + str(v) for k, v in ((k, s['changes'][k]) for k in ('create', 'update', 'delete', 'replace', 'no-change', 'read'))),
             '- Findings: ' + str(s['findings']) + ' · New: ' + str(s['new']) + ' · Suppressed: ' + str(s['suppressed']),
             '- Not evaluated (unknown): ' + str(s['unknown']) + ' · Unsupported resources: ' + str(s['ignored_resources']),
             '', escape(report['comparison']['message']), '', '**警告なしは安全性の保証ではありません。**',
             '', '線はTerraformの参照関係であり、実際の通信経路ではありません。']
    if details:
        lines += ['', '### Findings']
        for f in report['findings']:
            lines += ['', '#### ' + escape(f['id']) + ' · ' + escape(f['title']),
                      '- Resource: ' + escape(f['resource']), '- Comparison: ' + escape(f['comparison']),
                      '- Suppressed: ' + escape(f['suppressed']), '- Reason: ' + escape(f['reason']),
                      '- Evidence: ' + escape(f['evidence']), '- Limitations: ' + escape(f['limitations'])]
            if f['suppression']:
                lines += ['- Suppression reason: ' + escape(f['suppression']['reason']),
                          '- Expires (UTC): ' + escape(f['suppression']['expires']),
                          '- Expired: ' + escape(f['suppression']['expired'])]
        lines += ['', '### Resource changes (allowlisted attributes)']
        for n in report['graph']['nodes']:
            lines += ['', '#### ' + escape(n['id']), '- Action: ' + escape(n['action']), '- Type: ' + escape(n['type'])]
            for edge in report['graph']['edges']:
                if n['id'] in (edge['source'], edge['target']):
                    lines += ['- Terraform reference: ' + escape(edge['source']) + ' → ' + escape(edge['target'])]
            for side in ('before', 'after'):
                lines += ['- ' + side + ': ' + escape(json.dumps(n[side], ensure_ascii=False, sort_keys=True))]
        lines += ['', '### Comparison history']
        for f in report['historical']:
            lines += ['- ' + escape(f['id']) + ': ' + escape(f['resource']) + ' · ' + escape(f['comparison']) + ' · ' + escape(f['reason'])]
        lines += ['', '### Cannot evaluate']
        for e in report['evaluations']:
            if e['status'] == 'unknown':
                lines += ['- ' + escape(e['id']) + ': ' + escape(e['resource']) + ' · ' + escape(e['reason'])]
    else:
        lines += ['', '詳細な属性値・アドレスは省略しています。Actionsのレポートを参照してください。']
    lines += ['', '### Scope and limitations'] + ['- ' + escape(x) for x in report['graph']['limitations']]
    output = '\n'.join(lines) + '\n'
    if len(output.encode()) > max_bytes:
        suffix = '\n\n…出力上限のため省略しました。完全なJSON / HTMLレポートを確認してください。\n'
        output = output.encode()[:max(0, max_bytes-len(suffix.encode()))].decode('utf-8', errors='ignore') + suffix
    return output

def standalone_html(report):
    try:
        index = (STATIC / 'index.html').read_text()
        scripts = re.findall(r'<script[^>]+src="(/assets/[^"]+\.js)"[^>]*></script>', index)
        styles = re.findall(r'<link[^>]+href="(/assets/[^"]+\.css)"[^>]*>', index)
        if len(scripts) != 1 or not styles:
            raise ReviewError('対応するUIビルドが必要です。')
        def asset(name):
            path = (STATIC / name.lstrip('/')).resolve()
            if STATIC.resolve() not in path.parents:
                raise ReviewError('UIビルドのパスが不正です。')
            return path.read_text()
        js = asset(scripts[0]).replace('</script', '<\\/script')
        css = '\n'.join(asset(x) for x in styles).replace('</style', '<\\/style')
    except OSError:
        raise ReviewError('HTML出力にはビルド済みUIが必要です。') from None
    nonce = secrets.token_urlsafe(24)
    # Escape ALL '<' including closing script tags and U+2028/U+2029.
    payload = json_text(report).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    csp = "default-src 'none'; script-src 'nonce-" + nonce + "'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; font-src data:; base-uri 'none'; form-action 'none'"
    return ('<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            + '<meta http-equiv="Content-Security-Policy" content="' + html.escape(csp, quote=True) + '">'
            + '<title>Infra X-Ray · ' + html.escape(report['target']) + '</title><style>' + css + '</style></head><body><div id="root"></div>'
            + '<script id="infra-xray-review" type="application/json" nonce="' + nonce + '">' + payload + '</script>'
            + '<script type="module" nonce="' + nonce + '">' + js + '</script></body></html>')

def render(report, format):
    if format == 'json':
        return json_text(report)
    if format == 'markdown':
        return markdown(report)
    if format == 'html':
        return standalone_html(report)
    raise ReviewError('未対応の出力形式です。')
