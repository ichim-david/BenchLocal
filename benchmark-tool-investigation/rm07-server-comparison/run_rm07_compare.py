import json
import pathlib
import time
import urllib.request

OUT = pathlib.Path(__file__).parent
SYSTEM_PROMPT = """You are a helpful assistant that solves practical reasoning problems.

Rules:
- Show concise visible work using equations, short bullet points, or numbered steps.
- Do not write a long essay.
- End with exactly one line that starts with "ANSWER: ".
- If the question asks for more than one value, format the final line as semicolon-separated key=value pairs.
- Use exact arithmetic when possible.
- Round only the final result when the problem context requires it.
- If the constraints are inconsistent, say so explicitly in the final answer."""
USER = """Alice drives from City A to City B at 60 km/h. The trip takes 3 hours. She then drives back from City B to City A, but hits traffic and averages only 40 km/h on the return.

What is her average speed for the entire round trip?"""

SERVERS = [
    {
        "name": "omlx-8000",
        "url": "http://127.0.0.1:8000/v1/chat/completions",
        "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
        "api_key": "UayjFP%sz3KKuN",
    },
    {
        "name": "mlx-lm-8081",
        "url": "http://127.0.0.1:8081/v1/chat/completions",
        "model": "/Users/ichimdav/.omlx/models/Qwen3.6-35B-A3B-OptiQ-4bit",
        "api_key": None,
    },
]


def call(server, max_tokens=512, stream=True):
    payload = {
        "model": server["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    headers = {"Content-Type": "application/json"}
    if server.get("api_key"):
        headers["Authorization"] = "Bearer " + server["api_key"]
    req = urllib.request.Request(server["url"], data=json.dumps(payload).encode(), headers=headers, method="POST")
    stem = OUT / f"{server['name']}-max{max_tokens}-{'stream' if stream else 'nonstream'}"
    started = time.time()
    with urllib.request.urlopen(req, timeout=420) as resp:
        body = resp.read()
        (stem.with_suffix(".meta.json")).write_text(json.dumps({
            "server": server, "payload": payload, "status": resp.status,
            "headers": dict(resp.headers), "started": started, "elapsed": time.time()-started,
        }, indent=2), encoding="utf-8")
        (stem.with_suffix(".raw")).write_bytes(body)
    if stream:
        text_parts = []
        reasons = []
        events = 0
        errors = []
        for line in body.decode("utf-8", "replace").splitlines():
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                continue
            events += 1
            try:
                ev = json.loads(data)
            except Exception as e:
                errors.append({"error": str(e), "data": data[:200]})
                continue
            for ch in ev.get("choices", []):
                if ch.get("finish_reason"):
                    reasons.append(ch.get("finish_reason"))
                delta = ch.get("delta") or ch.get("message") or {}
                text_parts.append(delta.get("content", ""))
        result = {"events": events, "errors": errors, "finish_reasons": reasons, "content": "".join(text_parts)}
    else:
        ev = json.loads(body)
        choice = ev["choices"][0]
        result = {"finish_reasons": [choice.get("finish_reason")], "content": choice.get("message", {}).get("content", ""), "response": ev}
    (stem.with_suffix(".parsed.json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (stem.with_suffix(".md")).write_text(result["content"], encoding="utf-8")
    print(server["name"], "finish", result.get("finish_reasons"), "chars", len(result["content"]), "answer?", "ANSWER:" in result["content"])


if __name__ == "__main__":
    for server in SERVERS:
        call(server, max_tokens=512, stream=True)
