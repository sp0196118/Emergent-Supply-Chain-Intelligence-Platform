# Architecture

## Domain model

The simulated network is a 3-echelon retail supply chain:

```
Suppliers  ──►  Distribution Centers  ──►  Stores  ──►  Customer demand
```

- **Store** agents experience stochastic daily demand (seeded from M5/Walmart data
  or a synthetic generator), hold inventory, and place replenishment orders.
- **DistributionCenter** agents aggregate orders from stores, hold buffer inventory,
  and place orders upstream to suppliers.
- **Supplier** agents fulfill orders with a lead time and (optionally) capacity limits.

This gives every downstream phase something concrete to act on:
- Mesa simulates the agents' day-to-day behavior.
- NetworkX treats the Store/DC/Supplier graph as a network and asks structural
  questions (which DC is a single point of failure? which store is hardest to serve?).
- OR-Tools computes the textbook-optimal policy for that network (safety stock,
  reorder points, EOQ) given the demand distribution.
- PPO learns a policy by interacting with the same simulation and is benchmarked
  against the OR-Tools baseline on cost and service level.

## Component responsibilities

| Component | Library | Responsibility |
|---|---|---|
| Simulation engine | Mesa | Agent behavior, time-stepping, state |
| Network analytics | NetworkX | Structural metrics on the agent graph |
| Inventory optimizer | OR-Tools | Classical optimal policies (baseline) |
| RL policy | PPO (stable-baselines3) | Learned adaptive policy (challenger) |
| Experiment tracking | MLflow | Logs every sim/opt/RL run for comparison |
| API layer | FastAPI | Orchestrates runs, exposes REST + WebSocket |
| Frontend | React | Visualizes network, inventory, and policy comparison |
| Packaging | Docker + GitHub Actions | Reproducible local/dev/CI environment |

## Request flow

1. Frontend requests a simulation run (`POST /simulation/run`) with parameters
   (network size, demand scenario, policy type: OR-Tools or PPO).
2. FastAPI spins up a Mesa model, steps it forward, and streams state over a
   WebSocket as it runs.
3. NetworkX metrics are computed once on the network topology (these don't change
   step-to-step unless the topology itself is edited).
4. OR-Tools is called once per scenario to produce the baseline policy; PPO's
   policy network is called once per agent per step (already trained — training
   itself happens offline via `app/rl/train.py`, not inside the live API request).
5. Every run's parameters, cost, and service-level outcome are logged to MLflow.
6. Frontend renders the network graph, an inventory-over-time chart, and a
   side-by-side cost comparison between policies.

## Why not put RL training in the API request path?

Training a PPO policy takes minutes-to-hours; an API request should not block on
that. Training happens as a separate offline step (`app/rl/train.py`), the trained
policy is saved to disk, and the API loads it for inference only. This keeps the
live demo responsive — a detail worth calling out explicitly if asked about it in
an interview.

## Open design decisions for later phases

- **Demand source**: M5 (Walmart) historical data replayed through the simulation,
  vs. a parametric synthetic generator for controlled experiments. Likely: both —
  M5 for realism, synthetic for stress-testing edge cases. Still open — Phase 3
  ships with the synthetic generator only.
- **Network size for the live demo**: confirmed in Phase 3 — at the default
  scale (2 suppliers, 3 DCs, 12 stores) with the default buffer sizes, the
  chain runs ~40 steps with zero stockouts. That's intentional: it's a
  legible "healthy" baseline for the demo graph, with deliberate headroom
  for Phase 5/6 to show improvement against a *stressed* scenario (e.g. a
  supplier capacity cut, demonstrated in `test_supplier_capacity_constraint_produces_stockouts`).
- **PPO action space**: continuous (exact reorder quantity) vs. discrete (reorder
  up to one of a few preset levels). Discrete is simpler to train and to explain.
- **Backorders vs. lost sales**: Phase 3's `fulfill_pending_orders` treats any
  unfulfilled order as lost demand, not backordered. Worth revisiting once
  Phase 5/6 compare policies on cost, since the two have different cost models.
- **Topology has no redundancy yet** (found in Phase 4): the round-robin
  assignment gives every DC exactly one supplier and every store exactly one
  DC, so the network is a strict forest with no failover routing. That's why
  `bottlenecks` in the analytics output currently shows every supplier and
  every DC as a single point of failure for its subtree — there's no
  alternate path for the flow-conservation check to find. Adding redundant
  routing (e.g. a store with two candidate DCs) would be a meaningful Phase 4
  follow-up if resilience modeling becomes a focus, but isn't required for
  Phase 5/6 to proceed.
- **EOQ has no calendar concept** (found in Phase 5): an early draft
  annualized demand (`x365`) before computing EOQ, implicitly assuming a
  simulation step == a day. That produced order-up-to levels ~10x larger
  than anything else in the model. There's no calendar in this simulation,
  so EOQ is computed directly in per-step units — the only unit actually
  consistent with the rest of the system.
- **Baseline comparisons must share the solver's choice space** (found in
  Phase 5): comparing CP-SAT's discrete tier choice against a continuous
  proportional allocation let the "naive" baseline occasionally beat the
  discrete optimum at tight budgets — not because the optimizer was wrong,
  but because continuous allocation has strictly more options available
  than 7 fixed tiers. The fix was a baseline drawn from the same discrete
  tier set ("give everyone the same tier"), which can never beat the true
  optimum by construction. Worth remembering for Phase 6: PPO's baseline
  comparison needs the same care, especially since PPO's action space may
  be continuous while OR-Tools' is tiered.
- **Decision timing must match, or "same policy, two code paths" isn't true**
  (found in Phase 6): Store's native `(reorder_point, order_up_to)` rule
  decides using THIS step's post-demand state; the `model.rl_policies` hook
  PPO uses resolves using LAST step's ending state, since a real-time
  decision-maker can't see today's demand before ordering today. A
  benchmark that compares PPO against the native rule directly is
  therefore comparing two different information sets, not two
  implementations of the same policy — and it understated PPO by ~17%
  *and reversed the sign of the finding* until a correctness test caught
  it (an identical (s, S) rule should cost the same through both paths,
  and didn't). Fixed by routing both arms of every comparison through the
  same `model.rl_policies` hook. Once fixed, PPO beats the OR-Tools
  baseline — and the best (s, S) pair found by direct grid search — by
  ~15-17%. This isn't a contradiction of Scarf's (s, S)-optimality result:
  that proof covers backorder models (or zero lead time), and this
  simulation uses lost sales with a positive lead time, a regime where
  (s, S) is known not to be optimal in general. The lesson generalizes
  beyond this phase: any time two policies are compared through different
  code paths, "looks like the same rule" isn't enough — they need to see
  literally the same inputs at literally the same point in the timeline.
- **A REST endpoint shouldn't expose less than the frontend that consumes
  it actually needs** (found in Phase 7): `NetworkMetrics` originally
  returned only aggregate numbers (centrality, bottleneck scores), not the
  graph structure itself. The alternative to extending it — re-deriving
  Phase 3's round-robin supplier/DC/store assignment client-side just to
  draw a diagram — would have created a second, driftable copy of
  topology logic in JavaScript. Added `nodes`/`edges` fields instead,
  populated directly from the same NetworkX graph the metrics are computed
  from, so the frontend renders the actual topology rather than a
  client-side guess at it. Same reasoning produced `GET /simulation/:id/state`:
  a thin REST wrapper around the existing `model.state_snapshot()`, reused
  as-is rather than duplicated, that Phase 8 will sit a WebSocket
  subscription next to rather than on top of.
