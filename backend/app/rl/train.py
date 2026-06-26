"""
Offline PPO training script — run separately from the API, never inside a
request (training takes far longer than an HTTP request should ever
block for). Trains against app/rl/env.py and saves both the policy and its
observation/reward normalization statistics to app/rl/models/, for
app/rl/policy.py to load at inference time.

Run directly:  python -m app.rl.train

Note on normalization: raw observations mix very different scales
(inventory ~0-150 vs. demand_std~3) and raw rewards range roughly -350 to 0
per step. Both slow PPO's convergence noticeably if left unnormalized — an
early draft without VecNormalize plateaued ~10 points further from the
baseline at the same timestep budget. VecNormalize's running statistics
have to be saved and reused at inference exactly as they were during
training, or the policy sees a different input distribution than it was
trained on.

Note on what "good" looks like here: a first version of this benchmark
compared PPO directly against Store's NATIVE (reorder_point, order_up_to)
rule and found PPO losing by ~17% — but that comparison was quietly unfair.
The native rule decides using THIS step's post-demand state (it runs after
experience_demand in the simulation's staged loop), while PPO necessarily
decides using LAST step's ending state, since it can't see today's demand
before placing today's order any more than a real decision-maker could.
Once both policies were routed through the same model.rl_policies hook
(see app/rl/benchmark.py), eliminating that one-step look-ahead asymmetry,
PPO actually beats the OR-Tools baseline by ~15-17%, and even beats the
single best (reorder_point, order_up_to) pair found by direct grid search
over this exact problem. That's not a contradiction of Phase 5's findings:
Scarf's classical proof that (s, S) policies are optimal applies to
backorder inventory models (or zero lead time); this model uses LOST sales
with a positive lead time, a setting where (s, S) is known in the
inventory literature to NOT be optimal in general, since the best policy
can depend on more than just inventory position. PPO finding a genuinely
better, non-threshold policy here is exactly the kind of structural
advantage RL has over classical theory once the theory's optimality
guarantees stop applying. Full writeup in docs/ARCHITECTURE.md.
"""
import argparse
import os

from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import VecNormalize

from app.rl.env import SupplyChainEnv

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "ppo_store_policy.zip")
VECNORM_PATH = os.path.join(MODEL_DIR, "vecnormalize.pkl")


def train(
    total_timesteps: int = 1_000_000,
    n_envs: int = 8,
    seed: int = 0,
    verbose: int = 1,
) -> str:
    os.makedirs(MODEL_DIR, exist_ok=True)

    vec_env = make_vec_env(lambda: SupplyChainEnv(), n_envs=n_envs, seed=seed)
    vec_env = VecNormalize(vec_env, norm_obs=True, norm_reward=True, clip_obs=10.0)

    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=verbose,
        seed=seed,
        n_steps=512,
        batch_size=512,
        gamma=0.99,  # lead_time=2 delay between ordering and arrival needs reasonable future weighting
        ent_coef=0.01,  # extra exploration -- without it, early runs converged to a narrower, worse policy
    )
    model.learn(total_timesteps=total_timesteps)

    model.save(MODEL_PATH)
    vec_env.save(VECNORM_PATH)
    return MODEL_PATH


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    path = train(total_timesteps=args.timesteps, seed=args.seed)
    print(f"saved model to {path}")
