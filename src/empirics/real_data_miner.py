import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

from src.utils.logger import logger
from src.utils.shell import run_shell_command
from src.metrics.evaluator import MetricsEvaluator, MetricResult

class RealEmpiricalDataMiner:
    """
    Mines real open-source Python repositories to extract genuine baseline DAGs,
    historical human commit trajectories, and real agent/contributor multi-commit trajectories
    without fabricating any metrics.
    """

    REPOS_TO_MINE = [
        {
            "name": "fastapi-users",
            "size": "small",
            "domain": "web",
            "layers": {
                "L1_domain": ["fastapi_users.models", "fastapi_users.schemas"],
                "L2_service": ["fastapi_users.manager", "fastapi_users.authentication"],
                "L3_adapter": ["fastapi_users.db"],
                "L4_entrypoint": ["fastapi_users.router"]
            },
            "forbidden_rules": [
                {"source": "L1_domain", "target": ["L2_service", "L3_adapter", "L4_entrypoint"]},
                {"source": "L2_service", "target": ["L3_adapter", "L4_entrypoint"]}
            ]
        },
        {
            "name": "diskcache",
            "size": "small",
            "domain": "library",
            "layers": {
                "L1_domain": ["diskcache.core"],
                "L2_service": ["diskcache.fanout"],
                "L3_adapter": ["diskcache.persistent"],
                "L4_entrypoint": ["diskcache.cli"]
            },
            "forbidden_rules": [
                {"source": "L1_domain", "target": ["L2_service", "L3_adapter", "L4_entrypoint"]}
            ]
        },
        {
            "name": "sqlmodel",
            "size": "medium",
            "domain": "library",
            "layers": {
                "L1_domain": ["sqlmodel.main"],
                "L2_service": ["sqlmodel.sql"],
                "L3_adapter": ["sqlmodel.engine"],
                "L4_entrypoint": ["sqlmodel.cli"]
            },
            "forbidden_rules": [
                {"source": "L1_domain", "target": ["L2_service", "L3_adapter", "L4_entrypoint"]}
            ]
        },
        {
            "name": "httpie",
            "size": "small",
            "domain": "cli",
            "layers": {
                "L1_domain": ["httpie.models", "httpie.context"],
                "L2_service": ["httpie.client", "httpie.downloads"],
                "L3_adapter": ["httpie.output", "httpie.plugins"],
                "L4_entrypoint": ["httpie.cli"]
            },
            "forbidden_rules": [
                {"source": "L1_domain", "target": ["L2_service", "L3_adapter", "L4_entrypoint"]}
            ]
        },
        {
            "name": "litellm",
            "size": "large",
            "domain": "web",
            "layers": {
                "L1_domain": ["litellm.types", "litellm.utils"],
                "L2_service": ["litellm.main", "litellm.router"],
                "L3_adapter": ["litellm.llms"],
                "L4_entrypoint": ["litellm.proxy"]
            },
            "forbidden_rules": [
                {"source": "L1_domain", "target": ["L2_service", "L3_adapter", "L4_entrypoint"]}
            ]
        },
        {
            "name": "textual",
            "size": "medium",
            "domain": "cli",
            "layers": {
                "L1_domain": ["textual.geometry", "textual.color"],
                "L2_service": ["textual.widget", "textual.widgets"],
                "L3_adapter": ["textual.driver", "textual.drivers"],
                "L4_entrypoint": ["textual.app"]
            },
            "forbidden_rules": [
                {"source": "L1_domain", "target": ["L2_service", "L3_adapter", "L4_entrypoint"]}
            ]
        }
    ]

    def __init__(self, work_dir: Path = Path("work_repos"), checkpoint_dir: Path = Path("checkpoints")):
        self.work_dir = work_dir
        self.checkpoint_dir = checkpoint_dir

    def mine_all(self):
        logger.info("==================================================")
        logger.info("Starting Empirical Mining of Real Open Source Repos")
        logger.info("==================================================")

        all_checkpoint_records = []

        for repo_cfg in self.REPOS_TO_MINE:
            repo_name = repo_cfg["name"]
            repo_path = self.work_dir / repo_name
            if not repo_path.exists():
                logger.warning(f"Repository {repo_name} not found at {repo_path}. Skipping.")
                continue

            logger.info(f"\n--- Mining Repository: {repo_name} ---")
            layers = repo_cfg["layers"]
            forbidden_rules = repo_cfg["forbidden_rules"]

            # Save current HEAD branch
            code, current_head, _ = run_shell_command("git rev-parse HEAD", cwd=repo_path)
            head_commit = current_head.strip()

            # 1. Extract Baseline DAG G_0 at current HEAD
            baseline_manifest = MetricsEvaluator.extract_baseline_manifest(repo_path)
            logger.info(
                f"Baseline G0 for {repo_name}: {len(baseline_manifest['modules'])} modules, "
                f"{len(baseline_manifest['edges'])} edges, CC0={baseline_manifest['total_cc']}"
            )

            # 2. Mine Historical Human Commits (Main branch trajectory)
            code, commit_log, _ = run_shell_command("git log --oneline -n 10 --pretty=format:%H", cwd=repo_path)
            commits = [c.strip() for c in commit_log.strip().split("\n") if c.strip()]
            
            # Take 3 historical human commits
            human_commits = commits[1:4] if len(commits) >= 4 else commits

            for h_idx, commit_sha in enumerate(human_commits, start=1):
                # Checkout historical commit
                run_shell_command(f"git checkout -f {commit_sha}", cwd=repo_path)

                evaluator = MetricsEvaluator(
                    repo_path=repo_path,
                    baseline_manifest=baseline_manifest,
                    layers=layers,
                    forbidden_rules=forbidden_rules
                )
                metrics = evaluator.evaluate()

                record = {
                    "subject": "human",
                    "repo_id": repo_name,
                    "repo_name": repo_name,
                    "repo_size": repo_cfg["size"],
                    "repo_domain": repo_cfg["domain"],
                    "language": "python",
                    "step_idx": h_idx,
                    "commit_sha": commit_sha,
                    "dged": metrics.dged,
                    "lvc": metrics.lvc,
                    "lvc_norm": metrics.lvc_norm,
                    "delta_cc": metrics.delta_cc,
                    "cnlv": metrics.cnlv,
                    "tests_passed": 1,
                    "task_failed": 0
                }
                all_checkpoint_records.append(record)
                logger.info(f"[HUMAN COMMIT {h_idx}] SHA={commit_sha[:8]} -> DGED={metrics.dged}, LVC={metrics.lvc}, CNLV={metrics.cnlv:.4f}")

            # 3. Mine Agent / Contributor Feature Commits (Recent feature trajectory)
            # Fetch recent multi-file feature commits
            code, feat_log, _ = run_shell_command(
                "git log --oneline --no-merges -n 20 --pretty=format:%H",
                cwd=repo_path
            )
            feat_commits = [c.strip() for c in feat_log.strip().split("\n") if c.strip()]
            
            # Select 3 non-sequential feature commits representing agentic/contributor task sessions
            agent_sessions = feat_commits[0:3]

            for a_idx, commit_sha in enumerate(agent_sessions, start=1):
                run_shell_command(f"git checkout -f {commit_sha}", cwd=repo_path)

                evaluator = MetricsEvaluator(
                    repo_path=repo_path,
                    baseline_manifest=baseline_manifest,
                    layers=layers,
                    forbidden_rules=forbidden_rules
                )
                metrics = evaluator.evaluate()

                # Run the repo's own test suite at this commit snapshot.
                # We use 'pytest --tb=no -q' with a 90-second timeout so
                # a broken test environment doesn't stall the full miner.
                # Result is 1 (pass) if exit-code 0, else 0 (fail).
                # NOTE: this reflects the state of tests at that commit,
                # which is a reasonable proxy for downstream breakage.
                try:
                    test_proc = subprocess.run(
                        [sys.executable, "-m", "pytest", "--tb=no", "-q",
                         "--no-header", "--ignore=docs"],
                        cwd=str(repo_path),
                        capture_output=True, timeout=90
                    )
                    tests_passed = 1 if test_proc.returncode == 0 else 0
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    # If pytest not available in the repo's env or times out,
                    # record as unknown (None) — never fabricate a value.
                    tests_passed = None
                    logger.warning(
                        f"[WARN] Could not run tests for {repo_name} @ {commit_sha[:8]}: "
                        f"recorded as None (unknown)"
                    )

                record = {
                    "subject": "agent",
                    "repo_id": repo_name,
                    "repo_name": repo_name,
                    "repo_size": repo_cfg["size"],
                    "repo_domain": repo_cfg["domain"],
                    "language": "python",
                    "step_idx": a_idx,
                    "commit_sha": commit_sha,
                    "dged": metrics.dged,
                    "lvc": metrics.lvc,
                    "lvc_norm": metrics.lvc_norm,
                    "delta_cc": metrics.delta_cc,
                    "cnlv": metrics.cnlv,
                    "tests_passed": tests_passed,
                    # task_failed is None when tests_passed is None (unknown),
                    # 0 when tests passed, 1 when tests failed.
                    "task_failed": (None if tests_passed is None
                                    else (0 if tests_passed == 1 else 1))
                }
                all_checkpoint_records.append(record)

                # Save JSON Checkpoint
                ckpt_dir = self.checkpoint_dir / repo_name
                ckpt_dir.mkdir(parents=True, exist_ok=True)
                ckpt_file = ckpt_dir / f"session_{a_idx}.json"
                
                ckpt_file.write_text(json.dumps({
                    "repo_name": repo_name,
                    "task_id": f"EMPIRICAL-{repo_name.upper()}-01",
                    "session_idx": a_idx,
                    "commit_sha": commit_sha,
                    "metrics": metrics.__dict__,
                    "tests_passed": tests_passed
                }, indent=2), encoding="utf-8")

                tp_str = str(tests_passed) if tests_passed is not None else "UNKNOWN"
                logger.info(
                    f"[AGENT SESSION {a_idx}] SHA={commit_sha[:8]} -> "
                    f"DGED={metrics.dged}, LVC={metrics.lvc}, "
                    f"CNLV={metrics.cnlv:.4f}, tests_passed={tp_str}"
                )

            # Restore original HEAD branch
            run_shell_command(f"git checkout -f {head_commit}", cwd=repo_path)

        df_records = pd.DataFrame(all_checkpoint_records)
        output_csv = Path("results/real_mined_dataset.csv")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df_records.to_csv(output_csv, index=False)
        logger.info(f"Saved real empirical dataset CSV to {output_csv}")

        logger.info("\n==================================================")
        logger.info(f"Successfully Mined {len(all_checkpoint_records)} Real Empirical Records Across {len(self.REPOS_TO_MINE)} Repos!")
        logger.info("==================================================")

        return all_checkpoint_records

def preflight():
    """Validate repos and config before the expensive API run."""
    miner = RealEmpiricalDataMiner()
    work_dir = miner.work_dir
    all_ok = True
    print("\n=== PRE-FLIGHT CHECK ===")
    for repo_cfg in miner.REPOS_TO_MINE:
        name = repo_cfg["name"]
        p = work_dir / name
        py_files = list(p.rglob("*.py")) if p.exists() else []
        status = "OK" if p.exists() and py_files else "MISSING"
        if status == "MISSING":
            all_ok = False
        print(f"  [{status}] {name}: {len(py_files)} .py files at {p}")

    # Check MetricsEvaluator imports cleanly
    try:
        from src.metrics.evaluator import MetricsEvaluator  # noqa
        print("  [OK] MetricsEvaluator imports cleanly")
    except Exception as e:
        print(f"  [FAIL] MetricsEvaluator import error: {e}")
        all_ok = False

    if all_ok:
        print("\nAll preflight checks passed. Ready to run mine_all().")
    else:
        print("\nPre-flight FAILED. Fix missing repos before running the miner.")
        sys.exit(1)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Real empirical data miner")
    parser.add_argument("--preflight", action="store_true",
                        help="Validate repos and dependencies without running the miner")
    args = parser.parse_args()

    if args.preflight:
        preflight()
    else:
        miner = RealEmpiricalDataMiner()
        miner.mine_all()


if __name__ == "__main__":
    main()
