"""Synthetic GitHub snapshots and public local API requests, never live services."""
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from q_factory import reconcile as sync
from q_factory.client import Client
from q_factory.settings import SelfIdentity
from q_factory.git import FactoryError

TICKET = 'bbbbbbbb-bbbb-4bbb-8bbb-ab1234567890'
BOARD = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
OTHER = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
URL = 'https://github.com/example/app/pull/12'
HEAD, BASE = 'a'*40, 'b'*40


class Github:
    def __init__(self, *, state='open', merged=False, draft=False, reviews=None):
        self.pull = {'number':12,'body':'Jyra-Ticket: '+TICKET,'head':{'sha':HEAD},
                     'base':{'sha':BASE,'repo':{'full_name':'example/app'}},'state':state,
                     'merged':merged,'draft':draft,'commits':1,'updated_at':'synthetic'}
        self.commits = [{'sha':HEAD,'commit':{'message':'Implement feature\n\nJyra-Ticket: '+TICKET}}]
        self.reviews = reviews or []
        self.calls = []
    def get(self, endpoint, *, pages=False):
        self.calls.append((endpoint,pages))
        if '/commits?' in endpoint:
            assert pages
            return deepcopy(self.commits)
        if '/reviews?' in endpoint:
            assert pages
            return deepcopy(self.reviews)
        return deepcopy(self.pull)


class Local:
    def __init__(self, status='agent_coding', owner='worker'):
        self.row = {'id':TICKET,'board_id':BOARD,'type':'task','status':status,'claimed_by':'worker'}
        self.history = [{'id':str(uuid4()),'actor':owner,'to_status':status,'note':'Started'}]
        self.posts=[]
        self.race=False
        self.lose_response=False
        self.client=Client('http://localhost:8420','private-secret',transport=httpx.MockTransport(self.request))
    def request(self, request):
        path=request.url.path
        if request.method=='POST':
            self.posts.append(request)
            body=json.loads(request.content)
            if self.race or body['expected_transition_id']!=self.history[-1]['id']:
                return httpx.Response(409,json={'private':'private-secret'})
            self.row['status']=body['to_status']
            self.history.append({'id':str(uuid4()),**body})
            if self.lose_response:
                self.lose_response=False
                raise httpx.ReadTimeout('private-secret',request=request)
            return httpx.Response(200,json=self.row)
        if path.endswith('/transitions'):
            offset=int(request.url.params['offset'])
            # Force pagination even on tiny histories.
            return httpx.Response(200,json={'items':self.history[offset:offset+1],'total':len(self.history)})
        return httpx.Response(200,json=self.row)


def preview(local, github=None, **kwargs):
    defaults=dict(repo='example/app',board_id=BOARD,ticket_id=TICKET,urls=[URL],
                  actor='worker',authors={'lead'},advance_owned=False)
    defaults.update(kwargs)
    return sync.preview(local.client,github or Github(),**defaults)


def apply(local, plan):
    return sync.apply(local.client,plan,plan['expected_transition_id'],plan['receipt'])


def review(identity=1, author='lead', verdict='approved', state='COMMENTED', head=HEAD):
    return {'id':identity,'user':{'login':author},'state':state,'commit_id':head,
            'submitted_at':f'synthetic-{identity}',
            'body':'<!-- factory-review:v1\n'+json.dumps({'version':1,'repository':'example/app',
                'pr':12,'head':head,'base':BASE,'round':identity,'verdict':verdict})+'\n-->'}


@pytest.fixture
def minimal_stamp(monkeypatch):
    # The independent protocol module owns full review completeness validation.
    # This fixture isolates reconciliation's author/head/scope/event policy.
    def parse(body, **scope):
        parsed=json.loads(body.split('\n')[1])
        if any(parsed[key]!=value for key,value in scope.items()):
            raise FactoryError('Stamp scope mismatch')
        return parsed
    monkeypatch.setattr(sync,'stamp',parse)


def test_preview_is_read_only_and_apply_replay_is_idempotent():
    local=Local()
    plan=preview(local)
    assert local.posts==[] and plan['to_status']=='agent_coding'
    assert apply(local,plan)['applied']
    assert len(local.history)==2
    repeated=preview(local)
    assert repeated['already_applied']
    assert repeated['owner']=='worker'  # receipt did not acquire ownership
    assert sync.apply(local.client,repeated,plan['expected_transition_id'],plan['receipt'])['already_applied']
    assert len(local.posts)==1


def test_lost_response_retry_detects_committed_receipt():
    local=Local()
    plan=preview(local)
    local.lose_response=True
    with pytest.raises(FactoryError,match='unknown') as error:
        apply(local,plan)
    assert 'private-secret' not in str(error.value)
    repeated=preview(local)
    assert sync.apply(local.client,repeated,plan['expected_transition_id'],plan['receipt'])['already_applied']
    assert len(local.posts)==1


def test_cas_race_and_preview_change_refuse_without_clobber():
    local=Local()
    plan=preview(local)
    local.race=True
    with pytest.raises(FactoryError,match='HTTP 409') as error:
        apply(local,plan)
    assert 'private-secret' not in str(error.value)
    assert local.row['status']=='agent_coding'
    github=Github(draft=True)
    changed=preview(local,github)
    with pytest.raises(FactoryError,match='evidence'):
        sync.apply(local.client,changed,plan['expected_transition_id'],plan['receipt'])


@pytest.mark.parametrize('text',[
    'Example\n\n```\nJyra-Ticket: '+TICKET+'\n```',
    'Example\n\n```\n\nJyra-Ticket: '+TICKET,
    'Example\n\n<!--\nJyra-Ticket: '+TICKET+'\n-->',
    'Example\n\n> Jyra-Ticket: '+TICKET,
    'Jyra-Ticket: '+TICKET+'\n\nNot the trailer block',
])
def test_commit_trailer_spoofs_not_linked(text):
    assert sync.links(text,trailer=True)==set()


def test_malformed_or_wrong_scope_linkage_refused():
    local=Local()
    with pytest.raises(FactoryError,match='registered'):
        preview(local,urls=['https://github.com/other/app/pull/12'])
    for body in ['Jyra-Ticket: invalid', 'Jyra-Ticket: '+OTHER, '```\nJyra-Ticket: '+TICKET+'\n```']:
        github=Github();github.pull['body']=body
        with pytest.raises(FactoryError):preview(local,github)
    github=Github();github.commits[0]['commit']['message']='Title\n\nJyra-Ticket: '+OTHER
    with pytest.raises(FactoryError,match='trailers'):preview(local,github)
    with pytest.raises(FactoryError,match='canonical'):preview(local,ticket_id='../ticket')
    local.row['board_id']=OTHER
    with pytest.raises(FactoryError,match='belong'):preview(local)


def test_stale_or_truncated_commit_listing_refused():
    local=Local();github=Github();github.pull['commits']=251
    with pytest.raises(FactoryError,match='pagination'):preview(local,github)
    github=Github();github.commits[0]['sha']='c'*40
    with pytest.raises(FactoryError,match='stale'):preview(local,github)


def test_merged_never_done_and_closed_unmerged_keeps_status(minimal_stamp):
    local=Local();github=Github(state='closed',merged=True,reviews=[review()])
    plan=preview(local,github,advance_owned=True)
    assert plan['to_status']=='review'
    assert apply(local,plan)['status']=='review'
    assert preview(local,Github(state='closed'),advance_owned=True)['to_status']=='review'


@pytest.mark.parametrize('status,owner',[('blocked','worker'),('done','worker'),('backlog','worker'),('review','human')])
def test_manual_and_protected_states_preserved(minimal_stamp,status,owner):
    local=Local(status,owner)
    plan=preview(local,Github(reviews=[review(verdict='changes-requested')]),advance_owned=True)
    assert plan['to_status']==status


def test_changes_requested_returns_owned_work_to_in_progress(minimal_stamp):
    plan=preview(Local('review'),Github(reviews=[review(verdict='changes-requested')]),advance_owned=True)
    assert plan['to_status']=='in_progress'


def test_stale_spoofed_or_later_native_blocker_cannot_approve(minimal_stamp):
    for reviews in ([review(author='outsider')],[review(head='c'*40)],
                    [review(),review(2,author='outsider',state='CHANGES_REQUESTED')]):
        plan=preview(Local(),Github(reviews=reviews),advance_owned=True)
        assert plan['to_status']=='agent_coding'
    plan=preview(Local(),Github(reviews=[review(),review(2,state='CHANGES_REQUESTED')]),advance_owned=True)
    assert plan['to_status']=='agent_coding'


def test_every_previously_linked_pr_is_required():
    local=Local();plan=preview(local);apply(local,plan)
    with pytest.raises(FactoryError,match='every previously'):
        preview(local,urls=['https://github.com/example/app/pull/13'])


def test_multiple_prs_mixed_closed_state_cannot_advance(minimal_stamp):
    class Multiple(Github):
        def get(self, endpoint, *, pages=False):
            value=super().get(endpoint,pages=pages)
            if not pages and '/13' in endpoint:
                value['number']=13;value['state']='closed';value['merged']=False
            return value
    github=Multiple(reviews=[])
    plan=preview(Local(),github,urls=[URL,'https://github.com/example/app/pull/13'],advance_owned=True)
    assert len(plan['prs'])==2 and plan['to_status']=='agent_coding'


def test_github_pagination_and_sanitized_auth_failure(monkeypatch):
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout=json.dumps([{'id':1}])+'\n'+json.dumps([{'id':2}]))
    monkeypatch.setattr(sync.subprocess,'run',run)
    assert sync.GitHub().get('repos/example/app/pulls/12/reviews?per_page=100',pages=True)==[{'id':1},{'id':2}]
    assert '--paginate' in calls[0] and '--slurp' not in calls[0]
    monkeypatch.setattr(sync.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1,stdout='private-secret',stderr='private-secret'))
    with pytest.raises(FactoryError) as error:sync.GitHub().get('repos/example/app/pulls/12')
    assert 'private-secret' not in str(error.value)


def test_manual_roundtrip_after_preview_changes_token_and_preserves_owner():
    local=Local();plan=preview(local)
    local.history.extend([
        {'id':str(uuid4()),'actor':'human','to_status':'review','note':'Human review'},
        {'id':str(uuid4()),'actor':'human','to_status':'agent_coding','note':'Human decision'},
    ])
    changed=preview(local)
    assert changed['owner']=='human'
    with pytest.raises(FactoryError,match='history changed'):
        sync.apply(local.client,changed,plan['expected_transition_id'],plan['receipt'])
    assert local.posts==[]


def test_cli_apply_requires_explicit_preview_tokens(capsys):
    assert sync.main(['--self','--board',BOARD,'--ticket',TICKET,'--pr',URL,'--apply'])==1
    assert 'requires both preview' in json.loads(capsys.readouterr().err)['error']


@pytest.mark.parametrize('origin',['https://secret@github.com/example/app','https://elsewhere/example/app',
    'git@github.com:../app','https://github.com/example/app/extra'])
def test_repository_origins_reject_credentials_and_escapes(origin):
    with pytest.raises(FactoryError):sync.repository(origin)


SELF = SelfIdentity('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002', 'ascinocco/q-factory-clean')


def test_explicit_self_scope_cannot_target_another_repository(monkeypatch,tmp_path):
    class Local:
        def get(self,path):
            return ({'id':SELF.project_id,'type':'project'} if path.startswith('/entities/')
                    else {'id':SELF.board_id,'entity':{'id':SELF.project_id,'type':'project'}})
    monkeypatch.setattr(sync,'git',lambda *args:'git@github.com:other/project.git')
    with pytest.raises(FactoryError,match='repository origin documented in q-factory.toml'):
        sync.scope(tmp_path,Local(),None,SELF.board_id,True,SELF)


def test_self_scope_requires_the_documented_board(tmp_path):
    with pytest.raises(FactoryError,match='board documented in q-factory.toml'):
        sync.scope(tmp_path,object(),None,OTHER,True,SELF)


def test_pr_change_during_pagination_refuses_preview():
    class Changing(Github):
        def get(self,endpoint,*,pages=False):
            value=super().get(endpoint,pages=pages)
            if not pages and len(self.calls)>1:
                value['updated_at']='changed'
            return value
    with pytest.raises(FactoryError,match='changed during'):preview(Local(),Changing())


def complete_protocol_review():
    from q_factory.review_state import LENSES, criteria_digest, render_stamp
    record = {'version':1,'repository':'example/app','pr':12,'head':HEAD,'base':BASE,
              'round':1,'mode':'full','criteria_digest':criteria_digest({'criterion':'Synthetic acceptance'}),
              'lead_model':'claude-opus-5','lead_session':'lead',
              'reviewers':[{'model':'claude-sonnet-4-6','session':name,'artifact_digest':'c'*64}
                           for name in ('left','right')],
              'lenses':[{'name':name,'result':'pass','evidence':'Synthetic check passed.'} for name in LENSES],
              'acceptance':[{'criterion':'Synthetic acceptance','result':'met','evidence':'Synthetic test passed.'}],
              'findings':[],'blocking':0,'candidate_dispositions':[],'verdict':'approved',
              'checks_passed':True,'checks_evidence':'Synthetic checks passed.'}
    value=review()
    value['body']=render_stamp(record)
    return value


def test_real_protocol_parser_enforces_complete_exact_scope_before_advancing():
    local=Local()
    github=Github(reviews=[complete_protocol_review()])
    assert preview(local,github,advance_owned=True)['to_status']=='review'
    github.pull['base']['sha']='c'*40
    assert preview(local,github,advance_owned=True)['to_status']=='agent_coding'
    github=Github(reviews=[review()])  # incomplete JSON cannot masquerade as review
    assert preview(local,github,advance_owned=True)['to_status']=='agent_coding'


def test_dismissed_protocol_review_does_not_approve():
    dismissed=complete_protocol_review();dismissed['state']='DISMISSED'
    assert preview(Local(),Github(reviews=[dismissed]),advance_owned=True)['to_status']=='agent_coding'


def test_unclaimed_or_differently_claimed_work_cannot_advance(minimal_stamp):
    for claimant in (None,'other-worker'):
        local=Local();local.row['claimed_by']=claimant
        plan=preview(local,Github(reviews=[review()]),advance_owned=True)
        assert plan['to_status']=='agent_coding'


def test_native_review_without_protocol_stamp_is_evidence_only():
    native=review(state='CHANGES_REQUESTED');native['body']='Please adjust this.'
    assert preview(Local(),Github(reviews=[native]),advance_owned=True)['to_status']=='agent_coding'


def test_mismatched_markdown_fence_does_not_expose_linkage():
    for opening, closing in [('```','~~~'),('````','```')]:
        text=f'Example\n{opening}\n{closing}\n\nJyra-Ticket: {TICKET}'
        assert sync.links(text)==set()
        assert sync.links(text,trailer=True)==set()


def test_case_insensitive_pr_alias_replays_same_receipt():
    local=Local()
    plan=preview(local,urls=['https://github.com/EXAMPLE/APP/pull/12',URL])
    assert len(plan['prs'])==1
    apply(local,plan)
    repeated=preview(local,urls=['https://github.com/EXAMPLE/APP/pull/12'])
    assert repeated['receipt']==plan['receipt'] and repeated['already_applied']


def test_self_board_response_identity_is_checked(monkeypatch,tmp_path):
    class Local:
        def get(self,path):
            return ({'id':SELF.project_id,'type':'project'} if path.startswith('/entities/')
                    else {'id':OTHER,'entity':{'id':SELF.project_id,'type':'project'}})
    monkeypatch.setattr(sync,'git',lambda *args:'git@github.com:Ascinocco/q-factory-clean.git')
    with pytest.raises(FactoryError,match='association'):
        sync.scope(tmp_path,Local(),None,SELF.board_id,True,SELF)


@pytest.mark.parametrize('output',[
    '', '   ', '{"id":1}', '[{"id":1}]\n{"id":2}',
    '[{"id":1}] trailing private-secret', '[{"id":1}]\n[',
    '[[{"id":1}]]', '[{"id":1}], [{"id":2}]',
])
def test_paginated_json_stream_refuses_incomplete_or_nonarray_data(monkeypatch, output):
    monkeypatch.setattr(sync.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=output))
    with pytest.raises(FactoryError) as error:
        sync.GitHub().get('repos/example/app/pulls/12/reviews?per_page=100',pages=True)
    assert 'private-secret' not in str(error.value)


@pytest.mark.parametrize('output', ['[]', ' \n[]\n[]\t', '[{"id":1}][{"id":2}]'])
def test_paginated_json_stream_accepts_complete_arrays(monkeypatch, output):
    monkeypatch.setattr(sync.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=output))
    result=sync.GitHub().get('repos/example/app/pulls/12/reviews?per_page=100',pages=True)
    assert result==([{'id':1},{'id':2}] if 'id' in output else [])


def test_self_scope_without_an_identity_reads_q_factory_toml(tmp_path):
    """The fallback path: identity=None loads [self] from the root's toml."""
    (tmp_path/'q-factory.toml').write_text('[q_core]\napi_url = "http://127.0.0.1:8420"\n[self]\n'
                                          f'project_id = "{SELF.project_id}"\nboard_id = "{SELF.board_id}"\n'
                                          'repository = "ascinocco/q-factory-clean"\n')
    with pytest.raises(FactoryError,match='board documented in q-factory.toml'):
        sync.scope(tmp_path,object(),None,OTHER,True)
    (tmp_path/'q-factory.toml').unlink()
    with pytest.raises(FactoryError,match='q-factory.toml is missing'):
        sync.scope(tmp_path,object(),None,SELF.board_id,True)


def test_reconcile_api_url_overrides_the_configured_origin(monkeypatch,tmp_path):
    import subprocess
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    (tmp_path/'CLAUDE.md').write_text('Factory'); (tmp_path/'projects').mkdir(); (tmp_path/'projects/README.md').write_text('x')
    (tmp_path/'q-factory.toml').write_text('[q_core]\napi_url = "http://127.0.0.1:8420"\n[self]\n'
                                          f'project_id = "{SELF.project_id}"\nboard_id = "{SELF.board_id}"\n'
                                          'repository = "ascinocco/q-factory-clean"\n')
    monkeypatch.setenv('Q_CORE_API_TOKEN','private-test-token')
    seen={}
    def capture(url,token,tailnet=None):
        seen.update(url=url)
        raise FactoryError('stop after construction')
    monkeypatch.setattr(sync,'Client',capture)
    args=['--root',str(tmp_path),'--self','--board',SELF.board_id,'--ticket',TICKET,'--pr',URL]
    assert sync.main(args+['--api-url','http://127.0.0.1:9999'])==1
    assert seen=={'url':'http://127.0.0.1:9999'}
    assert sync.main(args)==1
    assert seen=={'url':'http://127.0.0.1:8420'}
