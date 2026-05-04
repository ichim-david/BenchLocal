# Tool Streaming Checks

This contains a sanity-check script for `mlx-lm` Qwen tool-call streaming.

Run:

```bash
python3 run_mlx_stream_tests.py
```

It sends sequential streamed tool-call requests to `mlx-lm` and validates generated files for:

- Python
- Rust
- TypeScript
- JSON

The purpose is to verify that streamed tool-call arguments reconstruct as valid JSON, paths do not contain trailing newlines, and code/content formatting is preserved.

Current result summary is in `streaming-summary.json`.
