import getpass
import runpy
import warnings
from pathlib import Path

import pytest
from dotenv import dotenv_values

import configure_ai as setup


SECRET = "example-local-test-secret-123456789"
EXISTING_ENV = (
    "# Keep existing local settings\n"
    "DATABASE_URL=sqlite:///./data/custom.db\n"
    'CORS_ORIGINS=\'["http://localhost:9123"]\'\n'
    "OPENAI_MODEL=custom-model\n"
    "OTHER_SETTING=keep-me\n"
    "AI_MODE=demo\n"
    "OPENAI_API_KEY=previous-test-secret\n"
)


def test_updates_only_ai_settings_and_never_echoes_key(tmp_path, capsys):
    env_path = tmp_path / ".env"
    env_path.write_text(EXISTING_ENV, encoding="utf-8")
    before = dotenv_values(env_path)

    result = setup.configure_ai(env_path, input_secret=lambda _: f"  {SECRET}  ")

    after = dotenv_values(env_path)
    assert result == 0
    assert after == {**before, "OPENAI_API_KEY": SECRET, "AI_MODE": "openai"}
    assert "# Keep existing local settings" in env_path.read_text(encoding="utf-8")
    captured = capsys.readouterr()
    assert captured.out == "AI enabled. Restart backend to use it.\n"
    assert captured.err == ""
    assert SECRET not in captured.out + captured.err
    assert not list(tmp_path.rglob("*.db"))


def test_creates_environment_file_when_missing(tmp_path, capsys):
    env_path = tmp_path / ".env"

    assert setup.configure_ai(env_path, input_secret=lambda _: SECRET) == 0

    assert dotenv_values(env_path) == {"OPENAI_API_KEY": SECRET, "AI_MODE": "openai"}
    assert SECRET not in str(capsys.readouterr())


@pytest.mark.parametrize("already_exists", [True, False])
@pytest.mark.parametrize(
    "invalid_key",
    ["", " \t ", "too-short", "  " + "x" * 19 + "  ", SECRET + "\n", SECRET + "\r", SECRET + "\nAI_MODE=demo"],
)
def test_invalid_input_never_changes_or_creates_file(
    tmp_path, capsys, already_exists, invalid_key
):
    env_path = tmp_path / ".env"
    if already_exists:
        env_path.write_text(EXISTING_ENV, encoding="utf-8")
    original = env_path.read_bytes() if already_exists else None

    assert setup.configure_ai(env_path, input_secret=lambda _: invalid_key) != 0

    assert (env_path.read_bytes() if env_path.exists() else None) == original
    captured = capsys.readouterr()
    assert captured.out == ""
    assert SECRET not in captured.out + captured.err
    assert "previous-test-secret" not in captured.out + captured.err


@pytest.mark.parametrize("already_exists", [True, False])
@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt])
def test_interrupted_input_cancels_without_writing(
    tmp_path, capsys, already_exists, interruption
):
    env_path = tmp_path / ".env"
    if already_exists:
        env_path.write_text(EXISTING_ENV, encoding="utf-8")
    original = env_path.read_bytes() if already_exists else None

    def interrupted_input(_):
        raise interruption

    assert setup.configure_ai(env_path, input_secret=interrupted_input) != 0

    assert (env_path.read_bytes() if env_path.exists() else None) == original
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "AI setup cancelled.\n"


def test_refuses_getpass_echo_fallback(tmp_path, capsys):
    env_path = tmp_path / ".env"

    def unavailable_hidden_input(_):
        warnings.warn("No terminal available", getpass.GetPassWarning)
        pytest.fail("Visible-input fallback must never run")

    assert setup.configure_ai(env_path, input_secret=unavailable_hidden_input) != 0

    assert not env_path.exists()
    assert "hidden input" in capsys.readouterr().err


def test_default_target_is_beside_helper_independent_of_cwd(tmp_path, monkeypatch):
    assert setup.DEFAULT_ENV_PATH == Path(setup.__file__).resolve().parent / ".env"
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    env_path = backend_dir / ".env"
    monkeypatch.setattr(setup, "DEFAULT_ENV_PATH", env_path)
    monkeypatch.chdir(other_dir)
    monkeypatch.setattr(getpass, "getpass", lambda _: SECRET)

    assert setup.configure_ai() == 0

    assert dotenv_values(env_path)["OPENAI_API_KEY"] == SECRET
    assert not (other_dir / ".env").exists()


def test_import_does_not_prompt_or_write(tmp_path, monkeypatch, capsys):
    def unexpected_prompt(_):
        pytest.fail("Import must not prompt for a key")

    monkeypatch.setattr(getpass, "getpass", unexpected_prompt)
    monkeypatch.chdir(tmp_path)

    runpy.run_path(setup.__file__, run_name="configure_ai_import_check")

    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr() == ("", "")
