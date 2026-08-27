import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.metrics.evaluator import MetricsEvaluator
from src.utils.logger import logger
from src.utils.shell import run_shell_command

class CheckpointStore:
    """
    Idempotent checkpoint store.
    Snapshots repo state after each agent session, runs test suite,
    extracts import graph, computes metrics, and persists to disk.
    Allows seamless resumption after runtime disconnects.
    """

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def get_session_checkpoint_path(self, repo_name: str, task_id: str, session_idx: int) -> Path:
        return self.checkpoint_dir / repo_name / task_id / f"session_{session_idx}.json"

    def is_checkpoint_completed(self, repo_name: str, task_id: str, session_idx: int) -> bool:
        ckpt_path = self.get_session_checkpoint_path(repo_name, task_id, session_idx)
        return ckpt_path.exists()

    def get_completed_checkpoints(self, repo_name: str, task_id: str) -> List[Dict[str, Any]]:
        task_dir = self.checkpoint_dir / repo_name / task_id
        if not task_dir.exists():
            return []

        checkpoints = []
        for file in sorted(task_dir.glob("session_*.json")):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                checkpoints.append(data)
            except Exception as e:
                logger.warning(f"Error reading checkpoint file {file}: {e}")

        return checkpoints

    def save_checkpoint(
        self,
        repo_name: str,
        task_id: str,
        session_idx: int,
        repo_path: Path,
        baseline_manifest: Dict[str, Any],
        layers: Dict[str, List[str]],
        forbidden_rules: List[Dict[str, Any]],
        test_cmd: str,
        transcript: str
    ) -> Dict[str, Any]:
        """
        Runs test suite, extracts graph G_t, computes metrics, and saves checkpoint.
        """
        ckpt_path = self.get_session_checkpoint_path(repo_name, task_id, session_idx)
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)

        # Baseline graph state
        v_pre = set(baseline_manifest["baseline_nodes"])
        e_pre = set(tuple(e) for e in baseline_manifest["baseline_edges"])
        cc_pre = baseline_manifest["baseline_cyclomatic_complexity"]

        # Run test suite
        test_code, test_out, test_err = run_shell_command(test_cmd, cwd=repo_path, check=False)
        tests_passed = (test_code == 0)

        # Extract current graph G_t
        v_post, e_post = MetricsEvaluator.extract_python_import_graph(repo_path)
        cc_post = MetricsEvaluator.compute_cyclomatic_complexity(repo_path)

        # Compute metrics
        dged = MetricsEvaluator.compute_dged(v_pre, e_pre, v_post, e_post)
        lvc, violations = MetricsEvaluator.compute_lvc(e_pre, e_post, layers, forbidden_rules)
        lvc_norm = MetricsEvaluator.compute_normalized_lvc(lvc, len(e_pre))
        cnlv = MetricsEvaluator.compute_cnlv(lvc, cc_pre, cc_post)

        # Compute trajectory CDR from past session checkpoints
        prior_ckpts = self.get_completed_checkpoints(repo_name, task_id)
        lvc_series = [c["metrics"]["lvc_norm"] for c in prior_ckpts] + [lvc_norm]
        beta_cdr = MetricsEvaluator.compute_cdr(lvc_series)

        # Get git diff snippet
        _, diff_out, _ = run_shell_command("git diff HEAD~1 HEAD", cwd=repo_path)

        checkpoint_data = {
            "repo_name": repo_name,
            "task_id": task_id,
            "session_idx": session_idx,
            "tests_passed": tests_passed,
            "test_output": test_out[:1000],  # Truncate for clean storage
            "metrics": {
                "dged": dged,
                "lvc": lvc,
                "lvc_norm": lvc_norm,
                "cnlv": cnlv,
                "beta_cdr": beta_cdr,
                "cc_pre": cc_pre,
                "cc_post": cc_post
            },
            "violations": [
                {"source": v[0], "target": v[1], "description": v[2]}
                for v in violations
            ],
            "git_diff": diff_out[:2000],
            "transcript": transcript
        }

        ckpt_path.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")
        logger.info(
            f"[CHECKPOINT SAVED] Session {session_idx} -> "
            f"DGED={dged}, LVC={lvc}, CNLV={cnlv:.4f}, CDR={beta_cdr:.4f}, TestsPassed={tests_passed}"
        )
        return checkpoint_data
