"""Validate commit-stamped factory reviews; no network or mutation authority."""
from __future__ import annotations

import hashlib
import json
import re

from .git import FactoryError

LENSES = ('correctness', 'contract-coherence', 'convention-drift', 'test-integrity',
          'silent-failure', 'scope-simplification', 'acceptance-specification')
VERDICTS = {'approved', 'changes-requested', 'incomplete', 'needs-input'}
MARKER = '<!-- factory-review:v1\n'
SHA = re.compile(r'[0-9a-f]{40}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')


#: Accepted review-lead models. Opus 5.5 was accepted by the owner on 2026-09-25
#: (`opus` resolves to it); records stamped by Opus 5 before then stay valid.
LEAD_MODELS = frozenset({'claude-opus-5', 'claude-opus-5-5'})

def _require(condition, message='Invalid factory review record.'):
    if not condition:
        raise FactoryError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'Duplicate keys in factory review record.')
        result[key] = value
    return result


def criteria_digest(context: dict) -> str:
    """Hash the explicit ticket/epic specification snapshot, excluding no fields.

    Callers pass only specification fields, not changing queue status/timestamps.
    The digest identifies evidence; it does not grant authority to publish it.
    """
    return hashlib.sha256(json.dumps(context, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


#: The review runner context's specification. prior_findings changes every round, so it is
#: emptied (not removed): that's the form posted stamps already hash, and they must stay valid.
SPECIFICATION_KEYS = ('ticket', 'epic', 'acceptance_criteria')


def specification_digest(context: dict) -> str:
    """criteria_digest of a review runner context: its ticket, epic and acceptance_criteria, with
    prior_findings emptied. Criteria are hashed exactly as supplied, so plain-text and labelled forms
    of the same criteria differ; every round of a PR must use the same form."""
    _require(isinstance(context, dict) and all(key in context for key in SPECIFICATION_KEYS),
             'Context needs ticket, epic and acceptance_criteria for its criteria digest.')
    return criteria_digest({**{key: context[key] for key in SPECIFICATION_KEYS}, 'prior_findings': []})


def validate_stamp(record, *, repository, pr, head, base):
    """Validate untrusted JSON without leaking arbitrary type diagnostics."""
    try:
        return _validate_stamp(record, repository=repository, pr=pr, head=head, base=base)
    except FactoryError:
        raise
    except (ValueError, TypeError, KeyError):
        raise FactoryError('Malformed factory review record.') from None


def _validate_stamp(record, *, repository, pr, head, base):
    _require(isinstance(record, dict))
    _require(record.get('version') == 1 and type(record.get('version')) is int)
    _require(record.get('repository') == repository and record.get('pr') == pr
             and type(record.get('pr')) is int, 'Review belongs to another PR.')
    _require(isinstance(head, str) and SHA.fullmatch(head) and isinstance(base, str)
             and SHA.fullmatch(base), 'Review requires full head and base commit IDs.')
    _require(record.get('head') == head and record.get('base') == base,
             'Review is stale for the current head or base.')
    _require(type(record.get('round')) is int and record['round'] > 0)
    _require(record.get('verdict') in VERDICTS)
    _require(isinstance(record.get('criteria_digest'), str)
             and DIGEST.fullmatch(record['criteria_digest']))
    _require(record.get('mode') in {'full', 'incremental'})
    _require(record.get('lead_model') in LEAD_MODELS
             and _text(record.get('lead_session')), 'Review requires the requested Opus lead identity.')
    if record['mode'] == 'incremental':
        _require(type(record.get('previous_review_id')) is int and record['previous_review_id'] > 0)
        _require(isinstance(record.get('previous_head'), str)
                 and SHA.fullmatch(record['previous_head']))
    reviewers = record.get('reviewers')
    _require(isinstance(reviewers, list) and len(reviewers) == 2,
             'Review requires both independent reviewer results.')
    sessions = set()
    for reviewer in reviewers:
        _require(isinstance(reviewer, dict) and _text(reviewer.get('session')))
        _require(reviewer['session'] not in sessions, 'Reviewer sessions must be independent.')
        sessions.add(reviewer['session'])
        _require(isinstance(reviewer.get('model'), str)
                 and re.fullmatch(r'claude-sonnet-[a-z0-9-]+', reviewer['model']))
        _require(isinstance(reviewer.get('artifact_digest'), str)
                 and DIGEST.fullmatch(reviewer['artifact_digest']))
    _require(record['lead_session'] not in sessions)
    lenses = record.get('lenses')
    _require(isinstance(lenses, list) and len(lenses) == len(LENSES))
    _require(all(isinstance(lens, dict) for lens in lenses))
    _require({lens.get('name') for lens in lenses} == set(LENSES), 'All seven lenses are required.')
    for lens in lenses:
        _require(lens.get('result') in {'pass', 'findings', 'unverified'} and _text(lens.get('evidence')))
    acceptance = record.get('acceptance')
    _require(isinstance(acceptance, list) and acceptance, 'Acceptance evidence is required.')
    for item in acceptance:
        _require(isinstance(item, dict) and _text(item.get('criterion'))
                 and item.get('result') in {'met', 'unmet', 'unverified', 'not-in-scope'}
                 and _text(item.get('evidence')))
    findings = record.get('findings')
    _require(isinstance(findings, list))
    ids = set()
    unresolved = 0
    for finding in findings:
        _require(isinstance(finding, dict))
        fid = finding.get('id')
        _require(isinstance(fid, str) and re.fullmatch(r'R[1-9][0-9]*-F[1-9][0-9]*', fid)
                 and fid not in ids, 'Findings need unique stable IDs.')
        ids.add(fid)
        _require(finding.get('severity') in {'blocking', 'non-blocking'})
        _require(finding.get('disposition') in {'open', 'fixed', 'refuted', 'deferred'})
        _require(type(finding.get('verified')) is bool and _text(finding.get('evidence')))
        if finding['disposition'] == 'deferred':
            _require(_text(finding.get('follow_up')) and _text(finding.get('owner')))
        resolved = finding['disposition'] in {'fixed', 'refuted'} and finding['verified']
        unresolved += finding['severity'] == 'blocking' and not resolved
    _require(type(record.get('blocking')) is int and record['blocking'] == unresolved,
             'Blocking count disagrees with finding dispositions.')
    _require(isinstance(record.get('candidate_dispositions'), list),
             'Lead validation and deduplication evidence is required.')
    severity = {finding['id']: finding['severity'] for finding in findings}
    for candidate in record['candidate_dispositions']:
        _require(isinstance(candidate, dict) and _text(candidate.get('source'))
                 and _text(candidate.get('reason')))
        _require(candidate.get('finding_id') in ids or candidate.get('finding_id') is None)
        if 'lead_override' in candidate:
            _validate_lead_override(candidate, severity)
    if record['verdict'] == 'approved':
        _require(unresolved == 0, 'Unresolved blocking findings prevent approval.')
        _require(all(lens['result'] != 'unverified' for lens in lenses), 'Incomplete lenses prevent approval.')
        _require(all(item['result'] in {'met', 'not-in-scope'} for item in acceptance)
                 and any(item['result'] == 'met' for item in acceptance),
                 'Unmet or unverified acceptance prevents approval.')
        _require(record.get('checks_passed') is True and _text(record.get('checks_evidence')),
                 'Approval requires explicit successful check evidence.')
    elif record['verdict'] == 'changes-requested':
        _require(unresolved > 0, 'Changes requested must identify blocking findings.')
    return record


LEAD_OVERRIDE_ACTIONS = {'dropped', 'downgraded'}


def _validate_lead_override(candidate, severity):
    """A team lead may drop or downgrade a verified candidate, never silently.

    The team lead coordinates the implementers whose work is under review, so
    an override without a recorded reason would quietly undo the review's
    independence. It may not add findings: an unverified finding goes back to
    the review lead rather than into the record.
    """
    override = candidate['lead_override']
    _require(isinstance(override, dict) and set(override) == {'action', 'reason'}
             and override.get('action') in LEAD_OVERRIDE_ACTIONS and _text(override.get('reason')),
             'A team-lead override needs an action (dropped or downgraded) and a written reason.')
    finding_id = candidate.get('finding_id')
    if override['action'] == 'dropped':
        _require(finding_id is None, 'A dropped candidate cannot also be a published finding.')
    else:
        _require(finding_id is not None and severity.get(finding_id) == 'non-blocking',
                 'A downgraded candidate must map to a published non-blocking finding.')


def parse_stamp(body, *, repository, pr, head, base):
    """Parse one record. Caller verifies GitHub review author and commit_id.

    Text that merely resembles a stamp in a PR body/comment is not a review.
    This parser cannot establish author identity or actual model execution.
    """
    _require(isinstance(body, str) and body.count(MARKER) == 1,
             'Expected one factory review stamp.')
    payload = body.split(MARKER, 1)[1]
    _require('\n-->' in payload, 'Unterminated factory review stamp.')
    payload = payload.split('\n-->', 1)[0]
    try:
        record = json.loads(payload, object_pairs_hook=_unique_object)
        return validate_stamp(record, repository=repository, pr=pr, head=head, base=base)
    except FactoryError:
        raise
    except (ValueError, TypeError, KeyError):
        raise FactoryError('Malformed factory review record.') from None


def render_stamp(record):
    validate_stamp(record, **{key: record.get(key) for key in ('repository', 'pr', 'head', 'base')})
    return MARKER + json.dumps(record, sort_keys=True, indent=2) + '\n-->'


def review_mode(previous, *, base, digest, is_ancestor, reset_reason=None):
    """Do not silently reuse approvals after rebases or specification changes."""
    if previous is None:
        return 'full'
    changed = previous['base'] != base or previous['criteria_digest'] != digest or not is_ancestor
    if changed:
        _require(_text(reset_reason), 'Changed base, history or specification requires an explicit full-review reset reason.')
        return 'full'
    return 'incremental'
