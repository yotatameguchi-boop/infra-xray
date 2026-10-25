import copy
import io
import json
import urllib.error
import zipfile
from unittest.mock import Mock
import pytest
from infra_xray.github import GitHub, GitHubError, publish_comment, find_baseline, artifact_name
from infra_xray.ci import validate_publication
from infra_xray.review import ReviewError
from test_review import review, db, SHA

class Fake:
    repo='owner/repo'
    def __init__(self):
        self.comments=[];self.writes=[];self.sha=SHA;self.fork=False;self.checks=0;self.change_on_second=False
    def request(self,path,**kwargs):return {'id':123,'type':'Bot'}
    def pages(self,path,*args,**kwargs):return iter(self.comments)
    def api(self,path,**kwargs):
        if path.startswith('/pulls/'):
            self.checks+=1
            return {'state':'open','head':{'sha':'b'*40 if self.change_on_second and self.checks==2 else self.sha,'repo':{'full_name':'other/repo' if self.fork else self.repo}}}
        self.writes.append((path,kwargs))
        if kwargs.get('method')=='POST':self.comments.append({'id':99,'user':{'id':123},'body':kwargs['data']['body']})
        return {}

def test_no_post_by_default():
    fake=Fake();assert publish_comment(fake,review())=='disabled';assert not fake.writes and not fake.checks

def test_create_then_update_same_target_and_never_human():
    fake=Fake();r=review();publish_comment(fake,r,enabled=True)
    human={'id':100,'user':{'id':999},'body':fake.comments[0]['body']};fake.comments.insert(0,human)
    assert publish_comment(fake,r,enabled=True)=='updated'
    assert fake.writes[-1][0]=='/issues/comments/99'
    body=fake.writes[0][1]['data']['body']
    assert SHA in body and 'aws_db_instance.primary' not in body and 'publicly_accessible' not in body
    second=review(target='second');assert publish_comment(fake,second,enabled=True)=='created'

@pytest.mark.parametrize('condition',['stale','fork','race','newer_run'])
def test_stale_and_fork_never_write(condition):
    fake=Fake();r=review()
    if condition=='stale':fake.sha='b'*40
    if condition=='fork':fake.fork=True
    if condition=='race':fake.change_on_second=True
    if condition=='newer_run':
        publish_comment(fake,r,enabled=True);fake.comments[0]['body']=fake.comments[0]['body'].replace('run:10','run:99');fake.writes=[]
    assert publish_comment(fake,r,enabled=True) in ('stale_or_fork','stale_run')
    assert not fake.writes

def test_non_bot_token_rejected():
    fake=Fake();fake.request=lambda *a,**k:{'id':123,'type':'User'}
    with pytest.raises(GitHubError):publish_comment(fake,review(),enabled=True)

def test_publication_context_and_counts_validated():
    r=review();assert validate_publication(r,'default',1,SHA,10)==r
    with pytest.raises(ReviewError):validate_publication(r,'default',2,SHA,10)
    r['summary']['findings']='<script>CANARY</script>'
    with pytest.raises(ReviewError):validate_publication(r,'default',1,SHA,10)

class Response(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):pass

def test_transport_retries_reads_not_post_and_redacts_errors():
    opener=Mock();opener.open.side_effect=[urllib.error.HTTPError('SECRET',503,'CANARY',{},None),Response(b'{"ok":true}')]
    sleeps=[];client=GitHub('owner/repo','SECRET_TOKEN',opener=opener,sleep=sleeps.append)
    assert client.api('/pulls/1')['ok'] and sleeps==[1]
    opener.open.side_effect=urllib.error.HTTPError('SECRET',503,'CANARY',{},None);opener.open.reset_mock()
    with pytest.raises(GitHubError) as error:client.api('/issues/1/comments',method='POST',data={})
    assert 'CANARY' not in str(error.value) and opener.open.call_count==1

def test_artifact_download_strips_token_and_avoids_extraction():
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:z.writestr('report.json',json.dumps(review()));z.writestr('../../escape','ignored')
    opener=Mock();opener.open.side_effect=[urllib.error.HTTPError('https://api.github.com',302,'Redirect',{'Location':'https://blob.example/report'},None),Response(data.getvalue())]
    client=GitHub('owner/repo','SECRET_TOKEN',opener=opener)
    assert client.artifact_json({'id':1})['schema_version']==1
    requests=[c.args[0] for c in opener.open.call_args_list]
    assert requests[0].get_header('Authorization')=='Bearer SECRET_TOKEN'
    assert not requests[1].has_header('Authorization')

def test_corrupt_artifact_digest_rejected():
    client=GitHub('owner/repo','token',opener=Mock())
    client.api=Mock(return_value='https://blob.example/file');client.opener.open.return_value=Response(b'wrong')
    with pytest.raises(GitHubError):client.artifact_json({'id':1,'digest':'sha256:bad'})

def test_baseline_uses_previous_analysis_success_even_policy_failed():
    client=Mock();client.api.return_value={'workflow_id':8,'pull_requests':[{'number':1}]}
    old=review(db(),{'fail_on_rules':['DB-001']});old['run_id']=8
    runs=[{'id':9,'status':'completed','head_sha':SHA,'pull_requests':[{'number':2}]}, {'id':8,'status':'completed','conclusion':'failure','head_sha':SHA,'pull_requests':[{'number':1}]}]
    client.pages.side_effect=[iter(runs),iter([{'id':1,'name':artifact_name('default'),'expired':False}])]
    client.artifact_json.return_value=old
    found,state=find_baseline(client,1,10,'default',old['rules_fingerprint'])
    assert found==old and state=='compared'
