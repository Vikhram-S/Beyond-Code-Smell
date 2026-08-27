import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
import numpy as np

from src.utils.logger import logger

from dataclasses import dataclass

@dataclass
class MetricResult:
    dged: int
    lvc: int
    lvc_norm: float
    cnlv: float
    delta_cc: int

class MetricsEvaluator:
    """
    Implements Phase 2 architectural drift metrics:
    - Dependency Graph Edit Distance (DGED)
    - Layering Violation Count (LVC & LVC_norm)
    - Conformance Decay Rate (CDR / beta_CDR)
    - Complexity-Normalized Layering Violation (CNLV)
    """

    def __init__(
        self,
        repo_path: Path,
        baseline_manifest: Dict[str, Any],
        layers: Dict[str, List[str]],
        forbidden_rules: List[Dict[str, Any]]
    ):
        self.repo_path = Path(repo_path)
        self.baseline_manifest = baseline_manifest
        self.layers = layers
        self.forbidden_rules = forbidden_rules

    def evaluate(self) -> MetricResult:
        v_pre = set(self.baseline_manifest.get("modules", []))
        e_pre = set(tuple(e) for e in self.baseline_manifest.get("edges", []))
        cc_pre = self.baseline_manifest.get("total_cc", 1)

        v_post, e_post = self.extract_python_import_graph(self.repo_path)
        cc_post = self.compute_cyclomatic_complexity(self.repo_path)

        dged = self.compute_dged(v_pre, e_pre, v_post, e_post)
        lvc, _ = self.compute_lvc(e_pre, e_post, self.layers, self.forbidden_rules)
        lvc_norm = self.compute_normalized_lvc(lvc, len(e_pre))
        cnlv = self.compute_cnlv(lvc, cc_pre, cc_post)
        delta_cc = max(1, cc_post - cc_pre)

        return MetricResult(
            dged=dged,
            lvc=lvc,
            lvc_norm=lvc_norm,
            cnlv=cnlv,
            delta_cc=delta_cc
        )

    @classmethod
    def extract_baseline_manifest(cls, repo_path: Path) -> Dict[str, Any]:
        v0, e0 = cls.extract_python_import_graph(repo_path)
        cc0 = cls.compute_cyclomatic_complexity(repo_path)
        return {
            "modules": list(v0),
            "edges": [list(e) for e in e0],
            "total_cc": cc0
        }

    @staticmethod
    def extract_python_import_graph(repo_path: Path) -> Tuple[Set[str], Set[Tuple[str, str]]]:
        """
        Parses all Python files in repo_path and extracts the module dependency graph G = (V, E).
        V = set of top-level or relative module names
        E = set of (source_module, target_module) directed import edges
        """
        repo_path = Path(repo_path)
        nodes: Set[str] = set()
        edges: Set[Tuple[str, str]] = set()

        if not repo_path.exists():
            return nodes, edges

        py_files = list(repo_path.rglob("*.py"))
        
        for py_file in py_files:
            # Determine module name relative to repo root
            rel_path = py_file.relative_to(repo_path)
            parts = list(rel_path.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            if not parts:
                continue
                
            source_mod = parts[0]  # Top-level package/directory abstraction
            nodes.add(source_mod)

            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(py_file))
            except Exception as e:
                logger.debug(f"Failed AST parse for {py_file}: {e}")
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target_mod = alias.name.split(".")[0]
                        nodes.add(target_mod)
                        if source_mod != target_mod:
                            edges.add((source_mod, target_mod))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        target_mod = node.module.split(".")[0]
                        nodes.add(target_mod)
                        if source_mod != target_mod:
                            edges.add((source_mod, target_mod))

        return nodes, edges

    @staticmethod
    def compute_dged(
        v_pre: Set[str],
        e_pre: Set[Tuple[str, str]],
        v_post: Set[str],
        e_post: Set[Tuple[str, str]]
    ) -> int:
        r"""
        Computes Dependency Graph Edit Distance (DGED):
        DGED = |V_pre \ V_post| + |V_post \ V_pre| + |E_pre \ E_post| + |E_post \ E_pre|
        """
        v_removed = len(v_pre - v_post)
        v_added = len(v_post - v_pre)
        e_removed = len(e_pre - e_post)
        e_added = len(e_post - e_pre)
        
        return v_removed + v_added + e_removed + e_added

    @staticmethod
    def compute_lvc(
        e_pre: Set[Tuple[str, str]],
        e_post: Set[Tuple[str, str]],
        layer_mapping: Dict[str, List[str]],
        forbidden_rules: List[Dict[str, Any]]
    ) -> Tuple[int, List[Tuple[str, str, str]]]:
        r"""
        Computes Layering Violation Count (LVC) for newly introduced edges (E_post \ E_pre).
        Returns (lvc_count, list_of_violations [(src, tgt, rule_desc)]).
        """
        # Map modules to layer IDs
        mod_to_layer: Dict[str, str] = {}
        for layer_id, modules in layer_mapping.items():
            for mod in modules:
                mod_to_layer[mod] = layer_id

        new_edges = e_post - e_pre
        violations: List[Tuple[str, str, str]] = []

        for src, tgt in new_edges:
            src_layer = mod_to_layer.get(src)
            tgt_layer = mod_to_layer.get(tgt)

            if not src_layer or not tgt_layer:
                continue

            for rule in forbidden_rules:
                rule_src = rule.get("source")
                rule_tgts = rule.get("target", [])

                if src_layer == rule_src and tgt_layer in rule_tgts:
                    desc = f"Rule Violation: {src} ({src_layer}) cannot import {tgt} ({tgt_layer})"
                    violations.append((src, tgt, desc))

        return len(violations), violations

    @staticmethod
    def compute_normalized_lvc(lvc: int, baseline_edge_count: int) -> float:
        """
        Computes LVC_norm per 1,000 baseline edges:
        LVC_norm = (LVC / (|E_0| + 1)) * 1000
        """
        return (lvc / (baseline_edge_count + 1)) * 1000.0

    @staticmethod
    def compute_cdr(lvc_series: List[float]) -> float:
        """
        Computes Conformance Decay Rate (CDR / beta_CDR) as the slope of linear fit across sessions.
        lvc_series = [LVC_1, LVC_2, ..., LVC_T]
        Returns slope beta_CDR (violations per session).
        """
        if len(lvc_series) < 2:
            return 0.0

        t = np.arange(1, len(lvc_series) + 1)
        y = np.array(lvc_series, dtype=float)
        
        # Fit linear polynomial y = beta * t + alpha
        slope, _ = np.polyfit(t, y, 1)
        return float(slope)

    @staticmethod
    def compute_cyclomatic_complexity(repo_path: Path) -> int:
        """
        Calculates total Cyclomatic Complexity across Python ASTs in repo_path.
        """
        total_cc = 0
        repo_path = Path(repo_path)

        for py_file in repo_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cc = 1  # Base complexity per function
                    for child in ast.walk(node):
                        if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.Assert, ast.BoolOp)):
                            cc += 1
                    total_cc += cc

        return max(1, total_cc)

    @classmethod
    def compute_cnlv(cls, lvc: int, cc_pre: int, cc_post: int) -> float:
        """
        Computes Complexity-Normalized Layering Violation (CNLV):
        CNLV = LVC / max(1, CC_post - CC_pre)
        """
        delta_cc = max(1, cc_post - cc_pre)
        return float(lvc / delta_cc)
