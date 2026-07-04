- **Configurable cancellation cutoff window.** v1 lets students cancel anytime before a
  reservation's start, with no penalty. A regulation field for a minimum-notice cutoff (e.g. "no
  cancellations within 2h of start") would discourage last-minute flaking that blocks others from
  booking that slot.
- **Self-service registration via one-time invite codes.** v1 requires the admin to manually
  collect each student's Telegram ID (via `/myid`) before registering them. An invite-code flow
  (`/start <code>`) would let students self-link without the admin needing to look up IDs first —
  better if the lab grows.
- **Multiple admins via a DB-stored role.** v1 has a single bootstrap admin set (`ADMIN_IDS` in
  `.env`). A promotable DB role would let the bootstrap admin grant admin rights to e.g. a TA
  without redeploying.
- **Numeric per-user GPU concurrency override.** v1's privilege is a boolean
  (`can_use_multiple_gpus`). A numeric cap (e.g. "this user may hold reservations on up to 3 GPUs
  at once") would be more precise than unlimited/1.
- **Opt-in auto-booking waitlist.** v1's freed-slot watch is notify-only: the student gets a
  push and must manually re-reserve, first to act wins. An auto-booking queue would book the slot
  for the first subscriber automatically the instant it frees, removing the notify-then-race
  friction — at the cost of meaningfully more queue/validation logic.
- **Plotly-based usage charts.** v1 renders admin usage reports with Matplotlib (no extra system
  dependencies). Plotly would give nicer styling at the cost of a heavier dependency (kaleido
  bundles a Chromium-like binary for PNG export).
- **Dockerfile / docker-compose.** A containerized, repeatable deployment path for the lab
  server. Out of scope for v1 since it wasn't requested and doesn't affect the bot's architecture.