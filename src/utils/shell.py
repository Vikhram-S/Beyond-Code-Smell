import subprocess
import time
from pathlib import Path
from typing import Tuple
from src.utils.logger import logger

def run_shell_command(
    cmd: str,
    cwd: Path | str,
    timeout: int = 120,
    retries: int = 2,
    backoff_factor: float = 1.5,
    check: bool = False
) -> Tuple[int, str, str]:
    """
    Executes a shell command with retry logic, timeout handling, and structured logging.
    Returns (returncode, stdout, stderr).
    """
    cwd = Path(cwd)
    attempt = 0
    
    while attempt <= retries:
        attempt += 1
        try:
            logger.debug(f"Running command [attempt {attempt}/{retries + 1}]: {cmd} in {cwd}")
            process = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout
            )
            
            if check and process.returncode != 0:
                logger.warning(f"Command '{cmd}' failed with code {process.returncode}: {process.stderr}")
                
            return process.returncode, process.stdout, process.stderr
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Command '{cmd}' timed out after {timeout}s (attempt {attempt}/{retries + 1})")
            if attempt > retries:
                if check:
                    raise RuntimeError(f"Command '{cmd}' timed out after {timeout}s")
                return -1, "", f"Timeout after {timeout}s"
            time.sleep(backoff_factor ** attempt)
            
        except Exception as e:
            logger.error(f"Execution error running '{cmd}': {str(e)}")
            if attempt > retries:
                if check:
                    raise e
                return -1, "", str(e)
            time.sleep(backoff_factor ** attempt)
            
    return -1, "", "Failed all retries"
