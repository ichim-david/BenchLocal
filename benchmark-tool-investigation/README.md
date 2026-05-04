# Benchmark Tool Investigation Notes

This folder collects the scripts and artifacts used to investigate why ReasonMath-15 scenario **RM-07** passed when served by `omlx` but failed when served by `mlx-lm` for the same local OptiQ model.

## Goal

Investigate whether the observed benchmark failure was caused by:

1. The recent `mlx-lm` Qwen tool-call streaming parser changes.
2. A difference in plain chat streaming behavior between the two servers.
3. A benchmark/tooling issue such as insufficient `max_tokens` handling or treating truncated output as an answer failure.

The specific observed files were:

- `correct-math7.md` — `omlx` result, benchmark passed.
- `wrong-math7.md` — `mlx-lm` result, benchmark failed because the final `ANSWER: ` line was missing.

## Servers Compared

### `omlx`

```text
Base URL: http://127.0.0.1:8000/v1
Model: Qwen3.6-35B-A3B-OptiQ-4bit
```

Requires the local API key from Pi's config when called directly.

### `mlx-lm`

```text
Base URL: http://127.0.0.1:8081/v1
Model: /Users/ichimdav/.omlx/models/Qwen3.6-35B-A3B-OptiQ-4bit
```

## Files

### Root files

- `correct-math7.md` — original passing benchmark log for `omlx`.
- `wrong-math7.md` — original failing benchmark log for `mlx-lm`.

### `rm07-server-comparison/`

- `benchmark.ts` — raw ReasonMath benchmark source fetched from GitHub.
- `run_rm07_compare.py` — script that sends the RM-07 prompt to both local servers sequentially.
- `evaluate_rm07_outputs.py` — local reimplementation of the relevant RM-07 scoring logic from `benchmark.ts`.
- `rm07-evaluation-summary.json` — generated scoring summary across tested token limits.
- `*-max570-stream.md`, `*-max572-stream.md`, `*-max580-stream.md` — selected streamed assistant outputs showing the truncation boundary.

### `tool-streaming-checks/`

- `run_mlx_stream_tests.py` — script testing `mlx-lm` tool-call streaming for Python, Rust, TypeScript, and JSON file-writing tasks.
- `streaming-summary.json` — validation summary.
- `stream-test-python.py`, `stream-test-rust.rs`, `stream-test-typescript.ts`, `stream-test-json.json` — extracted tool-call file contents from those tests.

## Main Finding

The RM-07 failure does **not** appear to be a tool-calling bug.

RM-07 is plain chat. It does not provide tools and does not involve `tool_calls` or streamed tool-call argument reconstruction. Therefore, the Qwen XML tool-call parser changes are not on the execution path for this benchmark scenario.

The observed failure is consistent with **output truncation due to a tight `max_tokens` / completion-token budget**.

In `wrong-math7.md`, the `mlx-lm` answer is cut off in the middle of the harmonic-mean formula:

```text
$$ v_{avg} = \frac{2 v_1 v_2
```

Because generation was truncated before the final answer line, the benchmark reports:

```text
Missing final "ANSWER: " line.
```

## Reproduction Summary

Using the benchmark system prompt and RM-07 user prompt, I ran both servers sequentially at multiple `max_tokens` values.

Relevant results:

```text
max_tokens=570
omlx-8000       finish=['length'] score=15 answer='ANSWER: 48'
mlx-lm-8081     finish=['length'] score=15 answer=''

max_tokens=572
omlx-8000       finish=['length'] score=85 answer='ANSWER: 48 km/h'
mlx-lm-8081     finish=['length'] score=15 answer=''

max_tokens=580
omlx-8000       finish=['stop'] score=85 answer='ANSWER: 48 km/h'
mlx-lm-8081     finish=['stop'] score=85 answer='ANSWER: 48 km/h'
```

The important case is `max_tokens=572`: `omlx` gets the complete `ANSWER: 48 km/h` line in just before/at truncation, while `mlx-lm` does not. At `max_tokens=580`, both servers stop naturally and pass.

This indicates the benchmark result is sensitive to very small differences in output verbosity/formatting near the token limit.

## Why the Outputs Differ Slightly

The two servers produce nearly the same reasoning, but not byte-identical text.

`omlx` tends to emit a more compact harmonic-mean formula:

```text
\frac{2v_1v_2}{v_1+v_2} = \frac{2(60)(40)}{60+40}
```

`mlx-lm` emitted a slightly longer formula:

```text
\frac{2 v_1 v_2}{v_1 + v_2} = \frac{2 \times 60 \times 40}{60 + 40}
```

That small difference is enough to determine whether the final `ANSWER:` line appears before a tight completion limit.

## Tool Streaming Sanity Checks

I also tested the current `mlx-lm` tool-call streaming behavior after the parser fix.

Tasks tested:

1. Write a Python file.
2. Write a Rust file.
3. Write a TypeScript file.
4. Write a JSON file.

All passed these checks:

- SSE stream parsed successfully.
- Exactly one `write` tool call was reconstructed.
- Tool arguments were valid JSON.
- `path` had no trailing newline or carriage return.
- `content` preserved newlines/code formatting.
- Python content parsed with `ast.parse`.
- JSON content parsed with `json.loads`.

This suggests the current tool-call streaming fix is fine and unrelated to RM-07.

## Suspected Benchmark Tool Issue

The benchmark appears to treat a response with `finish_reason: "length"` as a normal model answer and scores it directly. This can unfairly convert an infrastructure/truncation condition into a reasoning failure.

For RM-07, the `mlx-lm` output was mathematically on track and had already matched some trace checkpoints, but the final answer line was missing only because the completion was cut off.

## Suggested Benchmark Fixes

### 1. Increase max output tokens

Use a larger completion budget for ReasonMath scenarios, for example:

```text
max_tokens >= 1024
```

RM-07 passed for both servers at `max_tokens=580`, but a safer benchmark-wide value should be higher.

### 2. Treat `finish_reason === "length"` specially

If the API response has:

```json
"finish_reason": "length"
```

then the benchmark should probably not score the text as a completed answer. Options:

- Retry with a larger `max_tokens`.
- Mark the scenario as `truncated` / infrastructure failure.
- Score separately from reasoning correctness.

### 3. Optionally enforce concise answers in the prompt

The system prompt already says not to write a long essay, but RM-07 responses include an alternative harmonic-mean derivation. The benchmark could add something like:

```text
Do not include alternative solution methods.
Use at most 4 short calculation lines before the final ANSWER line.
```

However, prompt tightening is less robust than handling truncation correctly.

## How to Run

From the repository root:

```bash
python3 benchmark-tool-investigation/rm07-server-comparison/run_rm07_compare.py
python3 benchmark-tool-investigation/rm07-server-comparison/evaluate_rm07_outputs.py
```

For tool streaming checks:

```bash
python3 benchmark-tool-investigation/tool-streaming-checks/run_mlx_stream_tests.py
```

Note: the scripts assume both local servers are running at the URLs listed above.
