# RM-07 Server Comparison

Scripts and selected outputs for comparing `omlx` and `mlx-lm` on ReasonMath-15 RM-07.

Run:

```bash
python3 run_rm07_compare.py
python3 evaluate_rm07_outputs.py
```

The scripts assume:

- `omlx`: `http://127.0.0.1:8000/v1`, model `Qwen3.6-35B-A3B-OptiQ-4bit`
- `mlx-lm`: `http://127.0.0.1:8081/v1`, model `/Users/ichimdav/.omlx/models/Qwen3.6-35B-A3B-OptiQ-4bit`

Key finding: RM-07 failure is reproduced as truncation at tight `max_tokens`, not as a tool-call issue.
