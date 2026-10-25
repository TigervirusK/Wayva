"""Local provider setup never needs a secret or changes saved trip settings."""

from pathlib import Path
import runpy

from dotenv import dotenv_values
import pytest

import configure_local_ai as setup


def test_local_setup_preserves_database_cloud_key_comments_and_other_settings(tmp_path, capsys):
    path = tmp_path / ".env"
    path.write_text(
        "# Preserve this comment\nDATABASE_URL=sqlite:///./data/existing.db\n"
        "OPENAI_API_KEY=fictional-do-not-print\nOPENAI_MODEL=custom-model\nOTHER=value\nAI_MODE=openai\n",
        encoding="utf-8",
    )
    original = dotenv_values(path)

    assert setup.configure_local_ai(path) == 0

    assert dotenv_values(path) == {**original, "AI_MODE": "ollama", "OLLAMA_MODEL": "qwen3:4b-q4_K_M",
                                  "OLLAMA_BASE_URL": "http://127.0.0.1:11434"}
    assert "# Preserve this comment" in path.read_text(encoding="utf-8")
    output = capsys.readouterr()
    assert "No API key is needed" in output.out
    assert "fictional-do-not-print" not in output.out + output.err
    assert not list(tmp_path.rglob("*.db"))


def test_local_setup_creates_only_the_env_file_and_uses_selected_model(tmp_path):
    path = tmp_path / ".env"

    assert setup.configure_local_ai(path, model="qwen3:0.6b", base_url="http://localhost:11434/") == 0

    assert dotenv_values(path) == {"AI_MODE": "ollama", "OLLAMA_MODEL": "qwen3:0.6b",
                                  "OLLAMA_BASE_URL": "http://localhost:11434"}
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("model", ["", "   ", "bad model", "bad\nAI_MODE=openai", "x" * 121,
                                  "gpt-oss:120b-cloud", "other:cloud", "model;command"])
def test_invalid_or_cloud_models_do_not_touch_configuration(tmp_path, model):
    path = tmp_path / ".env"
    path.write_text("AI_MODE=demo\n", encoding="utf-8")
    original = path.read_bytes()

    assert setup.configure_local_ai(path, model=model) == 1
    assert path.read_bytes() == original


@pytest.mark.parametrize("base_url", ["https://127.0.0.1:11434", "http://example.com:11434",
    "http://192.168.1.20:11434", "http://user:secret@localhost:11434", "http://localhost:11434/api",
    "http://localhost:11434?x=y", "http://localhost:11434#fragment", "http://localhost:99999"])
def test_remote_or_malformed_server_urls_cannot_create_configuration(tmp_path, base_url):
    path = tmp_path / ".env"

    assert setup.configure_local_ai(path, base_url=base_url) == 1
    assert not path.exists()


def test_setup_default_path_is_beside_script_and_independent_of_cwd(tmp_path, monkeypatch):
    assert setup.DEFAULT_ENV_PATH == Path(setup.__file__).resolve().parent / ".env"
    directory = tmp_path / "backend"
    directory.mkdir()
    path = directory / ".env"
    monkeypatch.setattr(setup, "DEFAULT_ENV_PATH", path)
    monkeypatch.chdir(tmp_path)

    assert setup.configure_local_ai() == 0
    assert path.exists()
    assert not (tmp_path / ".env").exists()


def test_local_setup_handles_file_failure_without_disclosing_other_settings(tmp_path, monkeypatch, capsys):
    def fail(*_args, **_kwargs):
        raise OSError("private file details")
    monkeypatch.setattr(setup, "set_key", fail)

    assert setup.configure_local_ai(tmp_path / ".env") == 1
    assert "private file details" not in str(capsys.readouterr())


def test_import_does_not_write_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    runpy.run_path(setup.__file__, run_name="local_ai_import_check")

    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr() == ("", "")
