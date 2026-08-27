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
    """

    def __init__(self, llm_adapter: BaseLLMAdapter, config: Dict[str, Any]):
        self.llm_adapter = llm_adapter
        self.config = config

    @staticmethod
    def apply_code_edits(repo_path: Path, llm_response: str):
        """
        Parses Markdown code blocks formatted with '# File: path/to/file.py' header
        and writes edited files to repo_path.
        """
        pattern = r"```python\s*\n# File:\s*([^\n]+)\n(.*?)```"
        matches = re.findall(pattern, llm_response, re.DOTALL)

        if not matches:
            logger.warning("No formatted code blocks found in agent response.")
            return

        for rel_file, code_content in matches:
            target_file = repo_path / rel_file.strip()
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(code_content, encoding="utf-8")
            logger.info(f"Applied agent edit to {target_file.relative_to(repo_path)}")

    def run_session(
        self,
        repo_path: Path,
        task_id: str,
        session_idx: int,
        task_prompt: str
    ) -> str:
        """
        Executes a single agent session.
        Wipes chat context before session to enforce multi-session long-horizon evaluation.
        """
        system_prompt = (
            "You are an autonomous software engineering agent working on a codebase.\n"
            "You must generate complete python files enclosed in Markdown code blocks:\n"
            "```python\n# File: path/to/file.py\n<code content>\n```\n"
            "Do not modify files outside your objective scope."
        )

        user_prompt = (
            f"TASK ID: {task_id}\n"
            f"SESSION INDEX: {session_idx}\n"
            f"OBJECTIVE:\n{task_prompt}\n\n"
            f"Please implement the changes for Session {session_idx}."
        )

        logger.info(f"Executing Agent Session {session_idx} for task {task_id}")
        response = self.llm_adapter.generate_response(system_prompt, user_prompt)
        
        # Apply edits to workspace
        self.apply_code_edits(repo_path, response)

        # Create git commit for this session
        run_shell_command("git add .", cwd=repo_path)
        run_shell_command(f"git commit -m 'Agent session {session_idx} edits'", cwd=repo_path)

        return response
