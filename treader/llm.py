import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

_KNOWN_BACKENDS = {"claude", "codex"}
DEFAULT_TIMEOUT = 120


class LLMError(Exception):
    pass


def load_llm_settings(vault_path: Path = None) -> tuple:
    """Read llm_backend / llm_timeout_seconds from the vault's config.yaml."""
    backend = None
    timeout = DEFAULT_TIMEOUT
    if vault_path is None:
        return backend, timeout
    config_path = Path(vault_path) / "config.yaml"
    if not config_path.exists():
        return backend, timeout
    try:
        config = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError:
        return backend, timeout
    if not isinstance(config, dict):
        return backend, timeout
    backend = config.get("llm_backend") or None
    raw_timeout = config.get("llm_timeout_seconds")
    if raw_timeout:
        try:
            timeout = int(raw_timeout)
        except (TypeError, ValueError):
            pass
    return backend, timeout


def detect_backend(config_override: str = None) -> str:
    if config_override:
        return config_override
    if shutil.which("claude"):
        return "claude"
    if shutil.which("codex"):
        return "codex"
    raise LLMError(
        "No LLM backend found. Install Claude Code (claude) or OpenAI Codex CLI (codex)."
    )


def _run(backend: str, prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    if backend not in _KNOWN_BACKENDS:
        raise LLMError(f"Unknown backend '{backend}'. Choose from: {_KNOWN_BACKENDS}")
    cmd = ["claude", "-p", prompt] if backend == "claude" else ["codex", "-q", prompt]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise LLMError(f"Backend timed out after {timeout}s")
    if result.returncode != 0:
        raise LLMError(
            f"Backend '{backend}' exited {result.returncode}.\nstderr: {result.stderr.strip()[:500]}"
        )
    return result.stdout.strip()


def call_text(
    prompt: str,
    config_override: str = None,
    timeout: int = None,
    vault_path: Path = None,
) -> str:
    config_backend, config_timeout = load_llm_settings(vault_path)
    backend = detect_backend(config_override or config_backend)
    return _run(backend, prompt, timeout if timeout is not None else config_timeout)


def call_structured(
    prompt: str,
    config_override: str = None,
    timeout: int = None,
    vault_path: Path = None,
) -> Any:
    config_backend, config_timeout = load_llm_settings(vault_path)
    backend = detect_backend(config_override or config_backend)
    if timeout is None:
        timeout = config_timeout
    for attempt in range(2):
        current_prompt = prompt if attempt == 0 else (
            prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON. No preamble, no explanation, no markdown."
        )
        raw = _run(backend, current_prompt, timeout)
        text = raw
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:] if lines[0].startswith("```") else lines
            lines = lines[:-1] if lines and lines[-1].startswith("```") else lines
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if attempt == 1:
                raise LLMError(
                    f"LLM returned unparseable JSON after 2 attempts.\nRaw output:\n{raw[:500]}"
                )
