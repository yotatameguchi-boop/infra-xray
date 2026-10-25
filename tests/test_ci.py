import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from infra_xray import ci
from infra_xray.review import ReviewError
from test_review import sample, SHA

@pytest.fixture
def environment(tmp_path,monkeypatch):
    event=tmp_path/'event.json';event.write_text(json.dumps({'number':1,'pull_request':{'number':1,'head':{'sha':SHA,'repo':{'full_name':'owner/repo'}}}}))
    plan=tmp_path/'private-plan.json';plan.write_text(json.dumps(sample()))
    output=tmp_path/'output';summary=tmp_path/'summary'
    env={'GITHUB_EVENT_PATH':str(event),'GITHUB_RUN_ID':'10','GITHUB_REPOSITORY':'owner/repo','GITHUB_SHA':SHA,'GITHUB_OUTPUT':str(output),'GITHUB_STEP_SUMMARY':str(summary),'RUNNER_TEMP':str(tmp_path),'IX_PLAN':str(plan),'IX_TARGET':'production','IX_BASELINE':'false','IX_POST_COMMENT':'false','IX_PUBLISH_REQUIRED':'false','IX_COMMENT_DETAILS':'false'}
    for k,v in env.items():monkeypatch.setenv(k,v)
    return tmp_path,env

def outputs(path):return dict(line.split('=',1) for line in Path(path).read_text().splitlines())

def test_analysis_upload_surface_and_policy_exit(environment,monkeypatch):
    root,env=environment;config=root/'config.json';config.write_text(json.dumps({'fail_on_rules':['DB-001']}));monkeypatch.setenv('IX_CONFIG',str(config))
    assert ci.main(['analyze'])==0
    values=outputs(env['GITHUB_OUTPUT']);assert values['exit-code']=='1'
    files={p.name for p in Path(values['report-dir']).iterdir()};assert files=={'report.json','report.md','report.html'}
    assert 'aws_db_instance' not in Path(env['GITHUB_STEP_SUMMARY']).read_text()
    report=json.loads((Path(values['report-dir'])/'report.json').read_text());assert report['pr']==1 and report['commit']==SHA

def test_generated_json_retained_if_html_fails(environment,monkeypatch):
    _,env=environment;original=ci.render
    def fail(report,format):
        if format=='html':raise ReviewError('UI unavailable')
        return original(report,format)
    monkeypatch.setattr(ci,'render',fail)
    assert ci.main(['analyze'])==2
    values=outputs(env['GITHUB_OUTPUT']);assert values['exit-code']=='2'
    assert (Path(values['report-dir'])/'report.json').is_file()

def test_publish_disabled_and_fork_safe(environment,monkeypatch):
    _,env=environment
    mocked=Mock();monkeypatch.setattr(ci,'GitHub',mocked)
    assert ci.main(['publish'])==0;mocked.assert_not_called()
    monkeypatch.setenv('IX_POST_COMMENT','true')
    event=json.loads(Path(env['GITHUB_EVENT_PATH']).read_text());event['pull_request']['head']['repo']['full_name']='fork/repo';Path(env['GITHUB_EVENT_PATH']).write_text(json.dumps(event))
    assert ci.main(['publish'])==0;mocked.assert_not_called()

def test_optional_and_required_publish_errors(environment,monkeypatch,capsys):
    root,env=environment;monkeypatch.setenv('IX_POST_COMMENT','true');monkeypatch.setenv('IX_REPORT',str(root/'SECRET_CANARY'))
    assert ci.main(['publish'])==0
    monkeypatch.setenv('IX_PUBLISH_REQUIRED','true');assert ci.main(['publish'])==2
    assert 'CANARY' not in capsys.readouterr().err

def test_baseline_permission_failure_continues(environment,monkeypatch):
    _,env=environment;monkeypatch.setenv('IX_BASELINE','true');monkeypatch.setenv('IX_READ_TOKEN','FAKE')
    monkeypatch.setattr(ci,'find_baseline',Mock(side_effect=ReviewError('unavailable')))
    assert ci.main(['analyze'])==0
    report=json.loads((Path(outputs(env['GITHUB_OUTPUT'])['report-dir'])/'report.json').read_text())
    assert report['comparison']['status']=='unavailable'

def test_malformed_publication_never_prints_input_or_traceback(environment,monkeypatch,capsys):
    root,_=environment
    from test_review import review
    report=review(target='production');report['check']=['CANARY']
    path=root/'malformed.json';path.write_text(json.dumps(report))
    monkeypatch.setenv('IX_POST_COMMENT','true');monkeypatch.setenv('IX_PUBLISH_REQUIRED','true');monkeypatch.setenv('IX_REPORT',str(path))
    assert ci.main(['publish'])==2
    captured=capsys.readouterr();assert 'CANARY' not in captured.err and 'Traceback' not in captured.err
