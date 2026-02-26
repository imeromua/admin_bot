import html
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


logger = logging.getLogger("admin_bot")


def safe_html(text: str, *, max_len: int) -> str:
    if text is None:
        text = ""
    if len(text) > max_len:
        text = text[:max_len] + "\n\n... (обрізано)"
    return html.escape(text)


def split_text_chunks(text: str, *, max_chunk: int = 3800) -> List[str]:
    """Split text into chunks that fit within Telegram message limits."""
    chunks: List[str] = []
    cur = ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > max_chunk:
            chunks.append(cur)
            cur = line + "\n"
        else:
            cur += line + "\n"
    if cur:
        chunks.append(cur)
    return chunks or [""]


def run_command(
    args: List[str],
    *,
    cwd: Optional[Path] = None,
    timeout: int = 30,
    env: Optional[Dict[str, str]] = None,
    max_output_size: int = 4000,
) -> str:
    """Run a command safely (no shell), capture stdout+stderr."""
    try:
        res = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
        )
        out = (res.stdout or "").strip()
        if len(out) > max_output_size:
            out = out[:max_output_size] + "\n\n... (обрізано, занадто довгий вивід)"
        if res.returncode != 0:
            return f"❌ Error (exit code {res.returncode}):\n{out}"
        return out
    except subprocess.TimeoutExpired:
        return f"⏱ Timeout ({timeout}s)"
    except Exception as e:
        return f"❌ Exception: {e}"
