"""GitHub transport and review coordination; never executes repository code."""
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from .review import ReviewError, baseline_findings, digest
from .reports import markdown

class GitHubError(ReviewError):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class GitHub:
    def __init__(self, repo, token, opener=None, sleep=time.sleep):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo or ''):
            raise GitHubError('GitHub repositoryの形式が不正です。')
        if not token:
            raise GitHubError('GitHubトークンがありません。')
        self.repo, self.token = repo, token
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.sleep = sleep

    def request(self, path, method='GET', data=None, redirect=False):
        url = 'https://api.github.com' + path
        body = json.dumps(data).encode() if data is not None else None
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'infra-xray', 'Content-Type': 'application/json'}
        # Retry only reads and idempotent PATCH. Never duplicate POST on an ambiguous failure.
        attempts = 3 if method in ('GET', 'PATCH') else 1
        for attempt in range(attempts):
            try:
                with self.opener.open(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=20) as response:
                    raw = response.read(10*1024*1024+1)
                    if len(raw) > 10*1024*1024:
                        raise GitHubError('GitHubレスポンスが大きすぎます。')
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as error:
                if redirect and error.code == 302:
                    return error.headers.get('Location')
                if (error.code in (429, 500, 502, 503, 504) or (error.code == 403 and (error.headers.get('Retry-After') or error.headers.get('X-RateLimit-Remaining') == '0'))) and attempt+1 < attempts:
                    self.sleep(2 ** attempt)
                    continue
                if error.code in (401, 403):
                    raise GitHubError('GitHubの認証または権限が不足しています。') from None
                if error.code == 404:
                    raise GitHubError('GitHubの対象が見つからないか、アクセス権限がありません。') from None
                raise GitHubError('GitHub APIの処理が失敗しました。') from None
            except (urllib.error.URLError, OSError, ValueError):
                if attempt+1 < attempts:
                    self.sleep(2 ** attempt)
                    continue
                raise GitHubError('GitHubへの接続またはレスポンスの処理に失敗しました。') from None

    def api(self, suffix, **kwargs):
        return self.request('/repos/' + self.repo + suffix, **kwargs)

    def pages(self, suffix, key=None, max_pages=20):
        for page in range(1, max_pages+1):
            sep = '&' if '?' in suffix else '?'
            result = self.api(suffix + sep + 'per_page=100&page=' + str(page))
            items = result[key] if key else result
            if not isinstance(items, list):
                raise GitHubError('GitHub一覧の形式が不正です。')
            yield from items
            if len(items) < 100:
                return
        raise GitHubError('GitHub一覧の検索上限に達しました。')

    def artifact_json(self, artifact):
        location = self.api('/actions/artifacts/' + str(int(artifact['id'])) + '/zip', redirect=True)
        # Download signed content WITHOUT Authorization, including subsequent redirects.
        for _ in range(4):
            if not isinstance(location, str) or urllib.parse.urlparse(location).scheme != 'https':
                raise GitHubError('artifactのダウンロード先が不正です。')
            try:
                with self.opener.open(urllib.request.Request(location, headers={'User-Agent': 'infra-xray'}), timeout=30) as response:
                    raw = response.read(25*1024*1024+1)
                break
            except urllib.error.HTTPError as error:
                if error.code in (301, 302, 303, 307, 308):
                    location = error.headers.get('Location')
                    continue
                raise GitHubError('artifactを取得できません。') from None
        else:
            raise GitHubError('artifactのリダイレクト上限に達しました。')
        if len(raw) > 25*1024*1024:
            raise GitHubError('artifactがサイズ上限を超えています。')
        checksum = artifact.get('digest')
        if checksum and checksum != 'sha256:' + hashlib.sha256(raw).hexdigest():
            raise GitHubError('artifactのチェックサムが一致しません。')
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                # Never extract paths from an untrusted ZIP.
                matches = [m for m in archive.infolist() if m.filename == 'report.json']
                if len(matches) != 1 or matches[0].file_size > 10*1024*1024:
                    raise GitHubError('artifactのレポート形式・サイズが不正です。')
                return json.loads(archive.read(matches[0]))
        except (ValueError, zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError):
            raise GitHubError('artifactのレポートを読み込めません。') from None

def artifact_name(target):
    return 'infra-xray-review-' + hashlib.sha256(target.encode()).hexdigest()[:20]

def find_baseline(client, pr, run_id, target, rules_hash):
    """Same workflow/PR/target, older completed run, even if its policy failed."""
    current = client.api('/actions/runs/' + str(run_id))
    workflow_id = int(current['workflow_id'])
    if not any(p.get('number') == pr for p in current.get('pull_requests', [])):
        return None, 'unavailable'
    runs = list(client.pages('/actions/workflows/' + str(workflow_id) + '/runs?event=pull_request', 'workflow_runs', max_pages=5))
    for run in sorted(runs, key=lambda r: int(r['id']), reverse=True):
        if int(run['id']) >= run_id or run.get('status') != 'completed' or not any(p.get('number') == pr for p in run.get('pull_requests', [])):
            continue
        artifacts = client.pages('/actions/runs/' + str(int(run['id'])) + '/artifacts', 'artifacts')
        for artifact in artifacts:
            if artifact.get('name') != artifact_name(target) or artifact.get('expired'):
                continue
            try:
                report = client.artifact_json(artifact)
                baseline_findings(report, target, rules_hash)
                if report.get('pr') != pr or report.get('run_id') != int(run['id']) or report.get('commit') != run.get('head_sha'):
                    continue
                return report, 'compared'
            except (ReviewError, OSError, ValueError, KeyError):
                continue
    return None, 'unavailable' if any(int(r['id']) < run_id for r in runs) else 'initial'

def publish_comment(client, report, *, enabled=False, details=False, allow_fork=False):
    if not enabled:
        return 'disabled'
    pr, commit = report['pr'], report['commit']
    if not pr or not commit or not report['run_id']:
        raise GitHubError('投稿にはPR番号・完全なSHA・実行IDが必要です。')
    marker = '<!-- infra-xray:v1:' + digest([client.repo, pr, report['target']]) + ' -->'
    try:
        bot = client.request('/user')
    except GitHubError:
        if os.environ.get('GITHUB_ACTIONS') != 'true':
            raise
        bot = client.request('/users/github-actions%5Bbot%5D')
    # A PAT can update a human-authored comment accidentally; accept bot identities only.
    if bot.get('type') != 'Bot':
        raise GitHubError('コメント投稿にはGitHubのBotトークンが必要です。')
    def check_head():
        pull = client.api('/pulls/' + str(pr))
        if pull.get('state') != 'open' or pull.get('head', {}).get('sha') != commit:
            return False
        if not allow_fork and pull.get('head', {}).get('repo', {}).get('full_name') != client.repo:
            return False
        return True
    if not check_head():
        return 'stale_or_fork'
    own = [c for c in client.pages('/issues/' + str(pr) + '/comments')
           if c.get('user', {}).get('id') == bot.get('id') and c.get('body', '').startswith(marker)]
    if len(own) > 1:
        raise GitHubError('同じ解析対象のBotコメントが複数あります。手動で整理してください。')
    for comment in own:
        match = re.search(r'<!-- run:(\d+) -->', comment.get('body', ''))
        if match and int(match.group(1)) > report['run_id']:
            return 'stale_run'
    link = 'https://github.com/' + client.repo + '/actions/runs/' + str(report['run_id'])
    body = marker + '\n<!-- run:' + str(report['run_id']) + ' -->\n' + markdown(report, details=details, max_bytes=55000) + '\n[詳細レポート・実行履歴](' + link + ')\n'
    # This check is immediately before the write; workflow concurrency serializes writers.
    if not check_head():
        return 'stale_or_fork'
    if own:
        client.api('/issues/comments/' + str(int(own[0]['id'])), method='PATCH', data={'body': body})
        return 'updated'
    client.api('/issues/' + str(pr) + '/comments', method='POST', data={'body': body})
    return 'created'
