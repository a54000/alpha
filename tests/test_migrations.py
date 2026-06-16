from pathlib import Path

from alembic import command
from alembic.config import Config


def make_alembic_config(tmp_path: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    return config


def test_migrations_upgrade_downgrade_upgrade(tmp_path):
    config = make_alembic_config(tmp_path)

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")

