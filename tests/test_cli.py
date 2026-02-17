import pytest

from paperweight.main import main


def test_init_writes_minimal_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["init"])
    assert exit_code == 0
    config_path = tmp_path / "config.yaml"
    assert config_path.exists()
    assert "arxiv:" in config_path.read_text(encoding="utf-8")


def test_init_does_not_overwrite_without_force(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text("existing: true\n", encoding="utf-8")

    exit_code = main(["init"])
    assert exit_code == 1
    stderr = capsys.readouterr().err
    assert "already exists" in stderr
    assert "paperweight init:" in stderr


def test_version_flag():
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0


def test_import_public_api():
    import paperweight

    assert hasattr(paperweight, "__version__")
    assert isinstance(paperweight.__version__, str)
    assert paperweight.__version__ != ""
    assert callable(paperweight.load_config)
    assert callable(paperweight.score_papers)
    assert callable(paperweight.get_recent_papers)
    assert callable(paperweight.setup_and_get_papers)
    assert callable(paperweight.process_and_summarize_papers)
    assert callable(paperweight.summarize_scored_papers)


def test_doctor_reports_missing_config(tmp_path):
    missing = tmp_path / "missing.yaml"
    exit_code = main(["doctor", "--config", str(missing)])
    assert exit_code == 1


def test_doctor_success_with_loaded_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("placeholder: true\n", encoding="utf-8")

    monkeypatch.setattr(
        "paperweight.main.load_config",
        lambda config_path, profile=None: {
            "arxiv": {"categories": ["cs.AI"]},
            "processor": {"keywords": ["agents"]},
            "analyzer": {"type": "abstract"},
            "triage": {"enabled": False},
            "logging": {"level": "INFO"},
        },
    )

    exit_code = main(["doctor", "--config", str(config_path)])
    assert exit_code == 0


def test_doctor_strict_fails_on_warning(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("placeholder: true\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    monkeypatch.setattr(
        "paperweight.main.load_config",
        lambda config_path, profile=None: {
            "arxiv": {"categories": ["cs.AI"]},
            "processor": {"keywords": ["agents"]},
            "analyzer": {"type": "abstract", "llm_provider": "openai"},
            "triage": {"enabled": True, "llm_provider": "openai"},
            "logging": {"level": "INFO"},
        },
    )

    exit_code = main(["doctor", "--config", str(config_path), "--strict"])
    assert exit_code == 1


def test_doctor_passes_profile_to_config_loader(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("placeholder: true\n", encoding="utf-8")

    observed = {}

    def fake_load(config_path, profile=None):
        observed["profile"] = profile
        return {
            "arxiv": {"categories": ["cs.AI"]},
            "processor": {"keywords": ["agents"]},
            "analyzer": {"type": "abstract"},
            "triage": {"enabled": False},
            "logging": {"level": "INFO"},
            "active_profile": profile,
        }

    monkeypatch.setattr("paperweight.main.load_config", fake_load)

    exit_code = main(["doctor", "--config", str(config_path), "--profile", "fast"])
    assert exit_code == 0
    assert observed["profile"] == "fast"
