import os
import shutil
import tempfile
from typing import Tuple
from urllib.parse import urlparse

from git import Repo, GitCommandError


IGNORE_DIRS = {".git", "node_modules", "dist", "build", "venv", "__pycache__"}


def _is_valid_github_url(repo_url: str) -> bool:
    try:
        parsed = urlparse(repo_url)
        return parsed.scheme in {"http", "https"} and "github.com" in parsed.netloc and len(parsed.path.strip("/").split("/")) >= 2
    except Exception:
        return False


def clone_repo(repo_url: str) -> Tuple[str, str]:
    """
    Clone a GitHub repository into a temporary directory with retry logic.
    Returns:
      (repo_root_path, temp_dir_path)
    """
    if not _is_valid_github_url(repo_url):
        raise ValueError("Invalid GitHub repository URL.")

    temp_dir = tempfile.mkdtemp(prefix="vision_nav_repo_")
    repo_dir = os.path.join(temp_dir, "repo")

    # Retry logic for network issues
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Cloning attempt {attempt + 1}/{max_retries}: {repo_url}")
            Repo.clone_from(repo_url, repo_dir, depth=1)
            print(f"Successfully cloned repository to {repo_dir}")
            return repo_dir, temp_dir
        except GitCommandError as exc:
            print(f"Clone attempt {attempt + 1} failed: {exc}")
            if attempt == max_retries - 1:
                # Last attempt failed, cleanup and raise
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError(f"Failed to clone repository after {max_retries} attempts: {exc}") from exc
            else:
                # Wait before retry
                import time
                time.sleep(2)
                continue


def should_skip_dir(dir_name: str) -> bool:
    return dir_name in IGNORE_DIRS


def cleanup_temp_dir(temp_dir: str) -> None:
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
