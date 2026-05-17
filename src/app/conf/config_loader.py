import json
import os
from pathlib import Path

from app.conf.config_model import Settings


def _load_config() -> Settings:
    config_path = Path("config.json")
    data: dict = {}
    if config_path.exists():
        with config_path.open() as f:
            data = json.load(f)
    env_prefix = "QA_PIPE_"
    for key in list(Settings.model_fields):
        env_key = env_prefix + key
        if env_key in os.environ:
            data[key] = os.environ[env_key]
    return Settings(**data)
