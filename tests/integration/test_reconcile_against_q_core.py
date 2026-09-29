"""Factory reconciliation consumes actual public API responses, not shape doubles."""
import httpx
import pytest

from q_factory import reconcile as sync
from q_factory.client import Client
from q_factory.git import FactoryError
from q_factory.settings import SelfIdentity


@pytest.fixture
def reconciliation_api(client, test_settings, monkeypatch, tmp_path):
    headers = {'Authorization': f'Bearer {test_settings.api_token}'}
    entity_response = client.post('/entities', headers=headers, json={
        'type':'project', 'name':'Synthetic factory project',
        'attributes':{'repository_path':'projects/synthetic'},
    })
    assert entity_response.status_code == 200
    entity = entity_response.json()
    board_response = client.post('/boards', headers=headers,
                                 json={'entity_id':entity['id'],'title':'Synthetic board'})
    assert board_response.status_code == 200
    board = board_response.json()
    ticket_response = client.post('/tickets', headers=headers, json={
        'board_id':board['id'],'type':'task','title':'Synthetic task','actor':'worker',
    })
    assert ticket_response.status_code == 200
    ticket = ticket_response.json()
    seen = []
    def dispatch(request):
        # Forward factory HTTP calls through the production routes, serializers,
        # privacy validation and transaction logic against the fixture database.
        seen.append((request.method, request.url.path))
        response = client.request(request.method, request.url.path,
                                  params=list(request.url.params.multi_items()),
                                  content=request.content, headers=dict(request.headers))
        return httpx.Response(response.status_code, json=response.json())
    api = Client('http://127.0.0.1:8420', test_settings.api_token,
                 transport=httpx.MockTransport(dispatch))
    # Generated fixture identities stand in for the documented production IDs;
    # all entity/board/ticket shapes still come from the actual HTTP endpoints.
    monkeypatch.setattr(sync, 'git', lambda *args: 'git@github.com:Ascinocco/q-factory-clean.git')
    monkeypatch.setattr(sync, 'project', lambda root, path: {'path':root / path})
    identity = SelfIdentity(entity['id'], board['id'], 'ascinocco/q-factory-clean')
    yield api, entity, board, ticket, seen, tmp_path, identity
    api.close()


class LinkedPull:
    def __init__(self, ticket_id):
        self.ticket_id = ticket_id
    def get(self, endpoint, *, pages=False):
        if '/commits?' in endpoint:
            return [{'sha':'a'*40,'commit':{'message':'Synthetic change\n\nJyra-Ticket: '+self.ticket_id}}]
        if '/reviews?' in endpoint:
            return []
        return {'number':12,'body':'Jyra-Ticket: '+self.ticket_id,
                'head':{'sha':'a'*40},'base':{'sha':'b'*40,'repo':{'full_name':'Ascinocco/q-factory-clean'}},
                'state':'open','merged':False,'draft':False,'commits':1,'updated_at':'synthetic'}


@pytest.mark.parametrize('own',[True,False])
def test_public_scope_preview_apply_and_replay(reconciliation_api, own):
    api, entity, board, ticket, seen, root, identity = reconciliation_api
    detail = api.get('/boards/' + board['id'])
    assert detail['entity']['id'] == entity['id']
    assert 'entity_id' not in detail
    listing = api.all('/boards', entity_id=entity['id'])
    assert listing[0]['entity_id'] == entity['id']
    repo = sync.scope(root, api, None if own else entity['id'], board['id'], own, identity)
    assert repo == 'Ascinocco/q-factory-clean'
    kwargs = dict(repo=repo, board_id=board['id'], ticket_id=ticket['id'],
                  urls=['https://github.com/Ascinocco/q-factory-clean/pull/12'], actor='worker', authors=set())
    seen.clear()
    plan = sync.preview(api, LinkedPull(ticket['id']), **kwargs)
    assert all(method == 'GET' for method, _ in seen)
    assert plan['from_status'] == plan['to_status'] == 'backlog'
    result = sync.apply(api, plan, plan['expected_transition_id'], plan['receipt'])
    assert result['applied'] is True
    assert result['status'] == 'backlog'
    reread = sync.preview(api, LinkedPull(ticket['id']), **kwargs)
    assert reread['already_applied'] is True
    assert sync.apply(api, reread, plan['expected_transition_id'], plan['receipt'])['already_applied']
    history = api.all(f"/tickets/{ticket['id']}/transitions")
    assert len(history) == 2
    assert history[-1]['note'].startswith('Factory-GitHub-Receipt: ' + plan['receipt'])
    assert sum(method == 'POST' for method, _ in seen) == 1


def test_public_detail_association_mismatch_still_refused(reconciliation_api, client, test_settings, monkeypatch):
    api, entity, board, ticket, seen, root, identity = reconciliation_api
    other = client.post('/entities', headers={'Authorization':f'Bearer {test_settings.api_token}'},
                        json={'type':'project','name':'Other synthetic project'}).json()
    wrong = SelfIdentity(other['id'], board['id'], 'ascinocco/q-factory-clean')
    with pytest.raises(FactoryError, match='association'):
        sync.scope(root,api,None,board['id'],True,wrong)
