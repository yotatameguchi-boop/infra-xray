import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import pytest
from infra_xray.review import ReviewError, make_review, config_from
from infra_xray.reports import render, markdown

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,10,25,12,tzinfo=timezone.utc)
SHA='a'*40

def sample(name='review'):
    return json.loads((ROOT/'examples/synthetic-plans'/f'{name}.json').read_text())

def review(data=None, config=None, **kwargs):
    return make_review(data if data is not None else sample(),config,now=NOW,commit=SHA,pr=1,run_id=10,**kwargs)

def db(after=True):
    return {'format_version':'1.2','terraform_version':'1.9.8','planned_values':{},'resource_changes':[{'address':'aws_db_instance.test','type':'aws_db_instance','change':{'actions':['update'],'before':{'publicly_accessible':False},'after':{'publicly_accessible':after}}}]}

def suppression(**changes):
    return {'rule_id':'DB-001','resource':'aws_db_instance.test','reason':'Approved temporary exposure','expires':'2026-10-25',**changes}

def test_default_nonblocking_and_evidence():
    r=review()
    assert r['check']['exit_code']==0 and r['summary']['findings']==3
    assert r['summary']['changes']['replace']==1
    assert all(f['comparison']=='New' for f in r['findings'])
    assert len(r['evaluations'])==27
    assert r['comparison']['status']=='initial'
    assert all('evidence' in f for f in r['findings'])

@pytest.mark.parametrize('config',[{'fail_on_rules':['DB-001']},{'fail_on_severities':['high']}])
def test_policy_blocks_only_when_enabled(config):
    assert review(config=config)['check']['exit_code']==1
    assert review(sample('safe'),config)['check']['exit_code']==0

def test_unknown_policy_and_no_false_resolution():
    old=review(db())
    data=db();data['resource_changes'][0]['change']['after_unknown']={'publicly_accessible':True}
    r=review(data,{'fail_on_unknown':True},baseline=old)
    assert r['summary']['unknown']==1 and r['check']['exit_code']==1
    assert r['historical'][0]['comparison']=='Not evaluated'
    assert not r['findings']

@pytest.mark.parametrize('mutation',['missing','not_applicable','disabled'])
def test_disappearance_does_not_resolve(mutation):
    old=review(db());data=db();config={}
    if mutation=='missing':data['resource_changes']=[]
    if mutation=='not_applicable':data['resource_changes'][0]['change']['actions']=['no-op']
    if mutation=='disabled':config={'enabled_rules':['OPS-001']}
    r=review(data,config,baseline=old)
    assert not any(f['comparison']=='Resolved' for f in r['historical'])
    if mutation=='disabled':assert r['comparison']['status']=='unavailable'

def test_resolved_requires_evaluation_and_existing_stable_keys():
    old=review(db());same=review(db(),baseline=old)
    assert same['findings'][0]['comparison']=='Existing'
    assert same['findings'][0]['key']==old['findings'][0]['key']
    fixed=review(db(False),baseline=old)
    assert fixed['historical'][0]['comparison']=='Resolved'

def test_only_new_and_incompatible_baseline_conservative():
    old=review(db());config={'only_new':True,'fail_on_rules':['DB-001']}
    assert review(db(),config,baseline=old)['check']['exit_code']==0
    old['target']='different'
    r=review(db(),config,baseline=old)
    assert r['check']['exit_code']==1 and r['findings'][0]['comparison']=='Uncompared'

def test_suppression_and_expiry():
    old=review(db())
    config={'fail_on_rules':['DB-001'],'suppressions':[suppression()]}
    r=review(db(),config,baseline=old)
    assert r['summary']['suppressed']==1 and r['check']['exit_code']==0
    assert r['findings'][0]['comparison']=='Existing'
    assert not r['historical']
    config['suppressions'][0]['expires']='2026-10-24'
    r=review(db(),config)
    assert r['check']['exit_code']==1 and r['findings'][0]['suppression']['expired']

@pytest.mark.parametrize('change',[{'reason':''},{'expires':''},{'expires':'2026-02-31'},{'resource':'aws_db_instance.*'},{'rule_id':'UNKNOWN'}])
def test_invalid_suppression_rejected(change):
    with pytest.raises(ReviewError):config_from({'suppressions':[suppression(**change)]})

@pytest.mark.parametrize('config',[{'unknown':True},{'only_new':'true'},{'enabled_rules':['unknown']},{'fail_on_rules':['SG-001','SG-001']},{'max_input_bytes':True},{'max_output_bytes':0},{'suppressions':[suppression(),suppression()]}])
def test_invalid_config(config):
    with pytest.raises(ReviewError):config_from(config)

def test_deterministic_results():
    assert review()==review()

def test_baseline_extra_values_never_forwarded():
    old=review(db());old['secret']='BASELINE_CANARY';old['graph']['nodes'][0]['after']['password']='BASELINE_CANARY'
    old['findings'][0]['reason']='BASELINE_CANARY'
    assert 'BASELINE_CANARY' not in json.dumps(review(db(False),baseline=old))

def test_all_formats_mask_sensitive_and_escape_html():
    data=db();ch=data['resource_changes'][0]['change']
    ch['after']['password']='PASSWORD_CANARY';ch['after']['publicly_accessible']='FLAG_CANARY';ch['after_sensitive']={'publicly_accessible':True}
    data['variables']={'secret':{'value':'VARIABLE_CANARY'}}
    data['resource_changes'][0]['address']='aws_db_instance.</script><img src=x onerror=alert(1)>'
    r=review(data)
    for format in ('json','markdown','html'):
        text=render(r,format)
        assert 'CANARY' not in text
        if format!='json':assert '<img src=x' not in text
    html=render(r,'html')
    assert "connect-src &#x27;none&#x27;" in html
    assert '\\u003c/script' in html

def test_summary_privacy_and_markdown_bound():
    r=review()
    summary=markdown(r,details=False)
    assert 'aws_db_instance.primary' not in summary
    assert 'publicly_accessible' not in summary
    long=review(db());long['findings'][0]['reason']='x'*100000
    text=markdown(long)
    assert len(text.encode())<=60000 and '省略' in text

def test_cli_atomic_output_exit_and_input_preservation(tmp_path):
    plan=tmp_path/'plan.json';plan.write_text(json.dumps(db()))
    cfg=tmp_path/'config.json';cfg.write_text(json.dumps({'fail_on_rules':['DB-001']}))
    out=tmp_path/'report.json'
    cmd=[sys.executable,'-m','infra_xray','review',str(plan),'--format','json','--config',str(cfg)]
    result=subprocess.run(cmd+['--output',str(out)],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==1 and json.loads(out.read_text())['analysis_status']=='success'
    original=plan.read_text()
    result=subprocess.run(cmd+['--output',str(plan)],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==2 and plan.read_text()==original
    cfg.write_text(json.dumps({'max_output_bytes':1024}))
    out.write_text('EXISTING_OUTPUT')
    result=subprocess.run(cmd+['--output',str(out)],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==2 and out.read_text()=='EXISTING_OUTPUT'

def test_unavailable_baseline_cli_and_error_no_secrets(tmp_path):
    p=tmp_path/'plan.json';p.write_text(json.dumps(db()))
    cmd=[sys.executable,'-m','infra_xray','review',str(p),'--format','json','--baseline',str(tmp_path/'missing')]
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0 and json.loads(result.stdout)['comparison']['status']=='unavailable'
    p.write_text('{"PASSWORD_CANARY":NaN}')
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==2 and 'CANARY' not in result.stdout+result.stderr
