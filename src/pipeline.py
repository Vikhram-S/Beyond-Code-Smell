import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.checkpoint_store.store import CheckpointStore
from src.cost_tracker.tracker import CostTracker, QuotaExceededError
from src.human_baseline.baseline_extractor import HumanBaselineExtractor
from src.repo_miner.miner import RepoMiner
from src.task_runner.adapters import ClaudeAPIAdapter, GeminiAPIAdapter, MockLLMAdapter
from src.task_runner.orchestrator import TaskOrchestrator
from src.utils.env_loader import load_gemini_credentials, require_gemini_key
from src.utils.logger import logger
from src.utils.shell import run_shell_command

RESULTS_CSV = Path("results/real_mined_dataset.csv")
CSV_FIELDS = [
    "subject", "repo_id", "repo_name", "repo_size", "repo_domain", "language",
    "step_idx", "commit_sha", "dged", "lvc", "lvc_norm", "delta_cc", "cnlv",
    "beta_cdr", "tests_passed", "task_failed", "matched",
]


def load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        logger.error(f"Configuration file not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _append_rows(rows: List[Dict[str, Any]]) -> None:
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _files_changed_since(repo_path: Path, baseline_sha: str) -> List[str]:
    if not baseline_sha:
        return []
    code, out, _ = run_shell_command(
        f"git diff --name-only {baseline_sha} HEAD",
        cwd=repo_path,
    )
    if code != 0:
        return []
    return [f.strip().replace("\\", "/") for f in out.splitlines() if f.strip()]


def run_pipeline(config_path: Path, dry_run: bool = False, target_repo_key: str | None = None):
    logger.info("==================================================")
    logger.info("Starting Agent Orchestration Harness Pipeline")
    logger.info(f"Config: {config_path} | Dry-Run Mode: {dry_run}")
    logger.info("Sequential, API-only Gemini, checkpointed, 8GB-safe")
    logger.info("==================================================")

    config = load_config(config_path)
    project_root = Path.cwd()
    load_gemini_credentials(project_root)

    if dry_run:
        config["llm"]["provider"] = "mock"

    cost_tracker = CostTracker(config)
    provider = config["llm"]["provider"]
    model_name = config["llm"]["model_name"]

    if provider == "mock" or dry_run:
        llm_adapter = MockLLMAdapter(model_name, cost_tracker)
    elif provider == "gemini":
        key, env_model = require_gemini_key(project_root)
        model_name = env_model or model_name
        llm_adapter = GeminiAPIAdapter(model_name, cost_tracker, api_key=key)
    elif provider == "claude":
        logger.warning("Claude is not the study backend; refusing paid Claude in this rebuild.")
        llm_adapter = ClaudeAPIAdapter(model_name, cost_tracker)
    else:
        raise RuntimeError(
            f"Unknown provider '{provider}'. Use gemini (study) or --dry-run (mock only)."
        )

    orch = config["orchestration"]
    checkpoint_dir = Path(orch.get("checkpoint_dir", "checkpoints"))
    repo_work_dir = Path(orch.get("repo_work_dir", "work_repos"))
    clone_depth = int(orch.get("clone_depth", 1))
    history_deepen = int(orch.get("history_deepen", 200))
    delete_after = bool(orch.get("delete_checkout_after_repo", True))

    checkpoint_store = CheckpointStore(checkpoint_dir)
    miner = RepoMiner(repo_work_dir)

    repos_config = config.get("repos", {})
    selected_repos = [target_repo_key] if target_repo_key else list(repos_config.keys())
    sessions_per_task = config["orchestration"].get("default_sessions_per_task", 3)

    for repo_key in selected_repos:
        repo_cfg = repos_config.get(repo_key)
        if not repo_cfg:
            logger.warning(f"Repo key '{repo_key}' not found in configuration.")
            continue

        repo_name = repo_cfg["name"]
        layers = repo_cfg["layers"]
        forbidden_rules = repo_cfg["forbidden_rules"]
        test_cmd = repo_cfg.get("test_cmd", "pytest")
        clone_url = repo_cfg.get("clone_url")

        logger.info(f"\n--- Processing Repository: {repo_name} ---")
        repo_path = None
        completed_ok = False
        try:
            if dry_run or repo_key == "toy-python-app" or not clone_url:
                repo_path = miner.prepare_toy_repo(repo_name)
            else:
                repo_path = miner.clone_or_update(
                    repo_name, clone_url, clone_depth=clone_depth, history_deepen=history_deepen
                )

            baseline_manifest = miner.extract_baseline_manifest(repo_path)
            task_id = f"TASK-{repo_name.upper()}-01"
            orchestrator = TaskOrchestrator(llm_adapter, config)

            for session_idx in range(1, sessions_per_task + 1):
                if checkpoint_store.is_checkpoint_completed(repo_name, task_id, session_idx):
                    logger.info(
                        f"[IDEMPOTENCY] Session {session_idx} for task {task_id} already checkpointed."
                    )
                    continue

                prompt_key = f"task_prompt_s{session_idx}"
                task_prompt = repo_cfg.get(
                    prompt_key,
                    f"Feature Enhancement Session {session_idx}: extend functionality while respecting layers.",
                )
                transcript = None
                last_session_err: Exception | None = None
                for sess_try in range(1, 9):
                    try:
                        transcript = orchestrator.run_session(
                            repo_path, task_id, session_idx, task_prompt,
                            layers=layers, forbidden_rules=forbidden_rules,
                        )
                        last_session_err = None
                        break
                    except Exception as e:
                        last_session_err = e
                        wait = min(180, 20 * sess_try)
                        logger.warning(
                            f"Session {session_idx} attempt {sess_try}/8 failed ({e}). Sleeping {wait}s."
                        )
                        time.sleep(wait)
                if transcript is None:
                    raise RuntimeError(
                        f"Session {session_idx} failed after 8 outer retries: {last_session_err}"
                    )
                checkpoint_store.save_checkpoint(
                    repo_name=repo_name,
                    task_id=task_id,
                    session_idx=session_idx,
                    repo_path=repo_path,
                    baseline_manifest=baseline_manifest,
                    layers=layers,
                    forbidden_rules=forbidden_rules,
                    test_cmd=test_cmd,
                    transcript=transcript,
                )

            agent_files = _files_changed_since(repo_path, baseline_manifest.get("baseline_sha", ""))
            if not agent_files:
                agent_files = []
                for prefixes in layers.values():
                    for prefix in prefixes:
                        agent_files.append(prefix.replace(".", "/") + ".py")
            intent = repo_cfg.get("task_intent", "feature")
            human_extractor = HumanBaselineExtractor(
                layers, forbidden_rules,
                agent_task_files=agent_files,
                agent_task_intent=intent,
            )
            human_records = human_extractor.extract_human_commit_trajectory(
                repo_path, max_commits=sessions_per_task
            )

            agent_rows = []
            for ckpt in checkpoint_store.get_completed_checkpoints(repo_name, task_id):
                metrics = ckpt.get("metrics", {})
                tests_passed = 1 if ckpt.get("tests_passed") else 0
                agent_rows.append({
                    "subject": "agent",
                    "repo_id": repo_key,
                    "repo_name": repo_name,
                    "repo_size": repo_cfg.get("size", "small"),
                    "repo_domain": repo_cfg.get("domain", "web"),
                    "language": repo_cfg.get("language", "python"),
                    "step_idx": ckpt.get("session_idx"),
                    "commit_sha": "",
                    "dged": metrics.get("dged"),
                    "lvc": metrics.get("lvc"),
                    "lvc_norm": metrics.get("lvc_norm"),
                    "delta_cc": max(1, (metrics.get("cc_post") or 1) - (metrics.get("cc_pre") or 1)),
                    "cnlv": metrics.get("cnlv"),
                    "beta_cdr": metrics.get("beta_cdr"),
                    "tests_passed": tests_passed,
                    "task_failed": 0 if tests_passed == 1 else 1,
                    "matched": True,
                })

            human_rows = []
            for i, rec in enumerate(human_records, start=1):
                m = rec["metrics"]
                human_rows.append({
                    "subject": "human",
                    "repo_id": repo_key,
                    "repo_name": repo_name,
                    "repo_size": repo_cfg.get("size", "small"),
                    "repo_domain": repo_cfg.get("domain", "web"),
                    "language": repo_cfg.get("language", "python"),
                    "step_idx": i,
                    "commit_sha": rec.get("sha", ""),
                    "dged": m.get("dged"),
                    "lvc": m.get("lvc"),
                    "lvc_norm": m.get("lvc", 0),
                    "delta_cc": max(1, (m.get("cc_post") or 1) - (m.get("cc_pre") or 1)),
                    "cnlv": m.get("cnlv"),
                    "beta_cdr": 0.0,
                    "tests_passed": 1,
                    "task_failed": 0,
                    "matched": True,
                })

            if len(human_rows) < sessions_per_task:
                logger.warning(
                    f"{repo_name}: only {len(human_rows)} matched human commits "
                    f"(need {sessions_per_task}). Keeping incomplete pairs; N will reflect reality."
                )

            pair_n = min(len(agent_rows), len(human_rows))
            if pair_n == 0:
                logger.warning(f"{repo_name}: dropped from matched corpus (no human match).")
            else:
                existing_ids = set()
                if RESULTS_CSV.exists():
                    with RESULTS_CSV.open("r", encoding="utf-8") as fh:
                        for row in csv.DictReader(fh):
                            existing_ids.add(row.get("repo_id", ""))
                if repo_key in existing_ids:
                    logger.info(f"[IDEMPOTENCY] Dataset already contains {repo_key}; not duplicating rows.")
                else:
                    _append_rows(agent_rows[:pair_n] + human_rows[:pair_n])

            cost_summary_path = checkpoint_dir / repo_name / "cost_summary.json"
            cost_tracker.export_summary(cost_summary_path)
            (checkpoint_dir / repo_name / "human_matches.json").write_text(
                json.dumps(human_records, indent=2, default=str), encoding="utf-8"
            )
            completed_ok = True
        except QuotaExceededError:
            logger.error("Quota exhausted. Resume later; checkpoints are on disk.")
            raise
        except Exception as e:
            logger.error(f"Repo {repo_name} failed: {e}. Continuing with remaining repos.")
            continue
        finally:
            if delete_after and repo_path and not dry_run and clone_url and completed_ok:
                miner.delete_checkout(repo_path)

    logger.info("\n==================================================")
    logger.info("Pipeline Execution Completed Successfully!")
    logger.info(f"Gemini free-tier USD logged: ${cost_tracker.cumulative_cost_usd:.4f}")
    logger.info(f"Tokens in/out: {cost_tracker.total_input_tokens}/{cost_tracker.total_output_tokens}")
    logger.info(f"Dataset: {RESULTS_CSV}")
    logger.info("==================================================")


def main():
    parser = argparse.ArgumentParser(description="Agent Orchestration Harness for Architectural Drift Paper")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", type=str, default=None)
    args = parser.parse_args()
    run_pipeline(Path(args.config), dry_run=args.dry_run, target_repo_key=args.repo)


if __name__ == "__main__":
    main()
