# Supply Chain Digital Twin & Optimization Platform

A multi-agent simulation and optimization platform for retail/e-commerce supply chains.
Combines agent-based simulation (Mesa), network analytics (NetworkX), classical
inventory optimization (OR-Tools), and reinforcement learning (PPO) — exposed through
a FastAPI backend and a React dashboard with live updates.

## Why this exists

Most demand-forecasting portfolio projects stop at "predict the next 28 days of sales."
This one goes further: it simulates the *network* those forecasts feed into (suppliers,
distribution centers, stores), optimizes inventory policy against that network with
classical OR methods, and then asks whether a learned policy (PPO) can beat the
classical baseline under realistic demand uncertainty.

## Roadmap

- [x] **Phase 1** — Architecture & folder structure
- [x] **Phase 2** — FastAPI backend (routing, schemas, app skeleton)
- [x] **Phase 3** — Mesa multi-agent simulation (Store, DistributionCenter, Supplier agents)
- [x] **Phase 4** — NetworkX graph analytics (centrality, bottlenecks, resilience)
- [x] **Phase 5** — OR-Tools inventory optimization ((s,S) policy, EOQ, safety stock)
- [x] **Phase 6** — PPO reinforcement learning (adaptive reorder policy vs. OR-Tools baseline)
- [x] **Phase 7** — React frontend
- [ ] **Phase 8** — Real-time visualization (WebSocket-driven dashboard)
- [ ] **Phase 8** — Real-time visualization (WebSocket-driven dashboard)
- [ ] **Phase 9** — MLflow experiment tracking
- [ ] **Phase 10** — Docker + CI/CD

See `docs/ARCHITECTURE.md` for how the pieces fit together.

## Project layout

```
supply-chain-digital-twin/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app entrypoint        (Phase 2)
│   │   ├── core/               # config, logging               (Phase 2)
│   │   ├── api/routes/         # simulation/analytics/opt/rl    (Phase 2)
│   │   ├── simulation/         # Mesa agents + model            (Phase 3)
│   │   ├── analytics/          # NetworkX graph metrics         (Phase 4)
│   │   ├── optimization/       # OR-Tools solvers               (Phase 5)
│   │   ├── rl/                 # PPO env + training             (Phase 6)
│   │   ├── tracking/           # MLflow helpers                 (Phase 9)
│   │   └── schemas/            # Pydantic models
│   ├── tests/
│   └── requirements.txt
├── frontend/                   # React app                     (Phase 7-8)
├── data/
│   ├── raw/                    # M5 (Walmart) dataset goes here
│   └── processed/
├── notebooks/                  # exploration, model comparison
├── docs/
│   └── ARCHITECTURE.md
├── .github/workflows/          # CI/CD                          (Phase 10)
├── docker-compose.yml                                           (Phase 10)
└── README.md
```

## Local setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # adds pytest + httpx on top of requirements.txt
pytest tests/ -v                      # 51 passing tests (API + Mesa model + NetworkX + OR-Tools + PPO/RL)
uvicorn app.main:app --reload
```

### Try it (Phase 2 endpoints, all backed by a fake stepper until Phase 3)

```bash
curl -X POST http://127.0.0.1:8000/simulation/run \
  -H "Content-Type: application/json" \
  -d '{"num_stores": 4, "num_steps": 5}'
# => {"run_id": "...", "status": "queued", ...}

curl http://127.0.0.1:8000/simulation/<run_id>
curl http://127.0.0.1:8000/analytics/<run_id>/network-metrics
```

`/analytics/<run_id>/network-metrics` is available **immediately** after a
run is created (topology doesn't depend on simulation progress), and returns:

- `degree_centrality` / `betweenness_centrality` — standard NetworkX measures
- `articulation_points` — structural single points of failure (undirected graph)
- `bottlenecks` — a *functional* score, computed separately from articulation
  points on purpose: for every supplier/DC, how many stores lose all supplier
  connectivity if that node fails. This catches a real gap — a supplier
  feeding only one DC is a single point of failure for everything downstream
  of that DC, but it's a degree-1 leaf in its own (possibly disconnected)
  component, so it can never be a structural articulation point by
  definition. `tests/test_network_metrics.py::test_bottleneck_catches_single_dc_supplier_invisible_to_articulation_points`
  pins this down so it can't silently regress.

```bash
curl -X POST http://127.0.0.1:8000/optimization/<run_id>/solve \
  -H "Content-Type: application/json" -d '{}'
```

`/optimization/<run_id>/solve` runs a real OR-Tools CP-SAT solver: every
Store and DC must pick one of 7 service-level tiers, and CP-SAT picks the
combination that minimizes total expected stockout cost under a shared
inventory budget — a multiple-choice knapsack. Each node's cost is weighted
by **Phase 4's bottleneck score**, so a DC whose failure would cut off more
stores is worth protecting harder than its raw demand size alone would
suggest; without that weighting the default symmetric topology gives the
solver nothing a naive demand-proportional split wouldn't already get right.

The result is compared against the simplest possible baseline — give every
node the *same* tier — drawn from the same discrete tier set the solver
itself uses (an earlier draft compared against a continuous allocation
instead, which has access to a strictly richer option space and could beat
the discrete optimum at tight budgets on a technicality; see
`tests/test_solver.py::test_optimized_cost_never_exceeds_naive_uniform_baseline`,
which now holds at every budget level from 0 to 100k by construction). At
the default budget (60% of what a uniform-95%-everywhere policy would use),
the optimizer beats the naive baseline by **~19%**.

The solver also **applies** the result directly to the live model's agents
— any simulation steps run after this call use the optimized
`(reorder_point, order_up_to)` values. Worth knowing: those optimized values
are noticeably leaner than Phase 3's hardcoded defaults, so running the
simulation afterward now produces real stockouts where the original
generous defaults had none. That's the budget constraint doing its job —
Phase 3's defaults were arbitrary; Phase 5's are a deliberate, visible
cost/risk trade-off.

### Phase 6: PPO reinforcement learning

```bash
python -m app.rl.train               # trains for ~4-5 min, saves to app/rl/models/
curl -X POST "http://127.0.0.1:8000/rl/<run_id>/decide?node_id=store_0"
curl -X POST http://127.0.0.1:8000/rl/<run_id>/apply -d '{"store_ids": ["store_0"]}'
curl -X POST "http://127.0.0.1:8000/rl/benchmark?num_episodes=20"   # not run-scoped; see note below
```

PPO controls a single store's order quantity directly each step (no
(s, S) rule at all — just "how much to order, right now"), trained on a
minimal 1-supplier/1-DC/1-store network. Since every store in the default
network shares the same demand profile (Phase 3), the learned policy
generalizes to any of them without retraining. `/rl/<run_id>/apply` assigns
it to control real stores in a live run going forward, the same way
`/optimization/<run_id>/solve` applies an OR-Tools policy in Phase 5.
`/rl/benchmark` isn't scoped to a run_id on purpose — the comparison is
about the trained policy itself, evaluated on the network it was trained
on, not on any particular run's topology.

**The real finding here came from a bug a test caught, not from training
harder.** A first version benchmarked PPO directly against Store's native
`(reorder_point, order_up_to)` rule and PPO lost by ~17%, consistently,
regardless of more training, bigger networks, or normalization. That
result was wrong — not because PPO was undertrained, but because the
comparison was quietly unfair. Store's native rule decides using *this
step's* post-demand state (it runs after `experience_demand` in the
simulation's staged loop); PPO necessarily decides using *last step's*
ending state, since — like any real decision-maker — it can't see today's
demand before placing today's order. A correctness test
(`tests/test_benchmark.py`) caught the mismatch by checking that an
identical (s, S) rule, run through both paths, should cost the same and
didn't. Fixing it meant routing *both* policies through the exact same
decision hook (`model.rl_policies`), removing the baseline's one-step
look-ahead advantage.

Once fixed, **PPO beats the OR-Tools baseline by ~15-17%** — confirmed
robust across multiple independent seed ranges — and beats even the best
`(reorder_point, order_up_to)` pair found by direct grid search over this
exact problem. That's not a contradiction of classical inventory theory:
Scarf's proof that `(s, S)` policies are optimal applies to **backorder**
models (or zero lead time). This simulation uses **lost sales with a
positive lead time** — a regime where `(s, S)` is known in the inventory
literature to *not* be optimal in general, since the best policy can
depend on more than just inventory position. PPO finding a genuinely
better, non-threshold policy here is the kind of structural advantage RL
has once classical optimality guarantees stop applying — see
`docs/ARCHITECTURE.md` for the full writeup.

Live updates while a run is in progress:

```bash
# Python: websockets.connect("ws://127.0.0.1:8000/ws/simulation/<run_id>")
# or any WebSocket client / wscat
```

Note: `/simulation/run` now drives a **real Mesa multi-agent simulation**
(Phase 3) — Store agents sample stochastic demand and reorder from a
DistributionCenter, DCs aggregate store orders and reorder from a Supplier,
and Suppliers produce up to a per-step capacity instead of ordering from
anywhere. That capacity cap is what creates real scarcity and stockouts
downstream when it binds — see `tests/test_simulation.py::test_supplier_capacity_constraint_produces_stockouts`
for a stress test that proves it. Default parameters are deliberately
generous (a "healthy" chain with no stockouts at the default scale) so
there's clear headroom for Phase 5/6 to demonstrate improvement against a
genuinely stressed scenario.

### Phase 7: React frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 — backend must be running separately on :8000
```

A console for everything above: configure and start a run, watch its real
network topology (Phase 4) and live inventory (Phase 3), optimize it
(Phase 5), and compare against the learned policy (Phase 6) — all over
REST. Full details, including two backend additions this phase needed
(a `GET /simulation/:id/state` snapshot endpoint, and `nodes`/`edges` on
`NetworkMetrics` so the topology diagram doesn't have to re-derive Phase
3's network assignment client-side), are in `frontend/README.md`.

Deliberately REST-only, not WebSocket — the roadmap separates "React
Frontend" from "Real-Time Visualization" for a reason, and Phase 8 is
where polling becomes a live subscription. Every data hook here
(`useRunState`, `useNetworkMetrics`) is written so that swap doesn't
require changing what any component reads.

Verified two ways beyond the usual build+lint: a Node script that
replays the exact sequence of API calls the UI makes against the real
backend, asserting every field each component reads is actually present
in the response; and a live CORS preflight + dev-server boot check
confirming the Vite dev server and FastAPI backend talk to each other
correctly end to end. (No headless browser is available in this
environment, so this is the strongest verification short of opening it
in an actual browser.)
