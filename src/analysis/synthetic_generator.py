import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List

class SyntheticDataGenerator:
    """
    Generates realistic multi-repository evaluation checkpoint dataset
    matching Phase 1 Corpus Design (18 repos: small/medium/large, python/ts)
    for preliminary statistical pipeline validation.
    """

    REPO_CONFIGS = [
        {"repo_id": "PY-S1", "name": "fastapi-users", "size": "small", "domain": "web", "lang": "python", "base_edges": 120},
        {"repo_id": "PY-S2", "name": "httpie", "size": "small", "domain": "cli", "lang": "python", "base_edges": 180},
        {"repo_id": "PY-S3", "name": "diskcache", "size": "small", "domain": "library", "lang": "python", "base_edges": 95},
        {"repo_id": "PY-M1", "name": "sqlmodel", "size": "medium", "domain": "library", "lang": "python", "base_edges": 310},
        {"repo_id": "PY-M2", "name": "litellm", "size": "medium", "domain": "web", "lang": "python", "base_edges": 540},
        {"repo_id": "PY-M3", "name": "textual", "size": "medium", "domain": "cli", "lang": "python", "base_edges": 480},
        {"repo_id": "PY-L1", "name": "posthog-python", "size": "large", "domain": "web", "lang": "python", "base_edges": 820},
        {"repo_id": "PY-L2", "name": "kedro", "size": "large", "domain": "library", "lang": "python", "base_edges": 1250},
        {"repo_id": "PY-L3", "name": "home-assistant-core", "size": "large", "domain": "web", "lang": "python", "base_edges": 2400},
        {"repo_id": "TS-S1", "name": "trpc", "size": "small", "domain": "web", "lang": "typescript", "base_edges": 140},
        {"repo_id": "TS-S2", "name": "meilisearch-js", "size": "small", "domain": "library", "lang": "typescript", "base_edges": 110},
        {"repo_id": "TS-S3", "name": "inquirer-js", "size": "small", "domain": "cli", "lang": "typescript", "base_edges": 130},
        {"repo_id": "TS-M1", "name": "medusa", "size": "medium", "domain": "web", "lang": "typescript", "base_edges": 620},
        {"repo_id": "TS-M2", "name": "typeorm", "size": "medium", "domain": "library", "lang": "typescript", "base_edges": 740},
        {"repo_id": "TS-M3", "name": "prisma-client", "size": "medium", "domain": "library", "lang": "typescript", "base_edges": 580},
        {"repo_id": "TS-M4", "name": "plop", "size": "small", "domain": "cli", "lang": "typescript", "base_edges": 160},
        {"repo_id": "TS-L1", "name": "nestjs", "size": "large", "domain": "web", "lang": "typescript", "base_edges": 1450},
        {"repo_id": "TS-L2", "name": "directus", "size": "large", "domain": "web", "lang": "typescript", "base_edges": 1900},
    ]

    @classmethod
    def generate_dataset(cls, seed: int = 42) -> pd.DataFrame:
        np.random.seed(seed)
        records = []

        for repo in cls.REPO_CONFIGS:
            repo_id = repo["repo_id"]
            repo_name = repo["name"]
            size = repo["size"]
            domain = repo["domain"]
            lang = repo["lang"]
            base_edges = repo["base_edges"]

            # 1. Agent Trajectory across 3 sessions
            # Agent accumulates violations non-linearly (skewed distribution)
            agent_base_lvc = 0.5 if size == "small" else (1.2 if size == "medium" else 2.5)
            
            for session in range(1, 4):
                # Simulated right-skewed lognormal distribution for violations
                lvc = int(np.random.lognormal(mean=np.log(agent_base_lvc * session), sigma=0.6))
                lvc_norm = (lvc / (base_edges + 1)) * 1000.0
                dged = lvc + int(np.random.randint(1, 5))
                delta_cc = max(1, int(np.random.normal(loc=12 * session, scale=4)))
                cnlv = lvc / delta_cc

                # Test failure probability increases with CNLV
                test_fail_prob = 1.0 / (1.0 + np.exp(-(cnlv * 8.0 - 1.5)))
                tests_passed = bool(np.random.rand() > test_fail_prob)

                records.append({
                    "subject": "agent",
                    "repo_id": repo_id,
                    "repo_name": repo_name,
                    "repo_size": size,
                    "repo_domain": domain,
                    "language": lang,
                    "step_idx": session,
                    "dged": dged,
                    "lvc": lvc,
                    "lvc_norm": lvc_norm,
                    "delta_cc": delta_cc,
                    "cnlv": cnlv,
                    "tests_passed": 1 if tests_passed else 0,
                    "task_failed": 0 if tests_passed else 1
                })

            # 2. Human Baseline Trajectory across 3 historical commits
            # Humans make significantly fewer structural boundary violations
            human_base_lvc = 0.1 if size == "small" else 0.3
            
            for commit_idx in range(1, 4):
                lvc = int(np.random.poisson(lam=human_base_lvc * commit_idx))
                lvc_norm = (lvc / (base_edges + 1)) * 1000.0
                dged = lvc + int(np.random.randint(0, 3))
                delta_cc = max(1, int(np.random.normal(loc=10 * commit_idx, scale=3)))
                cnlv = lvc / delta_cc

                records.append({
                    "subject": "human",
                    "repo_id": repo_id,
                    "repo_name": repo_name,
                    "repo_size": size,
                    "repo_domain": domain,
                    "language": lang,
                    "step_idx": commit_idx,
                    "dged": dged,
                    "lvc": lvc,
                    "lvc_norm": lvc_norm,
                    "delta_cc": delta_cc,
                    "cnlv": cnlv,
                    "tests_passed": 1,  # Historical human commits in main pass tests
                    "task_failed": 0
                })

        return pd.DataFrame(records)
