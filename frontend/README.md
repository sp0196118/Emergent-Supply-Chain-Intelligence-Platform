# Frontend (Phase 7)

A React console for the Supply Chain Digital Twin backend: configure and
start a simulation, watch its network topology and inventory levels, and
compare the OR-Tools (Phase 5) and PPO (Phase 6) policies.

**Scope note:** this phase builds the real app over REST endpoints —
polling for state, not a live push subscription. Real-time updates are
Phase 8's explicit, separate job. Every data-fetching hook here
(`useRunState`, `useNetworkMetrics`) is written so Phase 8 can swap the
polling implementation for a WebSocket listener without changing what any
component reads.

## Setup

```bash
npm install
cp .env.example .env.local   # only needed if the backend isn't on localhost:8000
npm run dev                  # http://localhost:5173
```

The backend must be running separately (`uvicorn app.main:app --reload`
from `backend/`) — its CORS config already allows `localhost:5173`.

```bash
npm run build      # production build to dist/
npm run lint        # oxlint
```

## Structure

```
src/
├── api/client.js          single fetch wrapper for every backend endpoint used here
├── hooks/
│   ├── usePolling.js       generic interval-polling hook
│   ├── useRunState.js      GET /simulation/:id/state, stops polling once a run finishes
│   └── useNetworkMetrics.js  GET /analytics/:id/network-metrics, fetched once (topology is static per run)
├── components/
│   ├── NetworkTopology.jsx   SVG diagram from real node/edge data (Phase 4)
│   ├── InventorySnapshot.jsx live per-node inventory, grouped by kind
│   ├── PolicyLab.jsx         triggers OR-Tools optimize (Phase 5) and PPO benchmark (Phase 6)
│   ├── Sidebar.jsx, StatusBadge.jsx, EmptyState.jsx
└── pages/
    ├── NewRunPage.jsx        run configuration form
    └── RunPage.jsx           topology + inventory + policy lab for one run
```

## Notes on a couple of deliberate choices

- **The "New run" form only exposes `num_suppliers`, `num_distribution_centers`,
  `num_stores`, and `num_steps`.** `SimulationConfig` also has `demand_source`
  and `policy_type` fields, but the backend doesn't actually read them yet
  (nothing in `routes/simulation.py` passes them to `SupplyChainModel`).
  Showing controls that don't affect anything would be misleading, so they're
  left out of the UI until they're wired to real behavior.
- **The backend gained two small additions for this phase**, both reused
  from existing Phase 3/4 internals rather than new logic:
  `GET /simulation/:id/state` (a REST snapshot of `model.state_snapshot()`,
  Phase 7's stand-in for the Phase 8 WebSocket) and `nodes`/`edges` fields
  on `NetworkMetrics` (so the topology diagram renders the real graph
  instead of re-deriving Phase 3's round-robin assignment client-side).
- **"Compare policies" in the Policy Lab isn't scoped to the current run.**
  The PPO policy was trained on a fixed reference network (Phase 6); the
  comparison is about the policy itself, not this run's specific topology.
  "Apply to this run" is the separate action that actually affects the run
  you're looking at.
