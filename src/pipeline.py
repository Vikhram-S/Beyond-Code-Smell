import argparse
import sys
import yaml
from pathlib import Path
from typing import Dict, Any

from src.utils.logger import logger, setup_logger
from src.cost_tracker.tracker import CostTracker
from src.repo_miner.miner import RepoMiner
from src.task_runner.adapters import MockLLMAdapter, ClaudeAPIAdapter
from src.task_runner.orchestrator import TaskOrchestrator
from src.checkpoint_store.store import CheckpointStore
from src.human_baseline.baseline_extractor import HumanBaselineExtractor

def load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        logger.error(f"Configuration file not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_pipeline(config_path: Path, dry_run: bool = False, target_repo_key: str | None = None):
    logger.info("==================================================")
    logger.info("Starting Agent Orchestration Harness Pipeline")
    logger.info(f"Config: {config_path} | Dry-Run Mode: {dry_run}")
    logger.info("==================================================")

    config = load_config(config_path)
    
    # Override provider if dry-run
    if dry_run:
        config["llm"]["provider"] = "mock"

    # Initialize Cost Tracker
    cost_tracker = CostTracker(config)

    # Initialize LLM Adapter
    provider = config["llm"]["provider"]
    model_name = config["llm"]["model_name"]

    if provider == "mock" or dry_run:
        llm_adapter = MockLLMAdapter(model_name, cost_tracker)
    elif provider == "claude":
        llm_adapter = ClaudeAPIAdapter(model_name, cost_tracker)
    else:
        logger.warning(f"Unknown provider '{provider}', falling back to MockLLMAdapter.")
        llm_adapter = MockLLMAdapter(model_name, cost_tracker)

    # Setup directories
    checkpoint_dir = Path(config["orchestration"].get("checkpoint_dir", "checkpoints"))
    repo_work_dir = Path(config["orchestration"].get("repo_work_dir", "work_repos"))
    
    checkpoint_store = CheckpointStore(checkpoint_dir)
    miner = RepoMiner(repo_work_dir)

    repos_config = config.get("repos", {})
    selected_repos = [target_repo_key] if target_repo_key else list(repos_config.keys())

    for repo_key in selected_repos:
        repo_cfg = repos_config.get(repo_key)
        if not repo_cfg:
            logger.warning(f"Repo key '{repo_key}' not found in configuration.")
            continue

        repo_name = repo_cfg["name"]
        layers = repo_cfg["layers"]
        forbidden_rules = repo_cfg["forbidden_rules"]
        test_cmd = repo_cfg.get("test_cmd", "pytest")
        sessions_per_task = config["orchestration"].get("default_sessions_per_task", 3)

        logger.info(f"\n--- Processing Repository: {repo_name} ---")

        # Prepare workspace repository
        if repo_key == "toy-python-app" or dry_run:
            repo_path = miner.prepare_toy_repo(repo_name)
        else:
            repo_path = repo_work_dir / repo_name

        # Step 1: Baseline Manifest Extraction
        baseline_manifest = miner.extract_baseline_manifest(repo_path)

        # Step 2: Task Orchestration & Session Checkpoints
        task_id = f"TASK-{repo_name.upper()}-01"
        orchestrator = TaskOrchestrator(llm_adapter, config)

        for session_idx in range(1, sessions_per_task + 1):
            if checkpoint_store.is_checkpoint_completed(repo_name, task_id, session_idx):
                logger.info(
                    f"[IDEMPOTENCY] Session {session_idx} for task {task_id} "
                    f"already checkpointed. Skipping execution."
                )
                continue

            task_prompt = f"Feature Enhancement Session {session_idx}: Extend functionality while respecting layers."
            
            # Execute Agent Session
            transcript = orchestrator.run_session(repo_path, task_id, session_idx, task_prompt)

            # Save Checkpoint & Evaluate Metrics
            checkpoint_store.save_checkpoint(
                repo_name=repo_name,
                task_id=task_id,
                session_idx=session_idx,
                repo_path=repo_path,
                baseline_manifest=baseline_manifest,
                layers=layers,
                forbidden_rules=forbidden_rules,
                test_cmd=test_cmd,
                transcript=transcript
            )

        # Step 3: Human Baseline Metric Extraction
        logger.info("\n--- Extracting Human Historical Baseline ---")
        human_extractor = HumanBaselineExtractor(layers, forbidden_rules)
        human_baseline_results = human_extractor.extract_human_commit_trajectory(repo_path, max_commits=3)

        # Export Cost Summary
        cost_summary_path = checkpoint_dir / repo_name / "cost_summary.json"
        cost_tracker.export_summary(cost_summary_path)

    logger.info("\n==================================================")
    logger.info("Pipeline Execution Completed Successfully!")
    logger.info(f"Total API Cost: ${cost_tracker.cumulative_cost_usd:.4f}")
    logger.info("==================================================")

def main():
    parser = argparse.ArgumentParser(description="Agent Orchestration Harness for Architectural Drift Paper")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to YAML configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Run in mock/dry-run mode without invoking paid APIs")
    parser.add_argument("--repo", type=str, default=None, help="Target specific repo key from config")
    args = parser.parse_args()

    run_pipeline(
        config_path=Path(args.config),
        dry_run=args.dry_run,
        target_repo_key=args.repo
    )

if __name__ == "__main__":
    main()
