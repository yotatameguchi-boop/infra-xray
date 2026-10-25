"""Versioned review results; no GitHub or presentation dependencies."""
import copy
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from . import __version__
from .adapters import TerraformAdapter
from .rules import ssh_state

RULES = ('SG-001', 'DB-001', 'OPS-001')
DEFAULT_CONFIG = {'schema_version': 1, 'enabled_rules': list(RULES), 'fail_on_rules': [],
                  'fail_on_severities': [], 'only_new': False, 'fail_on_unknown': False,
                  'suppressions': [], 'max_input_bytes': 50 * 1024 * 1024,
                  'max_output_bytes': 10 * 1024 * 1024}

class ReviewError(ValueError):
    """Messages are authored constants, never source JSON or exception text."""

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    allow_nan=False).encode()).hexdigest()

def reject_constant(_):
    raise ReviewError('JSONに非有限数は使用できません。')

def load_json(path, limit):
    try:
        with open(path, 'rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ReviewError('入力サイズの上限を超えています。')
        return json.loads(raw.decode('utf-8-sig'), parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ReviewError('JSONを読み込めません。ファイルと形式を確認してください。') from None

def config_from(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict) or set(value) - set(DEFAULT_CONFIG):
        raise ReviewError('未対応の設定項目または設定形式です。')
    config = {**copy.deepcopy(DEFAULT_CONFIG), **value}
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise ReviewError('設定のschema_versionは1が必要です。')
    for key in ('enabled_rules', 'fail_on_rules', 'fail_on_severities'):
        values = config[key]
        allowed = ('high', 'warning') if key == 'fail_on_severities' else RULES
        if not isinstance(values, list) or any(not isinstance(v, str) or v not in allowed for v in values) or len(values) != len(set(values)):
            raise ReviewError('ルール・重要度の設定が不正です。')
        config[key] = sorted(values)
    for key in ('only_new', 'fail_on_unknown'):
        if type(config[key]) is not bool:
            raise ReviewError('判定設定はbooleanで指定してください。')
    for key in ('max_input_bytes', 'max_output_bytes'):
        if type(config[key]) is not int or not 1024 <= config[key] <= 100 * 1024 * 1024:
            raise ReviewError('サイズ上限は1024〜104857600 bytesで指定してください。')
    if not isinstance(config['suppressions'], list):
        raise ReviewError('suppressionsは配列が必要です。')
    seen = set()
    for s in config['suppressions']:
        if not isinstance(s, dict) or set(s) != {'rule_id', 'resource', 'reason', 'expires'}:
            raise ReviewError('抑制にはrule_id / resource / reason / expiresが必要です。')
        if s['rule_id'] not in RULES or not isinstance(s['resource'], str) or not 1 <= len(s['resource']) <= 1024 or '*' in s['resource']:
            raise ReviewError('抑制には対応ルールと完全一致アドレスを指定してください。')
        if not isinstance(s['reason'], str) or not 1 <= len(s['reason'].strip()) <= 500:
            raise ReviewError('抑制理由は1〜500文字で指定してください。')
        try:
            if not isinstance(s['expires'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', s['expires']):
                raise ValueError()
            date.fromisoformat(s['expires'])
        except (ValueError, TypeError):
            raise ReviewError('抑制期限は有効なYYYY-MM-DDで指定してください。') from None
        key = (s['rule_id'], s['resource'])
        if key in seen:
            raise ReviewError('抑制設定が重複しています。')
        seen.add(key)
    config['suppressions'] = sorted(config['suppressions'], key=lambda s: (s['rule_id'], s['resource']))
    return config

def finding_key(target, resource, rule):
    return digest([target, resource, rule])

def evaluate(node, rule, enabled):
    if rule not in enabled:
        return 'disabled'
    kind, action = node['type'], node['action']
    if rule == 'OPS-001':
        if kind != 'aws_db_instance':
            return 'not_applicable'
        return 'finding' if action in ('delete', 'replace') else 'pass'
    if rule == 'DB-001' and kind != 'aws_db_instance':
        return 'not_applicable'
    if rule == 'SG-001' and kind not in ('aws_security_group', 'aws_vpc_security_group_ingress_rule'):
        return 'not_applicable'
    if action not in ('create', 'update', 'replace'):
        return 'not_applicable'
    if rule == 'DB-001':
        before = False if action == 'create' else node['before'].get('publicly_accessible')
        after = node['after'].get('publicly_accessible')
        if type(before) is not bool or type(after) is not bool:
            return 'unknown'
    else:
        standalone = kind.endswith('ingress_rule')
        before = False if action == 'create' else ssh_state(node['before'], standalone)
        after = ssh_state(node['after'], standalone)
        if before is None or after is None:
            return 'unknown'
    return 'finding' if before is False and after is True else 'pass'

def baseline_findings(value, target, rules_hash):
    """Read only the minimal identity projection; never forward baseline values."""
    if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('analysis_status') != 'success':
        raise ReviewError('比較元のレポート形式に対応していません。')
    if value.get('target') != target or value.get('rules_fingerprint') != rules_hash:
        raise ReviewError('比較元の解析対象またはルール設定が互換ではありません。')
    if not isinstance(value.get('findings'), list):
        raise ReviewError('比較元の診断形式が不正です。')
    previous = {}
    for f in value['findings']:
        if not isinstance(f, dict) or not isinstance(f.get('resource'), str) or not 1 <= len(f['resource']) <= 1024 or f.get('id') not in RULES:
            raise ReviewError('比較元の診断形式が不正です。')
        key = finding_key(target, f['resource'], f['id'])
        if f.get('key') != key or key in previous:
            raise ReviewError('比較元の識別子が不正です。')
        previous[key] = {'key': key, 'resource': f['resource'], 'id': f['id']}
    return previous

def make_review(data, config=None, *, target='default', commit=None, pr=None, run_id=None,
                baseline=None, baseline_notice=None, now=None):
    config = config_from(config)
    if not isinstance(target, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', target):
        raise ReviewError('解析対象名は英数字・ハイフン・アンダースコア・ピリオドの1〜80文字です。')
    if commit is not None and not re.fullmatch(r'[0-9a-fA-F]{40,64}', commit):
        raise ReviewError('commitには完全なコミットSHAを指定してください。')
    for identifier in (pr, run_id):
        if identifier is not None and (type(identifier) is not int or identifier <= 0):
            raise ReviewError('PR番号と実行IDは正の整数が必要です。')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ReviewError('解析日時にはタイムゾーンが必要です。')
    now = now.astimezone(timezone.utc)
    graph = TerraformAdapter().parse(data)
    rule_hash = digest({'engine': 'terraform-aws-rules-v1', 'enabled_rules': config['enabled_rules']})
    comparison = {'status': 'initial', 'message': '初回解析：比較元なし。', 'baseline_commit': None}
    previous = {}
    if baseline is not None:
        try:
            previous = baseline_findings(baseline, target, rule_hash)
            # PR history must not silently cross PR boundaries.
            if baseline.get('pr') != pr:
                raise ReviewError('比較元のPR番号が一致しません。')
            comparison = {'status': 'compared', 'message': '前回レビュー結果との差分です。Terraformのbefore / afterとは別の比較です。',
                          'baseline_commit': baseline.get('commit') if isinstance(baseline.get('commit'), str) and re.fullmatch(r'[0-9a-fA-F]{40,64}', baseline['commit']) else None}
        except ReviewError as error:
            previous = {}
            comparison = {'status': 'unavailable', 'message': str(error), 'baseline_commit': None}
    elif baseline_notice:
        comparison = {'status': 'unavailable', 'message': '比較元を取得できませんでした。比較なしで解析しました。', 'baseline_commit': None}
    evaluations, findings = [], []
    for node in graph['nodes']:
        actual = {f['id']: f for f in node['findings']}
        filtered = []
        for rule in RULES:
            status = evaluate(node, rule, config['enabled_rules'])
            key = finding_key(target, node['id'], rule)
            ev = {'key': key, 'resource': node['id'], 'id': rule, 'status': status}
            if status == 'unknown':
                ev['reason'] = '必要な属性がunknown / sensitive / 欠落のため判定できません。'
            evaluations.append(ev)
            if status != 'finding':
                continue
            f = dict(actual[rule])
            f['key'] = key
            f['comparison'] = 'Existing' if key in previous else ('Uncompared' if comparison['status'] == 'unavailable' else 'New')
            s = next((s for s in config['suppressions'] if s['rule_id'] == rule and s['resource'] == node['id']), None)
            f['suppressed'] = bool(s and date.fromisoformat(s['expires']) >= now.date())
            f['suppression'] = {**s, 'expired': not f['suppressed']} if s else None
            findings.append(f)
            filtered.append(f)
        node['findings'] = filtered
    current_keys = {f['key'] for f in findings}
    eval_by_key = {e['key']: e for e in evaluations}
    historical = []
    for key, old in previous.items():
        if key not in current_keys:
            status = eval_by_key.get(key, {}).get('status')
            historical.append({**old, 'comparison': 'Resolved' if status == 'pass' else 'Not evaluated',
                               'reason': '今回は評価済み・非該当です。' if status == 'pass' else '今回の評価がない、対象外、無効、または判定不能です。解消とは断定しません。'})
    findings.sort(key=lambda f: (f['suppressed'], f['comparison'] != 'New', f['severity'] != 'high', f['resource'], f['id']))
    graph['findings'] = findings
    graph['nodes'].sort(key=lambda n: (n['action'] not in ('delete', 'replace'), not bool(n['findings']), n['id']))
    unknowns = [e for e in evaluations if e['status'] == 'unknown']
    active = [f for f in findings if not f['suppressed']]
    failed = [f['key'] for f in active if (f['id'] in config['fail_on_rules'] or f['severity'] in config['fail_on_severities'])
              and (not config['only_new'] or f['comparison'] in ('New', 'Uncompared'))]
    if config['fail_on_unknown']:
        failed.extend(e['key'] for e in unknowns)
    counts = {action: sum(n['action'] == action for n in graph['nodes']) for action in ('create', 'update', 'delete', 'replace', 'no-change', 'read')}
    return {'schema_version': 1, 'analysis_status': 'success', 'tool_version': __version__, 'target': target,
            'commit': commit, 'pr': pr, 'run_id': run_id, 'analyzed_at': now.isoformat(),
            'config_fingerprint': digest(config), 'rules_fingerprint': rule_hash, 'enabled_rules': config['enabled_rules'],
            'policy': {k: config[k] for k in ('fail_on_rules', 'fail_on_severities', 'only_new', 'fail_on_unknown')},
            'summary': {'changes': counts, 'findings': len(active), 'suppressed': len(findings)-len(active),
                        'unknown': len(unknowns), 'ignored_resources': graph['ignoredResources'],
                        'new': sum(f['comparison'] == 'New' for f in active)},
            'check': {'status': 'policy_failed' if failed else 'passed', 'failed_keys': sorted(failed),
                      'exit_code': 1 if failed else 0},
            'comparison': comparison, 'findings': findings, 'evaluations': evaluations,
            'historical': sorted(historical, key=lambda f: f['key']), 'graph': graph,
            'notices': ['警告なしは安全性の保証ではありません。', '構成情報を含みます。レポートの公開範囲を確認してください。',
                        '抑制期限はUTCの日付で当日末まで有効です。']}
