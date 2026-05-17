import json

from app.conf.config_loader import _load_config
from app.conf.config_model import Settings


def test_defaults_without_config_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cfg = _load_config()
    assert cfg.DATABASE_URL == "sqlite+aiosqlite:///./data.db"
    assert cfg.PORT == 8080
    assert cfg.GITLAB_BASE_URL == "https://gitlab.com"


def test_loads_from_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config_data = {
        "GITLAB_BASE_URL": "https://my.gitlab.example",
        "REPORTS_DIR": "/tmp/reports",
    }
    (tmp_path / "config.json").write_text(json.dumps(config_data))
    cfg = _load_config()
    assert cfg.GITLAB_BASE_URL == "https://my.gitlab.example"
    assert cfg.REPORTS_DIR == "/tmp/reports"


def test_env_var_overrides_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"GITLAB_BASE_URL": "https://from-json"}))
    monkeypatch.setenv("QA_PIPE_GITLAB_BASE_URL", "https://from-env")
    cfg = _load_config()
    assert cfg.GITLAB_BASE_URL == "https://from-env"


def test_settings_model_has_no_token_fields():
    cfg = Settings()
    assert not hasattr(cfg, "GITLAB_TOKEN")
    assert not hasattr(cfg, "GITLAB_PROJECT_ID")
    assert not hasattr(cfg, "GITLAB_VERIFY_SSL")
