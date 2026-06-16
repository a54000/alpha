def test_core_packages_importable():
    import app.backtest
    import app.indicators
    import app.ingestion
    import app.reporting
    import app.scoring
    import app.sectors
    import app.utils

    assert app.backtest is not None
    assert app.indicators is not None
    assert app.ingestion is not None
    assert app.reporting is not None
    assert app.scoring is not None
    assert app.sectors is not None
    assert app.utils is not None
