import tomllib
from pathlib import Path

from pydantic import BaseModel


class HardcoverConfig(BaseModel):
    api_token: str


class KoboConfig(BaseModel):
    mount_path: str = "/Volumes/KOBOeReader"


class Config(BaseModel):
    hardcover: HardcoverConfig
    kobo: KoboConfig = KoboConfig()

    @property
    def kobo_db_path(self) -> Path:
        return Path(self.kobo.mount_path) / ".kobo" / "KoboReader.sqlite"


def load_config(config_path: Path) -> Config:
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    return Config.model_validate(data)


def default_config_path() -> Path:
    return Path.home() / ".config" / "kobosync" / "config.toml"
