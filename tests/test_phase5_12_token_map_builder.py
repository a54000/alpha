from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def local_tmp_dir(name: str) -> Path:
    path = REPO_ROOT / ".pytest_tmp_phase5_12" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_builder_detects_duplicate_symbols_and_tokens():
    builder = load_script("build_angel_token_map")
    rows = [
        builder.InstrumentRow("ABC", "111", "NSE", "EQ", ""),
        builder.InstrumentRow("ABC", "222", "NSE", "EQ", ""),
        builder.InstrumentRow("XYZ", "111", "NSE", "EQ", ""),
    ]

    report = builder.validate_mapping(rows, pilot_symbols=["ABC", "XYZ"])

    assert report.duplicate_symbols == ["ABC"]
    assert report.duplicate_tokens == ["111"]


def test_builder_detects_missing_pilot_coverage():
    builder = load_script("build_angel_token_map")
    rows = [
        builder.InstrumentRow("ABC", "111", "NSE", "EQ", ""),
    ]

    report = builder.validate_mapping(rows, pilot_symbols=["ABC", "XYZ"])

    assert report.covered_symbols == ["ABC"]
    assert report.missing_symbols == ["XYZ"]
    assert report.extra_symbols == []


def test_builder_writes_token_map_csv():
    builder = load_script("build_angel_token_map")
    output = local_tmp_dir("csv_generation") / "angel_symbol_token_map.csv"
    rows = [
        builder.InstrumentRow("XYZ", "222", "NSE", "EQ", ""),
        builder.InstrumentRow("ABC", "111", "NSE", "EQ", ""),
    ]

    builder.write_token_map(output, rows)

    with output.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))

    assert list(records[0]) == ["symbol", "angel_token", "exchange", "instrument_type", "expiry"]
    assert records[0]["symbol"] == "ABC"
    assert records[0]["angel_token"] == "111"


def test_builder_loads_json_instrument_master_and_normalizes_symbol():
    builder = load_script("build_angel_token_map")
    source = local_tmp_dir("json_master") / "master.json"
    source.write_text(
        """
        [
          {"symbol": "ABC-EQ", "token": "111", "exch_seg": "NSE", "instrumenttype": "EQ"},
          {"symbol": "BANKNIFTY", "token": "999", "exch_seg": "NFO", "instrumenttype": "OPTIDX"}
        ]
        """,
        encoding="utf-8",
    )

    rows = builder.load_instrument_master(source, include_other_exchanges=True)

    assert rows[0].symbol == "ABC"
    assert rows[0].angel_token == "111"
    assert rows[1].exchange == "NFO"


def test_builder_default_filters_other_exchanges():
    builder = load_script("build_angel_token_map")
    source = local_tmp_dir("exchange_filter") / "master.csv"
    source.write_text(
        "symbol,token,exch_seg,instrumenttype\nABC-EQ,111,NSE,EQ\nBANKNIFTY,999,NFO,OPTIDX\n",
        encoding="utf-8",
    )

    rows = builder.load_instrument_master(source)

    assert [row.symbol for row in rows] == ["ABC"]
