import json
import pathlib
import re

OUT = pathlib.Path(__file__).parent
CANONICAL = "ANSWER: avg_speed=48 km/h"
CHECKPOINTS = ["distance_one_way=180", "return_time=4.5", "total_distance=360", "total_time=7.5", "avg_speed=48"]

def normalize_text(value):
    return re.sub(r"\s+", " ", value.strip()).lower()

def normalize_checkpoint_label(value):
    return normalize_text(value.replace("_", " "))

def extract_answer_line(answer):
    lines = answer.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    matches = [line for line in lines if line.startswith("ANSWER: ")]
    return matches[-1] if matches else ""

def answer_payload(line):
    return re.sub(r"^ANSWER:\s*", "", line, flags=re.I).strip()

def try_single_value_match(canonical, answer_line):
    cp = answer_payload(canonical)
    ap = answer_payload(answer_line)
    if ";" in cp or "=" not in cp:
        return False
    key, expected = cp.split("=", 1)
    expected_key = normalize_checkpoint_label(key)
    expected_value = normalize_text(expected)
    actual = normalize_text(ap)
    if actual == expected_value:
        return True
    without = re.sub(r"^[a-z_][a-z0-9_ ]*=\s*", "", actual, flags=re.I).strip()
    if without == expected_value:
        return True
    return expected_key in actual and expected_value in actual

def eval_one(path):
    d = json.loads(path.read_text())
    text = d["content"]
    answer_line = extract_answer_line(text)
    answer_points = 2 if answer_line and (normalize_text(answer_line) == normalize_text(CANONICAL) or try_single_value_match(CANONICAL, answer_line)) else 0
    matched = []
    norm = normalize_text(text)
    for cp in CHECKPOINTS:
        ncp = normalize_text(cp)
        ok = ncp in norm
        if not ok and "=" in cp:
            left, right = cp.split("=", 1)
            ok = normalize_checkpoint_label(left) in norm and normalize_text(right) in norm
        if ok:
            matched.append(cp)
    trace_points = 2 if len(matched) == len(CHECKPOINTS) else (1 if matched else 0)
    score = round(100 * (0.7 * (answer_points / 2) + 0.3 * (trace_points / 2)))
    return {"file": str(path), "finish_reasons": d.get("finish_reasons"), "chars": len(text), "answer_line": answer_line, "answer_points": answer_points, "matched_checkpoints": matched, "trace_points": trace_points, "score": score, "tail": text[-220:]}

results=[]
for path in sorted(OUT.glob("*-max*-stream.parsed.json")):
    results.append(eval_one(path))
(OUT / "rm07-evaluation-summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
for r in results:
    print(pathlib.Path(r['file']).name, 'finish=', r['finish_reasons'], 'score=', r['score'], 'answer=', repr(r['answer_line']))
