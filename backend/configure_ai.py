"""Enable OpenAI locally without putting a key in shell history or output."""

import getpass
import sys
import warnings
from collections.abc import Callable
from os import PathLike
from pathlib import Path

from dotenv import set_key

DEFAULT_ENV_PATH = Path(__file__).resolve().parent / ".env"


def configure_ai(
    env_path: str | PathLike[str] | None = None,
    *,
    input_secret: Callable[[str], str] | None = None,
) -> int:
    """Prompt for a key and update the selected env file; return a CLI status."""
    read_secret = input_secret if input_secret is not None else getpass.getpass
    try:
        # getpass otherwise falls back to visible input when no terminal is present.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            raw_key = read_secret("OpenAI API key (hidden; blank cancels): ")
    except (EOFError, KeyboardInterrupt):
        print("AI setup cancelled.", file=sys.stderr)
        return 1
    except getpass.GetPassWarning:
        print("AI setup requires a terminal with hidden input.", file=sys.stderr)
        return 1

    if "\r" in raw_key or "\n" in raw_key:
        print("The key must not contain line breaks.", file=sys.stderr)
        return 1
    key = raw_key.strip()
    if not key:
        print("AI setup cancelled.", file=sys.stderr)
        return 1
    if len(key) < 20:
        print("The key must contain at least 20 characters.", file=sys.stderr)
        return 1

    target = DEFAULT_ENV_PATH if env_path is None else Path(env_path)
    try:
        set_key(target, "OPENAI_API_KEY", key)
        set_key(target, "AI_MODE", "openai")
    except OSError:
        print("Could not save AI settings to the environment file.", file=sys.stderr)
        return 1

    print("AI enabled. Restart backend to use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(configure_ai())
