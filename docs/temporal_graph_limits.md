# Temporal, session, and graph features (scope)

**Current pipeline:** per-flow numeric features (CIC-style), single row per flow.

**Limits:** slow attacks, distributed scans, and long-horizon behavior may look “benign” on each row in isolation.

**Future extensions (not required for core scoring):**

- Per-host or per-subnet **aggregates** over a time window.
- **Sequences** of flows for a 5-tuple or session.
- **Graph** edges (who talks to whom) for lateral movement patterns.

These require additional engineering and storage beyond this repository’s default path.
