"""
human_baseline/baseline_extractor.py
=====================================
Matched-Task Human Baseline Extractor.

Design rationale
----------------
Comparing agent sessions against arbitrary organic commit history is not
apples-to-apples (a reviewer WILL say so).  Instead we enforce a
**matched-pair design**: for every agent task T_agent we select exactly ONE
real historical human commit T_human from the same repository that satisfies
all three matching criteria:

  1. Scope Equivalency:   |files_human - files_agent| <= FILE_TOUCH_TOLERANCE
  2. Intent Equivalency:  issue_type in {bugfix, feature, refactor} matches
  3. Subsystem Locality:  changed files overlap the same architectural layer

If NO such commit exists the repository is DROPPED from the corpus rather
than keeping an unmatched comparison.  This is enforced via
`MatchedBaselineResult.matched` == False which signals the pipeline to
exclude the repo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.metrics.evaluator import MetricsEvaluator
from src.utils.logger import logger
from src.utils.shell import run_shell_command

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FILE_TOUCH_TOLERANCE = 2          # |files_human - files_agent| <= 2
SUBSYSTEM_OVERLAP_MIN = 0.30      # ≥30 % of changed files must share a layer

BUGFIX_KEYWORDS  = {"fix", "bug", "patch", "error", "issue", "regression"}
FEATURE_KEYWORDS = {"add", "feature", "implement", "introduce", "new", "support"}
REFACTOR_KEYWORDS = {"refactor", "clean", "rename", "move", "restructure", "reorganize"}


def _classify_intent(subject: str) -> str:
    """Return 'bugfix', 'feature', 'refactor', or 'unknown'."""
    lower = subject.lower()
    if any(k in lower for k in BUGFIX_KEYWORDS):
        return "bugfix"
    if any(k in lower for k in FEATURE_KEYWORDS):
        return "feature"
    if any(k in lower for k in REFACTOR_KEYWORDS):
        return "refactor"
    return "unknown"


def _files_changed_by_commit(sha: str, repo_path: Path) -> List[str]:
    """Return list of files changed in a commit (relative paths)."""
    code, out, _ = run_shell_command(
        f"git diff-tree --no-commit-id -r --name-only {sha}",
        cwd=repo_path,
    )
    if code != 0:
        return []
    return [f.strip() for f in out.strip().splitlines() if f.strip()]


def _subsystem_of_file(filepath: str, layers: Dict[str, List[str]]) -> Optional[str]:
    """Return the first layer key whose path-prefix matches, else None."""
    for layer_name, prefixes in layers.items():
        for prefix in prefixes:
            if filepath.startswith(prefix.rstrip("/")):
                return layer_name
    return None


def _files_subsystems(files: List[str], layers: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Map each file to its layer (or 'unknown')."""
    mapping: Dict[str, List[str]] = {}
    for f in files:
        layer = _subsystem_of_file(f, layers) or "unknown"
        mapping.setdefault(layer, []).append(f)
    return mapping


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MatchedCommit:
    sha: str
    subject: str
    files_changed: List[str]
    intent: str
    layer_mapping: Dict[str, List[str]]
    score: float = 0.0          # Higher is better match


@dataclass
class MatchedBaselineResult:
    matched: bool
    reason: str = ""
    commit: Optional[MatchedCommit] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------

class HumanBaselineExtractor:
    """
    Selects a MATCHED historical human commit for each agent task and
    computes the same DGED / LVC / CNLV metrics over that commit delta.

    Parameters
    ----------
    layers : dict mapping layer name -> list of directory prefixes
    forbidden_rules : list of layer-dependency violation rule dicts
    agent_task_files : list of files the agent task is expected to touch
    agent_task_intent : 'bugfix' | 'feature' | 'refactor'
    max_candidates : how far back in git log to search (default 500)
    """

    def __init__(
        self,
        layers: Dict[str, List[str]],
        forbidden_rules: List[Dict[str, Any]],
        agent_task_files: List[str],
        agent_task_intent: str,
        max_candidates: int = 500,
    ) -> None:
        self.layers = layers
        self.forbidden_rules = forbidden_rules
        self.agent_task_files = agent_task_files
        self.agent_task_intent = agent_task_intent
        self.max_candidates = max_candidates

    # ------------------------------------------------------------------
    # Step 1 — Candidate selection
    # ------------------------------------------------------------------

    def _collect_candidates(
        self, repo_path: Path
    ) -> List[MatchedCommit]:
        """
        Walk the last `max_candidates` commits and return all that pass the
        three hard matching criteria.
        """
        n_agent = len(self.agent_task_files)
        agent_layers = _files_subsystems(self.agent_task_files, self.layers)

        code, out, _ = run_shell_command(
            f"git log --oneline -n {self.max_candidates} --pretty=format:%H%x09%s",
            cwd=repo_path,
        )
        if code != 0 or not out.strip():
            return []

        candidates: List[MatchedCommit] = []

        for line in out.strip().splitlines():
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            sha, subject = parts[0].strip(), parts[1].strip()

            # --- criterion 1: scope equivalency ---
            files = _files_changed_by_commit(sha, repo_path)
            n_human = len(files)
            if abs(n_human - n_agent) > FILE_TOUCH_TOLERANCE:
                continue

            # --- criterion 2: intent equivalency ---
            intent = _classify_intent(subject)
            if intent != self.agent_task_intent and intent != "unknown":
                continue

            # --- criterion 3: subsystem locality ---
            human_layers = _files_subsystems(files, self.layers)
            shared_layers = set(agent_layers.keys()) & set(human_layers.keys()) - {"unknown"}
            all_layers    = set(agent_layers.keys()) | set(human_layers.keys()) - {"unknown"}
            if all_layers:
                overlap = len(shared_layers) / len(all_layers)
            else:
                overlap = 0.0
            if overlap < SUBSYSTEM_OVERLAP_MIN:
                continue

            # Compute a simple score: lower file-delta + higher overlap
            score = overlap - (abs(n_human - n_agent) * 0.1)

            candidates.append(MatchedCommit(
                sha=sha,
                subject=subject,
                files_changed=files,
                intent=intent,
                layer_mapping=human_layers,
                score=score,
            ))

        return sorted(candidates, key=lambda c: c.score, reverse=True)

    # ------------------------------------------------------------------
    # Step 2 — Metric extraction for the winning commit
    # ------------------------------------------------------------------

    def _extract_metrics_for_commit(
        self, repo_path: Path, commit: MatchedCommit
    ) -> Dict[str, Any]:
        """
        Checkout parent → commit, compute metrics delta, restore HEAD.
        """
        # Find parent SHA
        code, parent_out, _ = run_shell_command(
            f"git rev-parse {commit.sha}^1",
            cwd=repo_path,
        )
        if code != 0:
            return {}
        parent_sha = parent_out.strip()

        try:
            run_shell_command(f"git checkout {parent_sha}", cwd=repo_path)
            v_pre, e_pre = MetricsEvaluator.extract_python_import_graph(repo_path)
            cc_pre = MetricsEvaluator.compute_cyclomatic_complexity(repo_path)

            run_shell_command(f"git checkout {commit.sha}", cwd=repo_path)
            v_post, e_post = MetricsEvaluator.extract_python_import_graph(repo_path)
            cc_post = MetricsEvaluator.compute_cyclomatic_complexity(repo_path)
        finally:
            run_shell_command("git checkout -", cwd=repo_path)

        dged = MetricsEvaluator.compute_dged(v_pre, e_pre, v_post, e_post)
        lvc, violations = MetricsEvaluator.compute_lvc(
            e_pre, e_post, self.layers, self.forbidden_rules
        )
        cnlv = MetricsEvaluator.compute_cnlv(lvc, cc_pre, cc_post)

        return {
            "dged": dged,
            "lvc": lvc,
            "cnlv": cnlv,
            "cc_pre": cc_pre,
            "cc_post": cc_post,
            "violations_count": len(violations),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_matched_baseline(self, repo_path: Path) -> MatchedBaselineResult:
        """
        Entry-point called by the orchestration pipeline.

        Returns a MatchedBaselineResult.  If `matched == False`, the caller
        MUST drop this repository from the corpus.
        """
        logger.info(
            f"[MatchedBaseline] Searching up to {self.max_candidates} commits "
            f"for intent='{self.agent_task_intent}', "
            f"agent_files={len(self.agent_task_files)}"
        )

        candidates = self._collect_candidates(repo_path)

        if not candidates:
            reason = (
                f"No historical human commit satisfies all three matching criteria "
                f"(scope ±{FILE_TOUCH_TOLERANCE}, intent='{self.agent_task_intent}', "
                f"subsystem overlap ≥{SUBSYSTEM_OVERLAP_MIN:.0%}). "
                f"Repository MUST be excluded from corpus."
            )
            logger.warning(f"[MatchedBaseline] {reason}")
            return MatchedBaselineResult(matched=False, reason=reason)

        best = candidates[0]
        logger.info(
            f"[MatchedBaseline] Selected commit {best.sha[:8]} "
            f"('{best.subject[:60]}') "
            f"score={best.score:.3f}, files={len(best.files_changed)}"
        )

        metrics = self._extract_metrics_for_commit(repo_path, best)
        if not metrics:
            return MatchedBaselineResult(
                matched=False,
                reason=f"Metric extraction failed for commit {best.sha}.",
            )

        return MatchedBaselineResult(
            matched=True,
            reason="",
            commit=best,
            metrics=metrics,
        )
