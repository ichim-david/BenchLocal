import ast
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8081/v1/chat/completions"
MODEL = "/Users/ichimdav/.omlx/models/Qwen3.6-35B-A3B-OptiQ-4bit"
OUTDIR = pathlib.Path("server-streaming-tests")
OUTDIR.mkdir(exist_ok=True)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Write content to a file. Use this when the user asks you to create or save a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to write"},
                    "content": {"type": "string", "description": "Complete file content"},
                },
                "required": ["path", "content"],
            },
        },
    }
]

TESTS = [
    {
        "name": "python",
        "filename": "stream-test-python.py",
        "prompt": "Write a Python file named stream-test-python.py. It should define fibonacci(n), include a small __main__ block that prints fibonacci(10), and include a triple-quoted docstring. Use the write tool exactly once.",
    },
    {
        "name": "rust",
        "filename": "stream-test-rust.rs",
        "prompt": "Write a Rust file named stream-test-rust.rs. It should define fn factorial(n: u64) -> u64, include fn main() that prints factorial(10), and include a comment with an example. Use the write tool exactly once.",
    },
    {
        "name": "typescript",
        "filename": "stream-test-typescript.ts",
        "prompt": "Write a TypeScript file named stream-test-typescript.ts. It should export an interface User, export a function formatUser(user: User): string, and include a small example object. Use the write tool exactly once.",
    },
    {
        "name": "json",
        "filename": "stream-test-json.json",
        "prompt": "Write a JSON file named stream-test-json.json. It should contain an object with fields project, version, features (array), thresholds (object with warn and error numbers), and enabled boolean. Use the write tool exactly once and make the content valid JSON with no markdown fences.",
    },
]


def request_stream(test):
    payload = {
        "model": MODEL,
        "stream": True,
        "temperature": 0.0,
        "max_tokens": 1400,
        "messages": [{"role": "user", "content": test["prompt"]}],
        "tools": TOOLS,
        "tool_choice": "auto",
    }
    req = urllib.request.Request(
        BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    sse_path = OUTDIR / f"{test['name']}.sse"
    meta_path = OUTDIR / f"{test['name']}.meta.json"
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=420) as resp, sse_path.open("wb") as f:
            meta = {"url": BASE_URL, "status": resp.status, "headers": dict(resp.headers), "started": started, "test": test}
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                f.flush()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        meta_path.write_text(json.dumps({"error": str(e), "body": body, "test": test}, indent=2), encoding="utf-8")
        raise
    return sse_path


def parse_sse(path):
    content_parts = []
    reasoning_parts = []
    tool_calls = {}
    finish_reasons = []
    events = 0
    json_errors = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            continue
        events += 1
        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            json_errors.append({"line": data[:200], "error": str(exc)})
            continue
        for choice in event.get("choices", []):
            if choice.get("finish_reason"):
                finish_reasons.append(choice.get("finish_reason"))
            delta = choice.get("delta") or choice.get("message") or {}
            if delta.get("content"):
                content_parts.append(delta["content"])
            if delta.get("reasoning"):
                reasoning_parts.append(delta["reasoning"])
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                rec = tool_calls.setdefault(idx, {"id": None, "type": None, "function": {"name": "", "arguments": ""}})
                if tc.get("id"):
                    rec["id"] = tc["id"]
                if tc.get("type"):
                    rec["type"] = tc["type"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    rec["function"]["name"] += fn["name"]
                if "arguments" in fn:
                    rec["function"]["arguments"] += fn.get("arguments") or ""
    return {
        "events": events,
        "json_errors": json_errors,
        "finish_reasons": finish_reasons,
        "assistant_content": "".join(content_parts),
        "reasoning": "".join(reasoning_parts),
        "tool_calls": [tool_calls[k] for k in sorted(tool_calls)],
    }


def command_exists(cmd):
    return subprocess.run(["/bin/sh", "-lc", f"command -v {cmd}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def validate(test, parsed):
    checks = []
    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("sse_events_present", parsed["events"] > 0, str(parsed["events"]))
    add("no_sse_json_errors", not parsed["json_errors"], json.dumps(parsed["json_errors"][:2]))
    add("finish_reason_tool_calls", "tool_calls" in parsed["finish_reasons"], repr(parsed["finish_reasons"]))
    add("one_tool_call", len(parsed["tool_calls"]) == 1, str(len(parsed["tool_calls"])))

    args = None
    if parsed["tool_calls"]:
        tc = parsed["tool_calls"][0]
        add("tool_name_write", tc["function"].get("name") == "write", repr(tc["function"].get("name")))
        raw_args = tc["function"].get("arguments", "")
        try:
            args = json.loads(raw_args)
            add("tool_arguments_valid_json", True)
        except Exception as exc:
            add("tool_arguments_valid_json", False, str(exc) + " raw prefix=" + repr(raw_args[:200]))
    else:
        add("tool_name_write", False, "no tool call")
        add("tool_arguments_valid_json", False, "no tool call")

    if args is not None:
        path = args.get("path")
        content = args.get("content")
        add("path_is_string", isinstance(path, str), repr(path))
        add("content_is_string", isinstance(content, str), type(content).__name__)
        add("path_has_no_trailing_newline", isinstance(path, str) and not path.endswith(("\n", "\r")), repr(path))
        add("path_mentions_expected_filename", isinstance(path, str) and test["filename"] in path, repr(path))
        add("content_not_empty", isinstance(content, str) and len(content) > 20, str(len(content) if isinstance(content, str) else None))
        add("content_preserves_newlines", isinstance(content, str) and "\n" in content, repr(content[:120]) if isinstance(content, str) else "")
        file_path = OUTDIR / test["filename"]
        if isinstance(content, str):
            file_path.write_text(content, encoding="utf-8")

            if test["name"] == "python":
                try:
                    ast.parse(content)
                    add("python_ast_parse", True)
                except SyntaxError as exc:
                    add("python_ast_parse", False, str(exc))
            elif test["name"] == "json":
                try:
                    json.loads(content)
                    add("json_content_parse", True)
                except json.JSONDecodeError as exc:
                    add("json_content_parse", False, str(exc))
            elif test["name"] == "rust":
                add("rust_contains_main", "fn main" in content, "")
                add("rust_contains_factorial", "factorial" in content, "")
                if command_exists("rustc"):
                    proc = subprocess.run(["rustc", "--emit=metadata", str(file_path)], capture_output=True, text=True, timeout=30)
                    add("rustc_metadata_check", proc.returncode == 0, (proc.stderr or proc.stdout)[-500:])
                else:
                    add("rustc_metadata_check", True, "skipped: rustc not installed")
            elif test["name"] == "typescript":
                add("typescript_has_exports", "export" in content and "formatUser" in content, "")
                if command_exists("tsc"):
                    proc = subprocess.run(["tsc", "--noEmit", "--strict", str(file_path)], capture_output=True, text=True, timeout=60)
                    add("tsc_noemit_check", proc.returncode == 0, (proc.stderr or proc.stdout)[-700:])
                else:
                    add("tsc_noemit_check", True, "skipped: tsc not installed")
    return checks


def main():
    summary = []
    for test in TESTS:
        print(f"\n=== running {test['name']} ===", flush=True)
        sse = request_stream(test)
        parsed = parse_sse(sse)
        parsed_path = OUTDIR / f"{test['name']}.parsed.json"
        parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        checks = validate(test, parsed)
        check_path = OUTDIR / f"{test['name']}.checks.json"
        check_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")
        ok = all(c["ok"] for c in checks)
        print(f"{test['name']}: {'PASS' if ok else 'FAIL'}")
        for c in checks:
            print(f"  [{'✓' if c['ok'] else '✗'}] {c['name']} {c['detail']}")
        summary.append({"name": test["name"], "ok": ok, "checks": checks})
    summary_path = OUTDIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nsummary written to {summary_path}")
    if not all(item["ok"] for item in summary):
        sys.exit(1)

if __name__ == "__main__":
    main()
