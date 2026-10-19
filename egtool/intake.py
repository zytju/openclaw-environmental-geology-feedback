"""Teacher-side text conversion and unsigned intake skeletons. No model calls."""
import re
from pathlib import Path
from .contracts import DIMENSIONS, VERSION, CASE_ID, require, read_json, digest, check_submission
from .pipeline import ROOT, assets, save, stamp


def fields(text, allowed, required):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(':')
        require(bool(sep) and key.strip() in allowed, 'MARKDOWN_FIELD_UNKNOWN')
        key = key.strip()
        require(key not in result, 'MARKDOWN_DUPLICATE_FIELD')
        result[key] = value.strip()
    require(set(required) <= result.keys(), 'MARKDOWN_FIELD_MISSING')
    return result


def csv_ids(value):
    return [x.strip() for x in value.split(',') if x.strip()]


def parse_markdown(text):
    parts = re.split(r'^##\s+([^\n]+)\s*$', text, flags=re.M)
    hkeys = {'student_id', 'material_kind', 'stage', 'report_scope', 'assessed_dimensions', 'previous_issue_ids'}
    h = fields(parts[0], hkeys, hkeys)
    sub = {'schema_version': VERSION, 'case_id': CASE_ID, **h,
        'assessed_dimensions': csv_ids(h['assessed_dimensions']), 'previous_issue_ids': csv_ids(h['previous_issue_ids']),
        'paragraphs': [], 'raw_analysis': [], 'evidence_cards': [], 'revisions': []}
    for heading, body in zip(parts[1::2], parts[2::2]):
        heading, body = heading.strip(), body.strip()
        if re.fullmatch(r'P[0-9]{2,6}', heading):
            sub['paragraphs'].append({'paragraph_id': heading, 'text': body})
        elif re.fullmatch(r'A[0-9]+ (notes|sketch_transcript)', heading):
            aid, kind = heading.split()
            sub['raw_analysis'].append({'artifact_id': aid, 'kind': kind, 'content': body})
        elif re.fullmatch(r'E[0-9]+', heading):
            keys = {'source_id', 'locator', 'excerpt_type', 'excerpt', 'interpretation', 'paragraph_ids'}
            c = fields(body, keys, keys)
            c['paragraph_ids'] = csv_ids(c['paragraph_ids'])
            sub['evidence_cards'].append({'card_id': heading, **c})
        elif re.fullmatch(r'I[0-9]{2,6}', heading):
            keys = {'paragraph_id', 'decision', 'reason'}
            sub['revisions'].append({'feedback_issue_id': heading, **fields(body, keys, keys)})
        else:
            raise ValueError('MARKDOWN_SECTION_UNKNOWN')
    schemas, sources, _ = assets()
    check_submission(sub, schemas['submission'], sources)
    return sub


def intake_skeleton(sub):
    return {'schema_version': VERSION, 'student_id': sub['student_id'], 'submission_sha256': digest(sub),
        'material_kind': sub['material_kind'], 'materials_readable': False, 'source_checks_done': False,
        'deidentified': False, 'approved_for_feedback': False, 'previous_feedback_verified': False,
        'reviewer_code': 'T000', 'reviewed_at': 'NOT_REVIEWED'}


def private_output(out, sub):
    if sub['material_kind'] == 'student_work':
        require(not Path(out).resolve().is_relative_to(ROOT), 'REAL_OUTPUT_INSIDE_PUBLIC_REPO')


def prepare(markdown, out):
    p = Path(markdown)
    require(not p.is_symlink(), 'SYMLINK_NOT_ALLOWED')
    paths = sorted(p.glob('*.md')) if p.is_dir() else [p]
    require(1 <= len(paths) <= 66, 'BATCH_CAPACITY_1_TO_66')
    submissions, seen = [], set()
    for source in paths:
        require(not source.is_symlink() and source.is_file() and source.stat().st_size <= 2000000, 'INPUT_FILE_OR_SIZE')
        sub = parse_markdown(source.read_text(encoding='utf-8-sig'))
        require(sub['student_id'] not in seen, 'BATCH_DUPLICATE_ID')
        seen.add(sub['student_id'])
        private_output(out, sub)
        submissions.append(sub)
    out = Path(out)
    require(not out.exists(), 'OUTPUT_EXISTS')
    out.mkdir(parents=True, mode=0o700)
    (out / 'submissions').mkdir(mode=0o700)
    ts = stamp()
    for sub in submissions:
        save(out / 'submissions' / (sub['student_id'] + '_' + ts + '.json'), sub)
    save(out / ('intake_' + ts + '.json'), [intake_skeleton(sub) for sub in submissions])
    return out


def intake_template(inputs, out):
    schemas, sources, _ = assets()
    p = Path(inputs)
    require(not p.is_symlink(), 'INPUT_DIRECTORY_SYMLINK')
    files = sorted(p.glob('*.json'))
    require(1 <= len(files) <= 66, 'BATCH_CAPACITY_1_TO_66')
    records, seen = [], set()
    for f in files:
        sub = read_json(f)
        check_submission(sub, schemas['submission'], sources)
        require(sub['student_id'] not in seen, 'BATCH_DUPLICATE_ID')
        seen.add(sub['student_id'])
        private_output(out, sub)
        records.append(intake_skeleton(sub))
    save(out, records)
    return Path(out)


def upgrade_submission(path, out, scope, dimensions):
    sub = read_json(path)
    require(sub.get('schema_version') == '1.0.0', 'UPGRADE_REQUIRES_1_0_0_SUBMISSION')
    sub.update(schema_version=VERSION, report_scope=scope, assessed_dimensions=dimensions)
    schemas, sources, _ = assets()
    check_submission(sub, schemas['submission'], sources)
    private_output(out, sub)
    save(out, sub)
    return Path(out)
