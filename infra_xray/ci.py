"""Thin Actions adapter. Analysis and publication run in separate jobs."""
import json
import os
import re
import sys
from pathlib import Path
from .review import (ReviewError, config_from, load_json, make_review, digest, RULES,
                     baseline_findings)
from .reports import render, markdown
from .review_cli import write_output
from .github import GitHub, GitHubError, artifact_name, find_baseline, publish_comment


def enabled(name):
    value = os.environ.get(name, 'false')
    if value not in ('true', 'false'):
        raise ReviewError('Actionsのboolean入力はtrue / falseで指定してください。')
    return value == 'true'


def context():
    event = load_json(os.environ['GITHUB_EVENT_PATH'], 2*1024*1024)
    pull = event.get('pull_request') or {}
    pr = pull.get('number') or event.get('number') if pull else None
    commit = pull.get('head', {}).get('sha') or os.environ.get('GITHUB_SHA')
    run_id = int(os.environ['GITHUB_RUN_ID'])
    repo = os.environ['GITHUB_REPOSITORY']
    fork = bool(pull and pull.get('head', {}).get('repo', {}).get('full_name') != repo)
    return pr, commit, run_id, repo, fork


def output(key, value):
    # All values here are generated paths, numeric codes or hashes, never plan values.
    if '\n' in str(value) or '\r' in str(value):
        raise ReviewError('Actionsの出力値が不正です。')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write(key + '=' + str(value) + '\n')


def analyze_action():
    target = os.environ.get('IX_TARGET', 'default')
    config_path = os.environ.get('IX_CONFIG')
    config = config_from(load_json(config_path, 1024*1024) if config_path else None)
    pr, commit, run_id, repo, fork = context()
    # Validate metadata and input BEFORE any integration calls.
    data = load_json(os.environ['IX_PLAN'], config['max_input_bytes'])
    report = make_review(data, config, target=target, pr=pr, commit=commit, run_id=run_id)
    baseline, notice = None, None
    if enabled('IX_BASELINE') and pr:
        token = os.environ.get('IX_READ_TOKEN')
        if token:
            try:
                baseline, state = find_baseline(GitHub(repo, token), pr, run_id, target, report['rules_fingerprint'])
                notice = state == 'unavailable'
            except Exception:  # Untrusted integration data must not escape in tracebacks.
                notice = True
        else:
            notice = True
        report = make_review(data, config, target=target, pr=pr, commit=commit, run_id=run_id,
                             baseline=baseline, baseline_notice=notice)
    name = artifact_name(target)
    directory = Path(os.environ['RUNNER_TEMP']) / name / str(run_id)
    directory.mkdir(parents=True, exist_ok=True)
    # Remove stale generated files on same-run retries; no arbitrary tree deletion.
    for filename in ('report.json', 'report.md', 'report.html'):
        (directory / filename).unlink(missing_ok=True)
    output('artifact-name', name)
    output('report-dir', directory)
    output('exit-code', 2)
    for format, filename in (('json', 'report.json'), ('markdown', 'report.md'), ('html', 'report.html')):
        write_output(directory / filename, render(report, format), config['max_output_bytes'])
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write(markdown(report, details=False))
    output('exit-code', report['check']['exit_code'])
    return 0  # Upload first; the final action step applies the policy exit code.


def validate_publication(report, target, pr, commit, run_id):
    if not isinstance(report, dict) or report.get('schema_version') != 1 or report.get('analysis_status') != 'success':
        raise ReviewError('投稿対象のレポート形式が不正です。')
    if any(report.get(k) != v for k, v in (('target', target), ('pr', pr), ('commit', commit), ('run_id', run_id))):
        raise ReviewError('投稿対象と現在のPR・コミット・実行が一致しません。')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', target):
        raise ReviewError('解析対象名が不正です。')
    for field in ('config_fingerprint', 'rules_fingerprint'):
        if not isinstance(report.get(field), str) or not re.fullmatch(r'[0-9a-f]{64}', report[field]):
            raise ReviewError('レポートの識別情報が不正です。')
    for field in ('tool_version', 'analyzed_at'):
        if not isinstance(report.get(field), str) or len(report[field]) > 100:
            raise ReviewError('レポートのメタデータが不正です。')
    if not isinstance(report.get('enabled_rules'), list) or any(r not in RULES for r in report['enabled_rules']):
        raise ReviewError('レポートのルールが不正です。')
    if report.get('check', {}).get('status') not in ('passed', 'policy_failed'):
        raise ReviewError('レポートの判定が不正です。')
    summary = report.get('summary', {})
    values = [summary.get(k) for k in ('findings', 'new', 'suppressed', 'unknown', 'ignored_resources')]
    values += [summary.get('changes', {}).get(k) for k in ('create', 'update', 'delete', 'replace', 'no-change', 'read')]
    if any(type(v) is not int or not 0 <= v <= 1000000 for v in values):
        raise ReviewError('レポートの件数が不正です。')
    baseline_findings(report, target, report['rules_fingerprint'])
    for f in report['findings']:
        if f.get('comparison') not in ('New', 'Existing', 'Uncompared') or type(f.get('suppressed')) is not bool:
            raise ReviewError('レポートの比較結果が不正です。')
        if any(not isinstance(f.get(k), str) for k in ('title', 'reason', 'evidence', 'limitations', 'severity')):
            raise ReviewError('レポートの診断内容が不正です。')
    # Remaining free text is escaped by Markdown renderer; never render raw HTML.
    return report


def publish_action():
    if not enabled('IX_POST_COMMENT'):
        print('コメント投稿は無効です。')
        return 0
    required = enabled('IX_PUBLISH_REQUIRED')
    try:
        pr, commit, run_id, repo, fork = context()
        if not pr or fork:
            print('PR以外または外部forkのため投稿を省略しました。')
            return 0
        report = validate_publication(load_json(os.environ['IX_REPORT'], 10*1024*1024),
                                      os.environ['IX_TARGET'], pr, commit, run_id)
        result = publish_comment(GitHub(repo, os.environ.get('IX_WRITE_TOKEN')), report,
                                 enabled=True, details=enabled('IX_COMMENT_DETAILS'))
        print('コメント結果: ' + result)
        return 0
    except Exception:  # Untrusted integration data must not escape in tracebacks.
        # Do not echo third-party API bodies, tokens, file paths or input values.
        print('コメント連携に失敗しました。権限・対象SHA・レポート形式を確認してください。レポートは保持されています。', file=sys.stderr)
        return 2 if required else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv == ['analyze']:
            return analyze_action()
        if argv == ['publish']:
            return publish_action()
    except Exception:  # Top-level CI boundary; errors are fixed, non-sensitive text.
        print('解析エラー: plan・設定・実行コンテキストを確認してください。', file=sys.stderr)
        return 2
    print('analyze または publishを指定してください。', file=sys.stderr)
    return 2

if __name__ == '__main__':
    raise SystemExit(main())
