from pathlib import Path

from app.utils.config import AppConfig, load_config
from app.utils.container import Container
from app.utils.logging import build_logger, configure_root_logging


def test_load_config_reads_canonical_config():
    repo_root = Path(__file__).resolve().parents[1]
    config = load_config(repo_root / "configs" / "config.yaml")

    assert isinstance(config, AppConfig)
    assert config.path.name == "config.yaml"
    assert config.raw["capital"] == 1_000_000
    assert config.raw["ranking"]["entry_top_n"] == 10


def test_build_logger_returns_named_logger():
    logger = build_logger("nse_research_platform.tests")

    assert logger.name == "nse_research_platform.tests"
    assert logger.propagate is False
    assert logger.handlers


def test_configure_root_logging_uses_platform_name():
    logger = configure_root_logging("INFO")

    assert logger.name == "nse_research_platform"


def test_container_register_resolve_and_has():
    container = Container()
    container.register("answer", lambda: 42)

    assert container.has("answer") is True
    assert container.resolve("answer") == 42
