"""Offline blind review queue. No inference, provider calls or implicit label approval."""

import argparse
import html
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from finguard_ai.benchmark_data import LABELS, digest, load_splits, normalized
from finguard_ai.encoder_data import check_external, reference_hashes, validate_review
from finguard_ai.privacy import mask


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def load_queue(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    for name in ("candidates.jsonl", "sources.json"):
        if digest(directory / name) != manifest["files"][name]:
            raise ValueError("Queue checksum changed; create a new review version")
    sources_list = json.loads((directory / "sources.json").read_text())
    sources = {s["id"]: s for s in sources_list}
    if len(sources) != len(sources_list):
        raise ValueError("Duplicate source id")
    rows = [json.loads(s) for s in (directory / "candidates.jsonl").read_text().splitlines() if s.strip()]
    seen_ids, seen_text = set(), set()
    for row in rows:
        text = row["text"]
        source = sources[row["sourceId"]]
        if any(key in row for key in ("label", "suggestedLabel", "prediction")):
            raise ValueError("Review candidates must not contain proposed labels")
        if (source.get("status") != "ELIGIBLE" or source.get("license") != "KOGL-1"
                or not source.get("licenseEvidence") or row.get("sourceType") != "licensed"):
            raise ValueError("Source rights not eligible for this public queue")
        if (row.get("reviewStatus") != "PENDING" or not row.get("locator")
                or row.get("representation") not in {"PUBLISHED_EXAMPLE", "NOTICE_EXCERPT"}
                or row.get("group") != row["sourceId"]):
            raise ValueError("Missing provenance or source grouping")
        if not normalized(text) or len(text) > 10000:
            raise ValueError("Invalid candidate text")
        # A baseline blocker, not a proof of anonymization. Human review is still mandatory.
        if (mask(text) != text or re.search(r"https?://|www\.|\b[\w-]+\.(?:com|net|kr|org)\b|\d{6,}", text, re.I)):
            raise ValueError("Potential identifier/URL: sanitize and version before review")
        key = normalized(text)
        if row["id"] in seen_ids or key in seen_text:
            raise ValueError("Duplicate candidate id/text")
        seen_ids.add(row["id"])
        seen_text.add(key)
    if not rows:
        raise ValueError("Empty queue")
    return rows, sources, manifest, digest(directory / "manifest.json")


def overlap_report(rows, reference):
    """Flag approximate lexical similarity for human inspection, never semantic independence."""
    result = []
    for row in rows:
        matches = [(SequenceMatcher(None, normalized(row["text"]), normalized(r["text"]),
                                   autojunk=False).ratio(), r["id"]) for r in reference]
        score, candidate = max(matches, default=(0.0, None))
        result.append({"id": row["id"], "closestReferenceId": candidate,
                       "characterSimilarity": round(score, 4), "needsOverlapReview": score >= 0.8})
    return result


def prepare(directory, reference, output):
    rows, sources, manifest, sha = load_queue(directory)
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite review work")
    report = overlap_report(rows, reference)
    form = {"queueSha256": sha, "datasetAuthor": manifest["datasetAuthor"], "reviewer": "",
            "reviewedOn": "", "independentReviewAttested": False,
            "decisions": {r["id"]: {"decision": "PENDING", "label": "", "reason": "",
                                     "privacyReviewed": False, "rightsReviewed": False,
                                     "overlapReviewed": False} for r in rows}}
    output.mkdir(parents=True)
    (output / "review.json").write_text(encoded(form))
    (output / "provenance.json").write_text(encoded({"sources": sources, "candidates": rows,
                                                   "overlap": report}))
    (output / "review.html").write_text(render_form(rows, form))
    return {"candidates": len(rows), "overlapFlags": sum(r["needsOverlapReview"] for r in report),
            "state": "PENDING", "directory": str(output)}


def finalize(directory, review_path, reference, output):
    rows, sources, manifest, sha = load_queue(directory)
    record = json.loads(Path(review_path).read_text())
    if record.get("queueSha256") != sha or record.get("datasetAuthor") != manifest["datasetAuthor"]:
        raise ValueError("Review does not match frozen queue")
    if set(record.get("decisions", {})) != {r["id"] for r in rows}:
        raise ValueError("Review must account for every candidate")
    approved, approved_rows = {}, []
    for row in rows:
        decision = record["decisions"][row["id"]]
        if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
            raise ValueError("Every decision needs a reason")
        if decision.get("decision") == "EXCLUDE":
            continue
        if (decision.get("decision") != "APPROVE" or decision.get("label") not in LABELS
                or any(decision.get(k) is not True
                       for k in ("privacyReviewed", "rightsReviewed", "overlapReviewed"))):
            raise ValueError("Pending/uncertain or unchecked candidate: review is incomplete")
        source = sources[row["sourceId"]]
        approved_rows.append({**row, "label": decision["label"], "source": source["url"],
                              "reviewStatus": "REVIEWED"})
        approved[row["id"]] = {"label": decision["label"],
                               "usageBasis": f'{source["license"]}; {source["url"]}; {decision["reason"]}'}
    exported_review = {k: record.get(k) for k in
                       ("datasetAuthor", "reviewer", "reviewedOn", "independentReviewAttested")}
    exported_review["approvedRows"] = approved
    # Validate human declarations before class coverage, then enforce the existing strict evaluation gate.
    validate_review(approved_rows, exported_review)
    check_external(approved_rows, reference_hashes(reference))
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite reviewed data")
    output.mkdir(parents=True)
    (output / "evaluation.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                                  for r in approved_rows))
    (output / "review.json").write_text(encoded(exported_review))
    (output / "decisions.json").write_text(encoded(record))
    return {"approved": len(approved_rows), "excluded": len(rows) - len(approved_rows),
            "state": "READY_FOR_REGISTRATION", "independence": "human attestation; not verified by software"}


def render_form(rows, form):
    cards = []
    for row in rows:
        cards.append(f'''<fieldset data-id="{html.escape(row['id'], quote=True)}">
<legend>{html.escape(row['id'])}</legend><p class="text">{html.escape(row['text'])}</p>
<label>처리 <select name="decision"><option>PENDING</option><option>APPROVE</option>
<option>EXCLUDE</option><option>UNCERTAIN</option></select></label>
<label>라벨 <select name="label"><option value="">선택 전</option>
<option>NORMAL</option><option>PHISHING</option><option>PREVENTION</option></select></label>
<label>판단 이유 <textarea name="reason"></textarea></label>
<label><input type="checkbox" name="privacyReviewed">개인정보·식별정보 확인</label>
<label><input type="checkbox" name="rightsReviewed">출처·이용조건 확인</label>
<label><input type="checkbox" name="overlapReviewed">기존 평가 자료와 중복 확인</label></fieldset>''')
    payload = encoded(form).replace("<", "\\u003c")
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>FinGuard 독립 검수</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:16px system-ui;max-width:850px;margin:36px auto;padding:20px;color:#183747;
background:#f7fafb}fieldset{background:white;border:1px solid #ccd8df;border-radius:10px;
margin:20px 0;padding:20px}label{display:block;margin:12px 0}textarea{display:block;width:95%;
min-height:60px}select,input,button{font:inherit;padding:6px}.text{white-space:pre-wrap}
button{background:#183747;color:white;border:0;border-radius:6px;padding:12px}</style>
<h1>FinGuard 문자 검수</h1><p>모델 예측·추정 라벨을 제공하지 않습니다. 먼저 문장을 읽고 라벨·이유를
선택한 뒤 provenance.json에서 출처·중복 여부를 확인하세요. 출처의 분류명이 판단에 영향을
줄 수 있습니다. 문장만으로 불명확하면 UNCERTAIN 또는 EXCLUDE를 선택하세요.</p>
<p>NORMAL: 일반 대화·정상 안내 / PHISHING: 사기 행동 유도 / PREVENTION: 예방 안내·사기 인용.
출처가 위험 사례라고 하더라도 텍스트만으로 판단할 수 없는 경우 강제로 라벨을 붙이지 마세요.</p>
<p>체크박스는 직접 확인한 항목만 선택하세요. 저장은 JSON 다운로드로만 이루어집니다.
재접속 시 자동 복원되지 않으므로 중간 저장 파일은 review.json으로 보관하세요.
개인정보가 남아 있으면 제외하고 정제한 새 버전으로 재검수합니다.</p>
<label>검수자 <input id="reviewer" autocomplete="off"></label>
<label>검수일 <input id="reviewedOn" type="date"></label>
<label><input id="attest" type="checkbox">자료 정리자와 별도로 직접 검수했음을 확인합니다.</label>
''' + "".join(cards) + '''<button id="save">검수 JSON 다운로드 (미완료도 저장 가능)</button>
<p id="status" role="status"></p><script type="application/json" id="initial">''' + payload + '''</script>
<script>
const record=JSON.parse(document.getElementById('initial').textContent);
document.getElementById('save').addEventListener('click',()=>{
record.reviewer=document.getElementById('reviewer').value.trim();
record.reviewedOn=document.getElementById('reviewedOn').value;
record.independentReviewAttested=document.getElementById('attest').checked;
for(const el of document.querySelectorAll('fieldset')){
 const d=record.decisions[el.dataset.id];
 for(const key of ['decision','label','reason']) d[key]=el.querySelector('[name="'+key+'"]').value;
 for(const key of ['privacyReviewed','rightsReviewed','overlapReviewed'])
  d[key]=el.querySelector('[name="'+key+'"]').checked;
}
const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));
const a=document.createElement('a');a.href=url;a.download='review.json';a.click();
setTimeout(()=>URL.revokeObjectURL(url),1000);
document.getElementById('status').textContent='다운로드했습니다. 저장은 평가 등록·승인이 아닙니다.';
});
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "finalize"))
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    splits, _ = load_splits(args.reference)
    reference = [r for part in splits.values() for r in part]
    try:
        if args.action == "prepare":
            result = prepare(args.queue, reference, args.output)
        else:
            if not args.review:
                parser.error("finalize requires --review")
            result = finalize(args.queue, args.review, reference, args.output)
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Review blocked: {exc}\n")
    print(encoded(result))


if __name__ == "__main__":
    main()
