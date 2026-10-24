import copy
import json
import subprocess
import sys
from pathlib import Path
import pytest
from infra_xray.parser import analyze, load_plan, PlanError

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples' / 'synthetic-plans'

def plan(kind='aws_db_instance', actions=None, before=None, after=None, **kwargs):
    return {'format_version':'1.2','terraform_version':'1.9.8','planned_values':{},'resource_changes':[{'address':kind+'.test','type':kind,'change':{'actions':actions or ['update'],'before':before,'after':after,**kwargs}}]}

def ids(p):
    return [f['id'] for f in analyze(p)['findings']]

def ssh(cidrs=None, protocol='tcp', low=22, high=22):
    return {'ingress':[{'protocol':protocol,'from_port':low,'to_port':high,'cidr_blocks':cidrs or ['0.0.0.0/0']}]}

def test_samples():
    graph=load_plan(EXAMPLES/'review.json')
    assert len(graph['nodes'])==9
    assert {f['id'] for f in graph['findings']}=={'SG-001','DB-001','OPS-001'}
    assert len(graph['edges'])==10
    assert not load_plan(EXAMPLES/'safe.json')['findings']

@pytest.mark.parametrize('actions,expected', [(['create'],'create'),(['update'],'update'),(['delete'],'delete'),(['no-op'],'no-change'),(['delete','create'],'replace'),(['create','delete'],'replace'),(['read'],'read')])
def test_actions(actions,expected):
    assert analyze(plan(actions=actions))['nodes'][0]['action']==expected

@pytest.mark.parametrize('version',['2.0','0.1','1','bad',None,1,{},[]])
def test_version_rejected(version):
    p=plan();p['format_version']=version
    with pytest.raises(PlanError): analyze(p)

def test_minor_accepted():
    p=plan();p['format_version']='1.999';p['future_field']={'password':'CANARY'}
    assert analyze(p)['formatVersion']=='1.999'

@pytest.mark.parametrize('before,after,expected',[(False,True,True),(True,True,False),(True,False,False),(False,False,False),(None,True,False),(False,None,False)])
def test_db_transition(before,after,expected):
    assert ('DB-001' in ids(plan(before={'publicly_accessible':before},after={'publicly_accessible':after})))==expected

def test_db_create_delete():
    assert ids(plan(actions=['create'],after={'publicly_accessible':True}))==['DB-001']
    assert ids(plan(actions=['delete'],before={'publicly_accessible':True}))==['OPS-001']

@pytest.mark.parametrize('protocol,low,high,expected',[('tcp',22,22,True),('6',0,65535,True),('-1',0,0,True),('udp',22,22,False),('tcp',80,443,False),('tcp',23,100,False)])
def test_ssh_range(protocol,low,high,expected):
    p=plan('aws_security_group',['create'],after=ssh(protocol=protocol,low=low,high=high))
    assert ('SG-001' in ids(p))==expected

def test_ssh_already_public_and_narrowing():
    assert not ids(plan('aws_security_group',before=ssh(),after=ssh()))
    assert not ids(plan('aws_security_group',before=ssh(),after=ssh(['10.0.0.0/8'])))
    assert ids(plan('aws_security_group',before=ssh(['10.0.0.0/8']),after=ssh()))==['SG-001']

def test_standalone_ssh():
    p=plan('aws_vpc_security_group_ingress_rule',['create'],after={'cidr_ipv4':'0.0.0.0/0','from_port':0,'to_port':50,'ip_protocol':'6'})
    assert ids(p)==['SG-001']

@pytest.mark.parametrize('mask_key',['after_unknown','after_sensitive'])
def test_unknown_sensitive_no_false_positive(mask_key):
    p=plan(before={'publicly_accessible':False},after={'publicly_accessible':True},**{mask_key:{'publicly_accessible':True}})
    g=analyze(p)
    assert not g['findings'] and g['nodes'][0]['limitations']

def test_sensitive_nested_and_arbitrary_fields_never_escape():
    p=plan('aws_security_group',before={'ingress':[],'secret':'BEFORE_CANARY'},after={'ingress':[{'protocol':'tcp','from_port':22,'to_port':22,'cidr_blocks':['CIDR_CANARY'],'description':'DESC_CANARY'}],'password':'PASSWORD_CANARY','tags':{'Name':'TAG_CANARY'}},after_sensitive={'ingress':[{'cidr_blocks':[True]}]})
    p['variables']={'password':{'value':'VARIABLE_CANARY'}}
    encoded=json.dumps(analyze(p))
    assert 'CANARY' not in encoded
    assert '[sensitive]' in encoded
    assert not ids(p)

def test_whole_resource_sensitive():
    p=plan(after={'publicly_accessible':'SECRET'},after_sensitive=True)
    assert 'SECRET' not in json.dumps(analyze(p))
    assert analyze(p)['nodes'][0]['after']=={'_status':'[sensitive]'}

def test_unknown_missing_attribute():
    p=plan(before={'publicly_accessible':False},after={},after_unknown={'publicly_accessible':True})
    assert analyze(p)['nodes'][0]['after']['publicly_accessible']=='[unknown]'

def test_graph_no_invented_edges():
    p=plan();p['configuration']={'root_module':{'resources':[{'address':'aws_db_instance.test','expressions':{'x':{'references':['aws_vpc.missing.id']}}}]}}
    assert analyze(p)['edges']==[]

def test_nested_configuration_and_index_ambiguity():
    p=plan();p['resource_changes'][0]['address']='module.db.aws_db_instance.test'
    p['resource_changes'].append({'address':'module.db.aws_vpc.main','type':'aws_vpc','change':{'actions':['no-op'],'before':{},'after':{}}})
    p['configuration']={'root_module':{'module_calls':{'db':{'module':{'resources':[{'address':'aws_db_instance.test','expressions':{'vpc':{'references':['aws_vpc.main.id']}}}]}}}}}
    assert len(analyze(p)['edges'])==1
    p['resource_changes'][1]['address']='module.db.aws_vpc.main[0]'
    assert not analyze(p)['edges']

def test_planned_values_unchanged_and_sensitive():
    p=plan();p['resource_changes']=[];p['planned_values']={'root_module':{'child_modules':[{'resources':[{'address':'module.a.aws_instance.web','type':'aws_instance','values':{'instance_type':'CANARY','user_data':'SECRET'},'sensitive_values':{'instance_type':True}}]}]}}
    g=analyze(p)
    assert len(g['nodes'])==1 and g['nodes'][0]['action']=='no-change'
    assert 'CANARY' not in json.dumps(g) and 'SECRET' not in json.dumps(g)

@pytest.mark.parametrize('data',[[],None,{'format_version':'1.0','terraform_version':'1.0.0'}, {'format_version':'1.0','terraform_version':'1.0.0','planned_values':{},'resource_changes':{} }])
def test_invalid_shape(data):
    with pytest.raises(PlanError): analyze(data)

def test_invalid_json_no_error_leak(tmp_path):
    path=tmp_path/'plan.json';path.write_text('{"password":"CANARY_SECRET",BROKEN}')
    result=subprocess.run([sys.executable,'-m','infra_xray','check',str(path)],capture_output=True,text=True,cwd=ROOT)
    assert result.returncode==2 and 'CANARY_SECRET' not in result.stderr+result.stdout

def test_100_resources():
    assert len(load_plan(EXAMPLES/'100-resources.json')['nodes'])==100

def test_unsupported_planned_resources_counted_once():
    p=plan();p['resource_changes']=[]
    p['planned_values']={'root_module':{'resources':[{'address':'aws_s3_bucket.logs','type':'aws_s3_bucket','values':{'secret':'CANARY'}}]}}
    graph=analyze(p)
    assert graph['ignoredResources']==1 and not graph['nodes']
    assert 'CANARY' not in json.dumps(graph)

@pytest.mark.parametrize('mask',[None,'malformed',123])
def test_malformed_sensitive_mask_fails_closed(mask):
    p=plan(after={'publicly_accessible':'CANARY'},after_sensitive=mask)
    assert 'CANARY' not in json.dumps(analyze(p))

def test_cli_error_is_specific_but_does_not_echo_input(tmp_path):
    p=plan();p['format_version']='SECRET_UNSUPPORTED'
    path=tmp_path/'invalid.json';path.write_text(json.dumps(p))
    result=subprocess.run([sys.executable,'-m','infra_xray','check',str(path)],capture_output=True,text=True,cwd=ROOT)
    assert result.returncode==2
    assert 'format_version' in result.stderr and 'SECRET_UNSUPPORTED' not in result.stderr

def test_mismatched_nested_mask_fails_closed():
    p=plan('aws_instance',after={'instance_type':'CANARY'},after_sensitive={'instance_type':{'nested':True}})
    assert 'CANARY' not in json.dumps(analyze(p))
