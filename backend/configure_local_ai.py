"""Select the local Ollama provider without asking for or changing API keys."""

import argparse
from os import PathLike
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from dotenv import set_key

DEFAULT_ENV_PATH = Path(__file__).resolve().parent / ".env"
DEFAULT_MODEL = "qwen3:4b-q4_K_M"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def _local_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value.strip())
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
            return None
        return value.strip().rstrip("/")
    except ValueError:
        return None


def configure_local_ai(
    env_path: str | PathLike[str] | None = None,
    *, model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL,
) -> int:
    """Preserve all other settings; configure a loopback-only, local model."""
    model = model.strip()
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}", model)
            or model.endswith((":cloud", "-cloud"))):
        print("Choose a local model name without whitespace or a cloud suffix.", file=sys.stderr)
        return 1
    local_url = _local_url(base_url)
    if local_url is None:
        print("Ollama must use an HTTP loopback address on this computer.", file=sys.stderr)
        return 1
    target = DEFAULT_ENV_PATH if env_path is None else Path(env_path)
    try:
        set_key(target, "AI_MODE", "ollama")
        set_key(target, "OLLAMA_MODEL", model)
        set_key(target, "OLLAMA_BASE_URL", local_url)
    except OSError:
        print("Could not save local AI settings to the environment file.", file=sys.stderr)
        return 1
    print(f"Local AI selected: {model}. Start Ollama and restart the backend. No API key is needed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Use a local Ollama model with TripRescue.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Installed local Ollama model name")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="HTTP loopback Ollama address")
    args = parser.parse_args()
    return configure_local_ai(model=args.model, base_url=args.base_url)


if __name__ == "__main__":
    raise SystemExit(main())
