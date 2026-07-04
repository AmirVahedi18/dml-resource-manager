- **Numeric per-user GPU concurrency override.** v1's privilege is a boolean
  (`can_use_multiple_gpus`). A numeric cap (e.g. "this user may hold reservations on up to 3 GPUs
  at once") would be more precise than unlimited/1.
- **Plotly-based usage charts.** v1 renders admin usage reports with Matplotlib (no extra system
  dependencies). Plotly would give nicer styling at the cost of a heavier dependency (kaleido
  bundles a Chromium-like binary for PNG export).
- **Dockerfile / docker-compose.** A containerized, repeatable deployment path for the lab
  server. Out of scope for v1 since it wasn't requested and doesn't affect the bot's architecture.
