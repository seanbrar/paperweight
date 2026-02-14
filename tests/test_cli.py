import pytest

from paperweight.main import main


def test_init_writes_minimal_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["init"])
    assert exit_code == 0
    config_path = tmp_path / "config.yaml"
    assert config_path.exists()
    assert "arxiv:" in config_path.read_text(encoding="utf-8")


def test_init_does_not_overwrite_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text("existing: true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        main(["init"])


def test_doctor_reports_missing_config(tmp_path):
    missing = tmp_path / "missing.yaml"
    exit_code = main(["doctor", "--config", str(missing)])
    assert exit_code == 1


def test_doctor_success_with_loaded_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("placeholder: true\n", encoding="utf-8")

    monkeypatch.setattr(
        "paperweight.main.load_config",
        lambda config_path: {
            "arxiv": {"categories": ["cs.AI"]},
            "processor": {"keywords": ["agents"]},
            "analyzer": {"type": "abstract"},
            "triage": {"enabled": False},
            "logging": {"level": "INFO"},
        },
    )

    exit_code = main(["doctor", "--config", str(config_path)])
    assert exit_code == 0
