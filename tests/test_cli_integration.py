"""Small high-value CLI integration workflows.

These tests run through the CLI entrypoint with real config loading while
stubbing network-heavy scraper boundaries.
"""

from datetime import date

import yaml

from paperweight.main import main


def _write_config(tmp_path, *, triage_enabled=False):
    config = {
        "arxiv": {"categories": ["cs.AI"], "max_results": 5},
        "triage": {
            "enabled": triage_enabled,
            "llm_provider": "openai",
            "min_score": 60,
            "max_selected": 5,
        },
        "processor": {
            "keywords": ["transformer", "agent"],
            "exclusion_keywords": [],
            "important_words": [],
            "title_keyword_weight": 3,
            "abstract_keyword_weight": 2,
            "content_keyword_weight": 1,
            "exclusion_keyword_penalty": 5,
            "important_words_weight": 0.5,
            "min_score": 0,
        },
        "analyzer": {"type": "abstract"},
        "logging": {"level": "INFO", "file": str(tmp_path / "paperweight.log")},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path


def _stub_scraper(monkeypatch):
    fake_papers = [
        {
            "title": "Transformer Agents",
            "link": "http://arxiv.org/abs/2401.12345",
            "date": date(2024, 1, 15),
            "abstract": "A paper about transformer-based agents.",
        }
    ]

    monkeypatch.setattr(
        "paperweight.scraper.fetch_recent_papers", lambda _config, _days: fake_papers
    )
    monkeypatch.setattr(
        "paperweight.scraper.fetch_paper_contents",
        lambda _ids: [("2401.12345", b"stub-bytes", "pdf")],
    )
    monkeypatch.setattr(
        "paperweight.scraper.extract_text_from_source", lambda _c, _m: "transformer agent"
    )
    monkeypatch.setattr("paperweight.scraper.get_last_processed_date", lambda: None)
    monkeypatch.setattr("paperweight.scraper.save_last_processed_date", lambda _d: None)


def _stub_scraper_two_papers(monkeypatch):
    fake_papers = [
        {
            "title": "Transformer Agents",
            "link": "http://arxiv.org/abs/2401.12345",
            "date": date(2024, 1, 15),
            "abstract": "A paper about transformer-based agents.",
        },
        {
            "title": "Reasoning Models",
            "link": "http://arxiv.org/abs/2401.67890",
            "date": date(2024, 1, 14),
            "abstract": "A paper about reasoning models.",
        },
    ]
    monkeypatch.setattr(
        "paperweight.scraper.fetch_recent_papers", lambda _config, _days: fake_papers
    )
    monkeypatch.setattr(
        "paperweight.scraper.fetch_paper_contents",
        lambda _ids: [
            ("2401.12345", b"stub-bytes", "pdf"),
            ("2401.67890", b"stub-bytes", "pdf"),
        ],
    )
    monkeypatch.setattr(
        "paperweight.scraper.extract_text_from_source", lambda _c, _m: "transformer agent"
    )
    monkeypatch.setattr("paperweight.scraper.get_last_processed_date", lambda: None)
    monkeypatch.setattr("paperweight.scraper.save_last_processed_date", lambda _d: None)


def test_run_stdout_mode_smoke(tmp_path, monkeypatch, capsys):
    config_path = _write_config(tmp_path, triage_enabled=False)
    _stub_scraper(monkeypatch)

    exit_code = main(["run", "--config", str(config_path), "--force-refresh"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "paperweight digest" in out
    assert "Transformer Agents" in out
    assert "http://arxiv.org/abs/2401.12345" in out


def test_run_atom_output_smoke(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, triage_enabled=False)
    atom_path = tmp_path / "digest.xml"
    _stub_scraper(monkeypatch)

    exit_code = main(
        [
            "run",
            "--config",
            str(config_path),
            "--force-refresh",
            "--delivery",
            "atom",
            "--output",
            str(atom_path),
        ]
    )

    assert exit_code == 0
    assert atom_path.exists()
    xml = atom_path.read_text(encoding="utf-8")
    assert "<feed" in xml
    assert "Transformer Agents" in xml


def test_doctor_warns_without_api_key(tmp_path, capsys, monkeypatch):
    config_path = _write_config(tmp_path, triage_enabled=True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("paperweight.utils.load_dotenv", lambda *_a, **_k: None)
    exit_code = main(["doctor", "--config", str(config_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "[WARN] triage auth" in out


def test_run_json_respects_max_items(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, triage_enabled=False)
    json_path = tmp_path / "digest.json"
    _stub_scraper_two_papers(monkeypatch)

    exit_code = main(
        [
            "run",
            "--config",
            str(config_path),
            "--force-refresh",
            "--delivery",
            "json",
            "--output",
            str(json_path),
            "--max-items",
            "1",
        ]
    )
    assert exit_code == 0
    payload = json_path.read_text(encoding="utf-8")
    assert payload.count('"title"') == 1


def test_run_max_items_caps_processing_before_hydration(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path, triage_enabled=False)
    _stub_scraper_two_papers(monkeypatch)

    observed = {"hydrated_count": 0}

    def fake_hydrate(papers, _config):
        observed["hydrated_count"] = len(papers)
        hydrated = []
        for paper in papers:
            paper_id = paper["link"].split("/abs/")[-1]
            hydrated.append(
                {
                    **paper,
                    "id": paper_id,
                    "content": "transformer agent",
                    "content_type": "pdf",
                    "artifacts": [],
                }
            )
        return hydrated

    monkeypatch.setattr("paperweight.main.hydrate_papers_with_content", fake_hydrate)

    exit_code = main(
        [
            "run",
            "--config",
            str(config_path),
            "--force-refresh",
            "--delivery",
            "stdout",
            "--max-items",
            "1",
        ]
    )

    assert exit_code == 0
    assert observed["hydrated_count"] == 1
