# src/scriptsmith/backends/claude_cli.py
"""Claude Code CLI backend adapter."""

from __future__ import annotations

import locale
import shutil
import subprocess
import sys

from scriptsmith.backends import BackendError, extract_json

# Windows command line limit is ~8191 chars. Keep safe margin.
_MAX_ARG_BYTES = 7000

# On Windows, .CMD wrappers often output in the system's legacy encoding
# (e.g., GBK/cp936 for Chinese Windows) rather than UTF-8.
_FALLBACK_ENCODING = locale.getpreferredencoding(False) if sys.platform == "win32" else "utf-8"


def _find_claude() -> str:
    """Find the claude CLI executable."""
    found = shutil.which("claude")
    if found:
        return found
    raise BackendError(
        "Claude Code CLI not found. Install from https://claude.ai/download"
    )


class ClaudeCLIBackend:
    """Backend that calls Claude Code CLI via subprocess."""

    def __init__(self, model: str = "sonnet", timeout: int = 300, reasoning_effort: str = "medium") -> None:
        self.model = model
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self._claude_path: str | None = None  # Lazy: resolved on first query

    def _get_claude_path(self) -> str:
        """Lazily resolve claude CLI path (avoids failing at import/init time)."""
        if self._claude_path is None:
            self._claude_path = _find_claude()
        return self._claude_path

    def query(self, prompt: str, *, timeout: int | None = None) -> str:
        """Send prompt to Claude CLI, return response text."""
        t = timeout or self.timeout
        claude = self._get_claude_path()

        prompt_bytes = prompt.encode("utf-8")
        # On Windows, non-ASCII chars in CLI args can get mangled by .CMD wrappers.
        # Always use stdin for prompts with non-ASCII or long prompts.
        use_stdin = len(prompt_bytes) >= _MAX_ARG_BYTES or not prompt.isascii()
        if use_stdin:
            cmd = [claude, "-p", "--model", self.model,
                   "--effort", self.reasoning_effort]
            stdin_input = prompt
        else:
            cmd = [claude, "-p", prompt, "--model", self.model,
                   "--effort", self.reasoning_effort]
            stdin_input = None

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=t,
                input=stdin_input.encode("utf-8") if stdin_input else None,
            )
        except FileNotFoundError:
            raise BackendError(
                "Claude Code CLI not found. Install from https://claude.ai/download"
            )
        except subprocess.TimeoutExpired:
            raise BackendError(f"Claude CLI timed out after {t}s")

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else result.stderr
            raise BackendError(f"Claude CLI failed (exit {result.returncode}): {stderr[:500]}")

        # Decode stdout: try UTF-8 first, fall back to system encoding (GBK on Chinese Windows)
        raw = result.stdout
        if isinstance(raw, str):
            return raw  # Already decoded (e.g., in tests or non-Windows)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode(_FALLBACK_ENCODING, errors="replace")

    def query_json(self, prompt: str, *, timeout: int | None = None, retries: int = 2) -> dict:
        """Send prompt, parse JSON from response. Retry on parse failure."""
        current_prompt = prompt
        last_error: BackendError | None = None

        for attempt in range(retries + 1):
            raw = self.query(current_prompt, timeout=timeout)
            try:
                return extract_json(raw)
            except BackendError as e:
                last_error = e
                if attempt < retries:
                    current_prompt = prompt + (
                        "\n\n[IMPORTANT: Your previous response was not valid JSON. "
                        "Output ONLY a valid JSON object. No markdown, no explanation, "
                        "no code fences. Start with { and end with }.]"
                    )

        raise last_error  # type: ignore[misc]
