import json
from pathlib import Path
from typing import Dict, Any
from src.metrics.evaluator import MetricsEvaluator
from src.utils.logger import logger
from src.utils.shell import run_shell_command

class RepoMiner:
    """
    Clones/prepares repository workspace, extracts baseline architecture graph (Phase 2),
    and snapshots pre-task state.
    """

    def __init__(self, work_dir: Path):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def prepare_toy_repo(self, repo_name: str) -> Path:
        """
        Creates a synthetic baseline Python repository workspace for testing / dry-runs.
        Structure:
        domain/
           __init__.py
           entity.py
        service/
           __init__.py
           user_service.py
        adapters/
           __init__.py
           db.py
        api/
           __init__.py
           routes.py
        """
        repo_path = self.work_dir / repo_name
        if repo_path.exists():
            return repo_path

        logger.info(f"Setting up synthetic repository workspace at {repo_path}")
        repo_path.mkdir(parents=True, exist_ok=True)

        # Domain
        (repo_path / "domain").mkdir(exist_ok=True)
        (repo_path / "domain" / "__init__.py").write_text("# Domain Package", encoding="utf-8")
        (repo_path / "domain" / "entity.py").write_text(
            "class User:\n    def __init__(self, name):\n        self.name = name\n",
            encoding="utf-8"
        )

        # Service
        (repo_path / "service").mkdir(exist_ok=True)
        (repo_path / "service" / "__init__.py").write_text("# Service Package", encoding="utf-8")
        (repo_path / "service" / "user_service.py").write_text(
            "from domain.entity import User\n\nclass UserService:\n    def get_user(self):\n        return User('Alice')\n",
            encoding="utf-8"
        )

        # Adapters
        (repo_path / "adapters").mkdir(exist_ok=True)
        (repo_path / "adapters" / "__init__.py").write_text("# Adapters Package", encoding="utf-8")
        (repo_path / "adapters" / "db.py").write_text(
            "from service.user_service import UserService\n\nclass DBAdapter:\n    pass\n",
            encoding="utf-8"
        )

        # API
        (repo_path / "api").mkdir(exist_ok=True)
        (repo_path / "api" / "__init__.py").write_text("# API Package", encoding="utf-8")
        (repo_path / "api" / "routes.py").write_text(
            "from service.user_service import UserService\n\ndef route():\n    return UserService().get_user()\n",
            encoding="utf-8"
        )

        # Tests
        (repo_path / "tests").mkdir(exist_ok=True)
        (repo_path / "tests" / "test_app.py").write_text(
            "from api.routes import route\n\ndef test_route():\n    assert route().name == 'Alice'\n",
            encoding="utf-8"
        )

        # Initialize git
        run_shell_command("git init", cwd=repo_path)
        run_shell_command("git config user.name 'Harness Evaluator'", cwd=repo_path)
        run_shell_command("git config user.email 'harness@evaluator.local'", cwd=repo_path)
        run_shell_command("git add .", cwd=repo_path)
        run_shell_command("git commit -m 'Initial baseline commit'", cwd=repo_path)

        return repo_path

    def extract_baseline_manifest(self, repo_path: Path) -> Dict[str, Any]:
        """
        Extracts pre-task graph nodes, edges, and cyclomatic complexity.
        """
        nodes, edges = MetricsEvaluator.extract_python_import_graph(repo_path)
        cc = MetricsEvaluator.compute_cyclomatic_complexity(repo_path)

        manifest = {
            "repo_name": repo_path.name,
            "baseline_nodes": sorted(list(nodes)),
            "baseline_edges": [list(e) for e in sorted(list(edges))],
            "baseline_edge_count": len(edges),
            "baseline_cyclomatic_complexity": cc
        }

        manifest_path = repo_path / "baseline_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        logger.info(
            f"Baseline extracted for {repo_path.name}: {len(nodes)} modules, "
            f"{len(edges)} edges, CC={cc}"
        )
        return manifest
