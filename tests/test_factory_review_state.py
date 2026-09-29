"""A stale or superficially green review must not become an acceptance gate."""
import json

import pytest

from q_factory.git import FactoryError
from q_factory.review_state import LENSES, MARKER, criteria_digest, parse_stamp, render_stamp, review_mode, validate_stamp


def record():
    return {'version': 1, 'repository': 'example/project', 'pr': 4,
            'head': 'a' * 40, 'base': 'b' * 40, 'round': 1, 'mode': 'full',
            'criteria_digest': criteria_digest({'ticket': {'criterion': 'Preserve empty input'}}),
            'lead_model': 'claude-opus-5', 'lead_session': 'lead',
            'reviewers': [{'model': 'claude-sonnet-4-6', 'session': name, 'artifact_digest': 'c' * 64}
                          for name in ('left', 'right')],
            'lenses': [{'name': name, 'result': 'pass', 'evidence': 'Checked the frozen source and fixture.'}
                       for name in LENSES],
            'acceptance': [{'criterion': 'Preserve empty input', 'result': 'met', 'evidence': 'Empty-input regression passed.'}],
            'findings': [], 'blocking': 0, 'candidate_dispositions': [],
            'verdict': 'approved', 'checks_passed': True, 'checks_evidence': 'Fixture tests passed.'}


def parse(value, **overrides):
    expected = {key: value[key] for key in ('repository', 'pr', 'head', 'base')}
    expected.update(overrides)
    return parse_stamp(MARKER + json.dumps(value) + '\n-->', **expected)


def test_record_roundtrip_and_separate_specification_fingerprint():
    value = record()
    assert parse_stamp(render_stamp(value), **{k: value[k] for k in ('repository', 'pr', 'head', 'base')}) == value
    assert criteria_digest({'a': 1, 'b': 2}) == criteria_digest({'b': 2, 'a': 1})
    assert criteria_digest({'a': 1}) != criteria_digest({'a': 2})


@pytest.mark.parametrize('field,value', [('head', 'd' * 40), ('base', 'd' * 40), ('repository', 'elsewhere/project'), ('pr', 5)])
def test_review_cannot_transfer_to_another_commit_base_or_pr(field, value):
    with pytest.raises(FactoryError):
        parse(record(), **{field: value})


@pytest.mark.parametrize('mutate', [
    lambda x: x['reviewers'].pop(),
    lambda x: x['reviewers'][1].update(session='left'),
    lambda x: x['reviewers'][0].update(model='claude-opus-5'),
    lambda x: x.update(lead_model='claude-sonnet-4-6'),
    lambda x: x['lenses'].pop(),
    lambda x: x['lenses'][0].update(name=x['lenses'][1]['name']),
    lambda x: x['lenses'][6].update(result='unverified'),
    lambda x: x['acceptance'][0].update(result='unmet'),
    lambda x: x['acceptance'][0].update(result='unverified'),
    lambda x: x.update(checks_passed=False),
])
def test_green_words_do_not_replace_independence_lenses_or_acceptance(mutate):
    value = record()
    mutate(value)
    with pytest.raises(FactoryError):
        parse(value)


def test_fixed_but_unverified_and_deferred_blockers_do_not_disappear():
    value = record()
    f = {'id': 'R1-F1', 'severity': 'blocking', 'disposition': 'fixed',
         'verified': False, 'evidence': 'Author reports a fix, not independently checked.'}
    value['findings'] = [f]
    value['blocking'] = 0
    with pytest.raises(FactoryError, match='count'):
        parse(value)
    value['blocking'] = 1
    with pytest.raises(FactoryError, match='blocking'):
        parse(value)
    value['verdict'] = 'changes-requested'
    assert parse(value)['blocking'] == 1
    f.update(disposition='deferred', verified=True, owner='implementer', follow_up='Jyra follow-up')
    value.update(verdict='approved', blocking=0)
    with pytest.raises(FactoryError):
        parse(value)
    f.update(disposition='fixed', evidence='Regression now passes at the recorded head.')
    assert parse(value)['verdict'] == 'approved'


def test_duplicate_json_fields_and_multiple_stamps_are_refused():
    value = record()
    expected = {k: value[k] for k in ('repository', 'pr', 'head', 'base')}
    body = render_stamp(value)
    with pytest.raises(FactoryError):
        parse_stamp(body + body, **expected)
    with pytest.raises(FactoryError, match='Duplicate'):
        parse_stamp(body.replace('"version": 1', '"version": 1, "version": 1'), **expected)


@pytest.mark.parametrize('changed', ['base', 'specification', 'history'])
def test_incremental_reset_requires_reason_for_changed_review_boundary(changed):
    old = record()
    args = {'base': old['base'], 'digest': old['criteria_digest'], 'is_ancestor': True}
    assert review_mode(old, **args) == 'incremental'
    if changed == 'base': args['base'] = 'd' * 40
    if changed == 'specification': args['digest'] = criteria_digest({'new': 'scope'})
    if changed == 'history': args['is_ancestor'] = False
    with pytest.raises(FactoryError, match='reset'):
        review_mode(old, **args)
    assert review_mode(old, **args, reset_reason='Changed boundary inspected; full review required.') == 'full'


def test_nonblocking_deferral_requires_a_real_followup_and_owner():
    value = record()
    value['findings'] = [{'id': 'R1-F1', 'severity': 'non-blocking', 'disposition': 'deferred',
                          'verified': True, 'evidence': 'Lead accepted the bounded follow-up.'}]
    with pytest.raises(FactoryError): parse(value)
    value['findings'][0].update(follow_up='ticket reference', owner='implementer')
    assert parse(value)['verdict'] == 'approved'


@pytest.mark.parametrize('field', ['verdict', 'mode', 'findings', 'lenses'])
def test_direct_validator_sanitizes_malformed_field_types(field):
    value = record()
    value[field] = {'malformed': ['nested', 'untrusted']}
    with pytest.raises(FactoryError):
        validate_stamp(value, **{k: value[k] for k in ('repository', 'pr', 'head', 'base')})


@pytest.mark.parametrize('model', ['claude-opus-5', 'claude-opus-5-5'])
def test_accepted_lead_models_stamp(model):
    """Opus 5.5 accepted 2026-09-25; earlier Opus 5 stamps stay valid."""
    value = {**record(), 'lead_model': model}
    assert parse(value)['lead_model'] == model


@pytest.mark.parametrize('model', ['claude-sonnet-5', 'claude-opus-4', 'opus', '', None])
def test_any_other_lead_model_is_refused(model):
    with pytest.raises(FactoryError):
        parse({**record(), 'lead_model': model})


# --- Team-lead overrides (review-lead flow) -----------------------------------
# The team lead makes the final call on what a review lead verified, but it
# coordinates the implementers, so any finding it drops or downgrades must carry
# a written reason in the record. An unrecorded override would quietly undo the
# review's independence.

def _override_record(**override):
    value = record()
    value['findings'] = [{'id': 'R1-F1', 'severity': 'non-blocking', 'disposition': 'open',
                          'verified': True, 'evidence': 'Reproduced with the fixture.'}]
    value['candidate_dispositions'] = [
        {'source': 'left:F1', 'finding_id': 'R1-F1', 'reason': 'Verified against the code.',
         'lead_override': {'action': 'downgraded', 'reason': 'Only reachable behind a disabled flag.'}},
        {'source': 'right:F2', 'finding_id': None, 'reason': 'Verified, but dropped by the team lead.',
         'lead_override': {'action': 'dropped', 'reason': 'Duplicates an accepted, ticketed limitation.'}},
    ]
    value['candidate_dispositions'][0]['lead_override'].update(override)
    return value


def test_recorded_team_lead_overrides_are_accepted():
    value = _override_record()
    assert parse(value)['candidate_dispositions'][1]['lead_override']['action'] == 'dropped'


@pytest.mark.parametrize('mutate', [
    # An override without a reason is exactly the silent override this forbids.
    lambda x: x['candidate_dispositions'][0]['lead_override'].pop('reason'),
    lambda x: x['candidate_dispositions'][0]['lead_override'].update(reason='   '),
    # Only the two documented actions; "added" would be an unverified finding.
    lambda x: x['candidate_dispositions'][0]['lead_override'].update(action='added'),
    lambda x: x['candidate_dispositions'][0].update(lead_override='downgraded'),
    lambda x: x['candidate_dispositions'][0]['lead_override'].update(extra='field'),
    # A dropped candidate cannot also be a published finding.
    lambda x: x['candidate_dispositions'][1].update(finding_id='R1-F1'),
    # A downgrade must point at a published finding that is now non-blocking.
    lambda x: x['candidate_dispositions'][0].update(finding_id=None),
    lambda x: x['findings'][0].update(severity='blocking') or x.update(blocking=1, verdict='changes-requested'),
])
def test_team_lead_overrides_must_be_recorded_and_consistent(mutate):
    value = _override_record()
    mutate(value)
    with pytest.raises(FactoryError):
        parse(value)


def test_candidates_without_an_override_are_unchanged():
    value = record()
    value['candidate_dispositions'] = [{'source': 'left:F1', 'finding_id': None,
                                        'reason': 'Refuted: the guard exists at line 12.'}]
    assert parse(value) == value



# Invented, in the shape of q-core#19's frozen runner input (committed fixtures must be invented).
DIGEST_TICKET = {'id': 'fixture-ticket', 'title': 'Add numbers', 'description': '**M1** `pytest -q` passes.\n**M2** Sums two integers.'}
PLAIN_ROUND_ONE = {'ticket': DIGEST_TICKET, 'epic': None, 'prior_findings': [],
                   'acceptance_criteria': ['**M1** `pytest -q` passes.', '**M2** Sums two integers.']}
LABELLED_ROUND_ONE = {**PLAIN_ROUND_ONE, 'acceptance_criteria': [
    {'label': 'M1', 'criterion': '**M1** `pytest -q` passes.'}, {'label': 'M2', 'criterion': '**M2** Sums two integers.'}]}


def test_specification_digest_is_the_posted_stamp_form_and_stable_across_rounds():
    # Posted stamps (q-core#19 R1 and R2, ba2d968c...) hash the context with prior_findings emptied, key kept.
    # These digests are pinned so neither the key selection nor the serialization can drift under them.
    from q_factory.review_state import specification_digest
    round_two = {**PLAIN_ROUND_ONE, 'prior_findings': [{'id': 'R1-F1', 'disposition': 'fixed in abc'}]}
    assert specification_digest(PLAIN_ROUND_ONE) == criteria_digest(PLAIN_ROUND_ONE) \
        == 'fb7f8e8cbe9ae305fea7bcb20973595baf62855d1ac2d96d608d6a61d8d6db7b'
    assert specification_digest(round_two) == criteria_digest(dict(round_two, prior_findings=[])) \
        == specification_digest(PLAIN_ROUND_ONE)
    assert criteria_digest(round_two) != specification_digest(round_two)  # the ambiguity this helper removes
    changed = {**round_two, 'acceptance_criteria': ['**M1** `pytest -q` passes.', '**M2** Sums three integers.']}
    assert specification_digest(changed) != specification_digest(PLAIN_ROUND_ONE)
    with pytest.raises(FactoryError, match='criteria digest'):
        specification_digest({'ticket': DIGEST_TICKET})


def test_labelled_and_plain_criteria_digests_differ_on_purpose():
    # Criteria are hashed exactly as supplied; normalizing the forms would invalidate posted stamps.
    # Every round of a PR must therefore use the same form.
    from q_factory.review_state import specification_digest
    assert specification_digest(LABELLED_ROUND_ONE) == '2789288681398508b33521c50ffa88af572895e2a952994c868d0eecc3602ec9'
    assert specification_digest(LABELLED_ROUND_ONE) != specification_digest(PLAIN_ROUND_ONE)
