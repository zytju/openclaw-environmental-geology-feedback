"""Small fail-closed validator for the JSON Schema subset shipped by this project.

This is not a general JSON Schema implementation. Unknown assertion keywords fail.
No network, command execution, remote schema resolution, or file attachments.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path

DIMENSIONS = ["problem_identification", "evidence_extraction", "reasoning_chain",
              "hazard_chain", "uncertainty", "mitigation_match"]
LABELS = ["问题识别", "证据提取", "推理链完整性", "灾害链分析", "不确定性表达", "防治建议匹配"]
VERSION = "1.1.0"
CASE_ID = "shuping-teaching-v1"


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "JSON_DUPLICATE_KEY")
        out[key] = value
    return out


def loads(text):
    def bad_constant(_):
        raise ContractError("JSON_NONFINITE_NUMBER")
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=bad_constant)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("JSON_PARSE_ERROR") from exc


def read_json(path, max_bytes=2_000_000):
    p = Path(path)
    require(not p.is_symlink(), "SYMLINK_NOT_ALLOWED")
    require(p.is_file() and p.stat().st_size <= max_bytes, "INPUT_FILE_OR_SIZE")
    try:
        return loads(p.read_text(encoding="utf-8-sig"))
    except UnicodeError as exc:
        raise ContractError("INPUT_UTF8_REQUIRED") from exc


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ContractError("NON_JSON_VALUE") from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


ASSERTIONS = {"$schema", "$id", "$defs", "$ref", "title", "description", "default",
              "type", "properties", "required", "additionalProperties", "items",
              "minItems", "maxItems", "uniqueItems", "minLength", "maxLength",
              "pattern", "enum", "const", "minimum", "maximum", "anyOf"}


def validate(value, schema, root=None, path="$", depth=0):
    require(depth <= 64, "SCHEMA_DEPTH")
    root = schema if root is None else root
    require(isinstance(schema, dict), "SCHEMA_OBJECT_REQUIRED")
    require(not (set(schema) - ASSERTIONS), "SCHEMA_UNSUPPORTED_KEYWORD")
    if "$ref" in schema:
        ref = schema["$ref"]
        require(ref.startswith("#/$defs/"), "SCHEMA_EXTERNAL_REF_FORBIDDEN")
        target = root["$defs"][ref.split("/")[-1]]
        validate(value, target, root, path, depth + 1)
    if "anyOf" in schema:
        successes = 0
        for part in schema["anyOf"]:
            try:
                validate(value, part, root, path, depth + 1)
                successes += 1
            except ContractError:
                pass
        require(successes > 0, path + ":ANYOF")
    if "const" in schema:
        require(type(value) is type(schema["const"]) and value == schema["const"], path + ":CONST")
    if "enum" in schema:
        require(any(type(value) is type(x) and value == x for x in schema["enum"]), path + ":ENUM")
    types = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str), "boolean": lambda x: type(x) is bool,
             "integer": lambda x: type(x) is int,
             "number": lambda x: type(x) in (int, float) and math.isfinite(x),
             "null": lambda x: x is None}
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        require(all(t in types for t in ts), "SCHEMA_UNKNOWN_TYPE")
        require(any(types[t](value) for t in ts), path + ":TYPE")
    if isinstance(value, dict):
        require(all(k in value for k in schema.get("required", [])), path + ":REQUIRED")
        props = schema.get("properties", {})
        extra = set(value) - set(props)
        if schema.get("additionalProperties") is False:
            require(not extra, path + ":EXTRA_PROPERTY")
        for k, v in value.items():
            if k in props:
                validate(v, props[k], root, path + "." + k, depth + 1)
            elif isinstance(schema.get("additionalProperties"), dict):
                validate(v, schema["additionalProperties"], root, path + ".*", depth + 1)
    if isinstance(value, list):
        require(len(value) >= schema.get("minItems", 0), path + ":MIN_ITEMS")
        require(len(value) <= schema.get("maxItems", 100000), path + ":MAX_ITEMS")
        if schema.get("uniqueItems"):
            require(len({canonical(x) for x in value}) == len(value), path + ":DUPLICATE_ITEM")
        if "items" in schema:
            for i, item in enumerate(value):
                validate(item, schema["items"], root, f"{path}[{i}]", depth + 1)
    if isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0), path + ":MIN_LENGTH")
        require(len(value) <= schema.get("maxLength", 10**9), path + ":MAX_LENGTH")
        if schema.get("minLength", 0):
            require(bool(value.strip()), path + ":BLANK")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, path + ":PATTERN")
    if type(value) in (int, float):
        require(math.isfinite(value), path + ":NONFINITE")
        require(value >= schema.get("minimum", -math.inf), path + ":MINIMUM")
        require(value <= schema.get("maximum", math.inf), path + ":MAXIMUM")
    return value


def unique(items, key):
    ids = [i[key] for i in items]
    require(len(set(ids)) == len(ids), "DUPLICATE_" + key.upper())
    return set(ids)


# A triage screen, never a proof of de-identification or absence of injection.
PII = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|(?<!\d)\d{17}[\dXx](?!\d)|(?:姓名|学号|身份证|手机号)\s*[:：]\s*\S+")
INJECTION = re.compile(r"忽略(?:以上|之前|前面).{0,8}(?:指令|规则)|(?:输出|泄露|显示).{0,8}系统提示|泄露.{0,8}(密钥|配置)|ignore.{0,20}(?:previous|above|all).{0,8}instructions|(?:reveal|print|show).{0,12}system\s*prompt", re.I)


def check_submission(sub, schema, sources):
    validate(sub, schema)
    require(1 <= int(sub["student_id"][1:]) <= 66, "COHORT_ID_RANGE")
    pids = unique(sub["paragraphs"], "paragraph_id")
    unique(sub["raw_analysis"], "artifact_id")
    unique(sub["evidence_cards"], "card_id")
    require(sub['report_scope'] != 'full_report' or sub['assessed_dimensions'] == DIMENSIONS, 'FULL_REPORT_SIX_DIMENSIONS_REQUIRED')
    for c in sub["evidence_cards"]:
        require(set(c["paragraph_ids"]) <= pids, "EVIDENCE_PARAGRAPH_UNKNOWN")
    require(len(set(sub["previous_issue_ids"])) == len(sub["previous_issue_ids"]), "DUPLICATE_PRIOR_ISSUE")
    for rev in sub["revisions"]:
        require(rev["paragraph_id"] in pids, "REVISION_PARAGRAPH_UNKNOWN")
        require(rev["feedback_issue_id"] in sub["previous_issue_ids"], "REVISION_ISSUE_UNKNOWN")
    return sub


def material_gate(sub, intake=None, sources=None):
    """Teacher intake is separate from student JSON and bound to its exact hash."""
    missing, holds = [], []
    if sources is None:
        holds.append('source_registry_required')
    else:
        known = {s['source_id'] for s in sources}
        if any(c['source_id'] not in known for c in sub['evidence_cards']):
            holds.append('teacher_source_registration_required')
    if not sub["raw_analysis"]:
        missing.append("raw_analysis")
    if not sub["evidence_cards"]:
        missing.append("evidence_cards")
    if sub["stage"] == "revision":
        if not sub["revisions"] or not sub["previous_issue_ids"]:
            missing.append("revision_explanations_and_previous_feedback")
        elif set(r["feedback_issue_id"] for r in sub["revisions"]) != set(sub["previous_issue_ids"]):
            missing.append("explain_each_previous_issue")
        if intake is None or intake.get("previous_feedback_verified") is not True:
            holds.append("teacher_previous_feedback_verification_required")
    serialized = canonical(sub).decode()
    if PII.search(serialized):
        holds.append("possible_personal_information")
    if INJECTION.search(serialized):
        holds.append("possible_prompt_injection")
    if intake is None or intake.get("submission_sha256") != digest(sub):
        holds.append("teacher_intake_missing_or_stale")
    else:
        if intake.get("student_id") != sub["student_id"]:
            holds.append("teacher_intake_id_mismatch")
        if intake.get("material_kind") != sub["material_kind"]:
            holds.append("teacher_intake_kind_mismatch")
        if sub["material_kind"] == "student_work" and (intake.get("reviewer_code") == "T000" or
                 str(intake.get("reviewed_at", "")).startswith("SIMULATED")):
            holds.append("simulated_intake_cannot_approve_student_work")
        for key in ("materials_readable", "source_checks_done", "deidentified", "approved_for_feedback"):
            if intake.get(key) is not True:
                holds.append("teacher_" + key + "_required")
    status = "needs_material" if missing else "teacher_hold" if holds else "eligible"
    return {"schema_version": VERSION, "student_id": sub["student_id"],
            "submission_sha256": digest(sub), "status": status, "missing": missing,
            "holds": holds, "authorship_proven": False}


def prose_text(value):
    """Exclude machine identifiers/hashes from a heuristic privacy text screen."""
    if isinstance(value, dict):
        return "\n".join(prose_text(v) for k, v in value.items()
                         if not (k.endswith("sha256") or k.endswith("_id") or k.endswith("_ids")))
    if isinstance(value, list):
        return "\n".join(prose_text(x) for x in value)
    return value if isinstance(value, str) else ""


def check_anchor(anchor, sub):
    ps = {p["paragraph_id"]: p["text"] for p in sub["paragraphs"]}
    if anchor["paragraph_id"] == "REPORT":
        require(anchor["quote"] is None, "ABSENCE_ANCHOR_NO_FAKE_QUOTE")
    else:
        require(anchor["paragraph_id"] in ps, "OUTPUT_PARAGRAPH_UNKNOWN")
        require(isinstance(anchor["quote"], str) and bool(anchor["quote"].strip()), "OUTPUT_QUOTE_EMPTY")
        require(any(c.isalnum() for c in anchor['quote']), 'OUTPUT_QUOTE_NO_MEANINGFUL_TEXT')
        require(anchor["quote"] in ps[anchor["paragraph_id"]], "OUTPUT_QUOTE_NOT_IN_REPORT")


def check_citations(citations, facts):
    by_id = {f["claim_id"]: f for f in facts}
    for c in citations:
        require(c["claim_id"] in by_id, "OUTPUT_CLAIM_UNKNOWN")
        f = by_id[c["claim_id"]]
        require(c["source_id"] == f["source_id"] and c["locator"] == f["locator"], "OUTPUT_CITATION_MISMATCH")


def check_feedback(feedback, sub, gate, schema, facts):
    validate(feedback, schema)
    require(gate["status"] == "eligible", "GATE_CLOSED")
    require(gate["submission_sha256"] == digest(sub), "GATE_STALE")
    require(feedback["student_id"] == sub["student_id"], "OUTPUT_STUDENT_MISMATCH")
    require(feedback["submission_sha256"] == digest(sub), "OUTPUT_SUBMISSION_MISMATCH")
    require([d["dimension"] for d in feedback["dimensions"]] == DIMENSIONS, "OUTPUT_SIX_DIMENSIONS_ORDER")
    card_ids = {c["card_id"] for c in sub["evidence_cards"]}
    all_issues = []
    for d in feedback["dimensions"]:
        check_anchor(d["anchor"], sub)
        check_citations(d["citations"], facts)
        require(set(d["evidence_card_ids"]) <= card_ids, "OUTPUT_EVIDENCE_CARD_UNKNOWN")
        in_scope = d['dimension'] in sub['assessed_dimensions']
        require((d['assessment'] != 'not_in_scope') == in_scope, 'ASSESSMENT_SCOPE_MISMATCH')
        levels = {'supported': (2, 3, None), 'partial': (0, 1, None), 'absent': (0, None),
                  'needs_teacher': (None,), 'not_in_scope': (None,)}
        require(d['level_proposal'] in levels[d['assessment']], 'ASSESSMENT_LEVEL_MISMATCH')
        if d['assessment'] == 'not_in_scope':
            require(not d['issues'] and not d['citations'] and not d['evidence_card_ids'] and not d.get('related_issue_ids'), 'OUT_OF_SCOPE_NO_ISSUES_OR_CITATIONS')
        if d["assessment"] in ("absent", 'not_in_scope'):
            require(d["anchor"]["paragraph_id"] == "REPORT", "ABSENCE_USE_REPORT_ANCHOR")
        else:
            require(d["anchor"]["paragraph_id"] != "REPORT", "PRESENT_NEEDS_EXACT_ANCHOR")
        if d["assessment"] not in ("supported", 'not_in_scope'):
            require(bool(d["issues"]) or (d['assessment']=='partial' and bool(d.get('related_issue_ids'))), "ISSUE_REQUIRED_FOR_GAP")
        for issue in d["issues"]:
            check_anchor(issue["anchor"], sub)
            check_citations(issue["citations"], facts)
            require(set(issue["evidence_card_ids"]) <= card_ids, "ISSUE_EVIDENCE_CARD_UNKNOWN")
            all_issues.append(issue)
    unique(all_issues, "issue_id")
    all_ids={i['issue_id'] for i in all_issues}
    for d in feedback['dimensions']:
        related=set(d.get('related_issue_ids',[]))
        require(related<=all_ids,'RELATED_ISSUE_UNKNOWN')
        require(not related.intersection(i['issue_id'] for i in d['issues']),'RELATED_ISSUE_MUST_BE_OTHER_DIMENSION')
    require(not PII.search(prose_text(feedback)), "OUTPUT_POSSIBLE_PERSONAL_INFORMATION")
    return feedback


def check_teacher(review, sub, feedback, schema, facts):
    validate(review, schema)
    require(review["student_id"] == sub["student_id"], "TEACHER_STUDENT_MISMATCH")
    require(review["submission_sha256"] == digest(sub), "TEACHER_SUBMISSION_MISMATCH")
    require(review["feedback_sha256"] == digest(feedback), "TEACHER_FEEDBACK_MISMATCH")
    require([x["dimension"] for x in review["checks"]] == DIMENSIONS, "TEACHER_SIX_DIMENSIONS_ORDER")
    issue_ids = {i["issue_id"] for d in feedback["dimensions"] for i in d["issues"]}
    dimension_issues = {d['dimension']: {i['issue_id'] for i in d['issues']} | set(d.get('related_issue_ids',[])) for d in feedback['dimensions']}
    for check in review["checks"]:
        require(set(check["issue_ids"]) <= issue_ids, "TEACHER_ISSUE_UNKNOWN")
        require(set(check['issue_ids']) <= dimension_issues[check['dimension']], 'TEACHER_ISSUE_WRONG_DIMENSION')
        check_anchor(check["anchor"], sub)
        check_citations(check["citations"], facts)
    for omission in review["omissions"]:
        check_anchor(omission["anchor"], sub)
        check_citations(omission["citations"], facts)
    if review["disposition"] == "accept_proposal":
        require(all(c["verdict"] == "aligned" for c in review["checks"]) and not review["omissions"], "TEACHER_ACCEPT_CONTRADICTION")
    require(not PII.search(prose_text(review)), "TEACHER_POSSIBLE_PERSONAL_INFORMATION")
    return review
