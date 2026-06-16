from pathlib import Path


def test_phase_0_repository_structure():
    repo_root = Path(__file__).resolve().parents[1]

    expected_directories = [
        repo_root / "app" / "ingestion",
        repo_root / "app" / "indicators",
        repo_root / "app" / "scoring",
        repo_root / "app" / "backtest",
        repo_root / "app" / "sectors",
        repo_root / "app" / "reporting",
        repo_root / "app" / "utils",
        repo_root / "sql",
        repo_root / "docs",
        repo_root / "tests",
        repo_root / "configs",
        repo_root / "streamlit_app",
    ]

    for directory in expected_directories:
        assert directory.is_dir(), f"missing directory: {directory.relative_to(repo_root)}"

    expected_files = [
        repo_root / "configs" / "config.yaml",
        repo_root / "README.md",
        repo_root / "requirements.txt",
    ]

    for file_path in expected_files:
        assert file_path.is_file(), f"missing file: {file_path.relative_to(repo_root)}"
