# NSE Research Platform - File Structure

```
nse-research-platform/
│
├── app/
│   ├── ingestion/
│   ├── indicators/
│   ├── scoring/
│   ├── backtest/
│   ├── sectors/
│   ├── reporting/
│   └── utils/
│
├── db/
│   ├── base.py
│   ├── connection.py
│   ├── models.py
│   └── session.py
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── migrations/
│
├── sql/
│
├── docs/
│   ├── BACKTEST_SPEC.md
│   ├── CODEX_WORKING_RULES.md
│   ├── DB_SCHEMA.md
│   ├── DESIGN_SYSTEM.md
│   ├── FEATURE_REGISTRY.yaml
│   ├── FILE_STRUCTURE.md
│   ├── INDICATOR_SPEC.md
│   ├── MASTER_PRD.md
│   ├── SCORING_ENGINE_SPEC.md
│   ├── SECTOR_ROTATION_SPEC.md
│   └── V1_SCOPE.md
│
├── tests/
│
├── configs/
│   └── config.yaml
│
├── streamlit_app/
│
├── requirements.txt
└── README.md
```

## Notes

- `configs/config.yaml` is the canonical runtime configuration file.
- `app/` is the Python package root for V1 implementation work.
- Empty directories are intentionally present so the structure exists before implementation.
