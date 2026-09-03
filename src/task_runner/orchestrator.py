import re
from pathlib import Path
from typing import Dict, Any, List
from src.utils.logger import logger
from src.utils.shell import run_shell_command
from src.task_runner.adapters import BaseLLMAdapter


class TaskOrchestrator:
    """
    Orchestrates agent execution across N sequential sessions per task.
    Enforces context resets between sessions to simulate long-horizon agent work.
    Sequential only: one LLM call per session.
    """

    def __init__(self, llm_adapter: BaseLLMAdapter, config: Dict[str, Any]):
        self.llm_adapter = llm_adapter
        self.config = config

    @staticmethod
    def list_python_tree(repo_path: Path, limit: int = 80) -> str:
        skip = {".git", "venv", ".venv", "__pycache__", "node_modules", ".tox"}
        files: List[str] = []
        for p in sorted(repo_path.rglob("*.py")):
            if any(tok in p.parts for tok in skip):
                continue
            files.append(str(p.relative_to(repo_path)).replace("\\", "/"))
            if len(files) >= limit:
                break
        return "\n".join(files) if files else "(no python files listed)"

    @staticmethod
    def apply_code_edits(repo_path: Path, llm_response: str):
        """
        Parses Markdown code blocks formatted with '# File: path/to/file.py' header
        and writes edited files to repo_path.
        """
        pattern = r"```(?:python)?\s*\n# File:\s*([^\n]+)\n(.*?)```"
        matches = re.findall(pattern, llm_response, re.DOTALL)

        if not matches:
            logger.warning("No formatted code blocks found in agent response.")
            return

        for rel_file, code_content in matches:
            rel = rel_file.strip().replace("\\", "/").lstrip("./")
            if ".." in Path(rel).parts:
                logger.warning(f"Refusing path traversal edit: {rel}")
                continue
            target_file = repo_path / rel
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(code_content, encoding="utf-8")
            logger.info(f"Applied agent edit to {target_file.relative_to(repo_path)}")

    def run_session(
        self,
        repo_path: Path,
        task_id: str,
        session_idx: int,
        task_prompt: str,
        layers: Dict[str, Any] | None = None,
        forbidden_rules: list | None = None,
    ) -> str:
        tree = self.list_python_tree(repo_path)
        layer_txt = ""
        if layers:
            layer_txt = "Architectural layers (do not invert dependency direction):\n"
            for k, v in layers.items():
                layer_txt += f"  {k}: {', '.join(v)}\n"
        if forbidden_rules:
            layer_txt += "Forbidden new import directions:\n"
            for rule in forbidden_rules:
                layer_txt += f"  {rule.get('source')} -> {rule.get('target')}\n"

        system_prompt = (
            "You are an autonomous software engineering agent working on a real codebase.\n"
            "Generate complete Python files enclosed in Markdown code blocks:\n"
            "```python\n# File: path/to/file.py\n<code content>\n```\n"
            "Prefer small, localized edits. Do not dump unrelated files.\n"
            "Do not use local ML models. Output only code blocks and a one-line summary."
        )

        user_prompt = (
            f"TASK ID: {task_id}\n"
            f"SESSION INDEX: {session_idx} (context is reset; you cannot see prior chat)\n"
            f"{layer_txt}\n"
            f"OBJECTIVE:\n{task_prompt}\n\n"
            f"Existing Python files (truncated listing):\n{tree}\n\n"
            f"Please implement the changes for Session {session_idx}."
        )

        logger.info(f"Executing Agent Session {session_idx} for task {task_id}")
        response = self.llm_adapter.generate_response(system_prompt, user_prompt)
        self.apply_code_edits(repo_path, response)

        run_shell_command("git add .", cwd=repo_path)
        run_shell_command(
            f'git commit --allow-empty -m "Agent session {session_idx} edits"',
            cwd=repo_path,
        )
        return response
