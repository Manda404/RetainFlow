from retainflow.data.bootstrap import (
    PostgresBootstrapConfig,
    PostgresBootstrapper,
    load_postgres_bootstrap_config,
)
from retainflow.logging import PROJECT_ROOT


def test_load_postgres_bootstrap_config() -> None:
    config = load_postgres_bootstrap_config("config/data_pipeline.yml")

    assert isinstance(config, PostgresBootstrapConfig)
    assert config.n_customers == 10000
    assert config.seed == 42
    assert config.reset_database is True
    assert config.csv_dir == PROJECT_ROOT / "data/raw/retainflow_csv"
    assert config.dsn == "postgresql://retainflow:retainflow@localhost:55432/retainflow"
    assert config.schema_name == "retainflow"
    assert config.docker_service_name == "postgres"


def test_load_postgres_bootstrap_config_uses_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("RETAINFLOW_N_CUSTOMERS", "250")
    monkeypatch.setenv("RETAINFLOW_SEED", "123")
    monkeypatch.setenv("RETAINFLOW_CSV_DIR", "/tmp/retainflow_custom_csv")
    monkeypatch.setenv("RETAINFLOW_POSTGRES_DSN", "postgresql://user:pass@localhost:5433/db")

    config = load_postgres_bootstrap_config("config/data_pipeline.yml")

    assert config.n_customers == 250
    assert config.seed == 123
    assert str(config.csv_dir) == "/tmp/retainflow_custom_csv"
    assert config.dsn == "postgresql://user:pass@localhost:5433/db"


def test_postgres_bootstrapper_keeps_config() -> None:
    config = load_postgres_bootstrap_config("config/data_pipeline.yml")
    bootstrapper = PostgresBootstrapper(config)

    assert bootstrapper.config is config
