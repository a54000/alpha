"""Build a dependency-light static HTML paper-trading dashboard."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "results" / "sprint_2_8"
SPRINT_27 = ROOT / "results" / "sprint_2_7"
OUT = PAPER / "paper_dashboard.html"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _pct(value) -> str:
    try:
        return f"{float(value):.2%}"
    except Exception:
        return "-"


def _table(frame: pd.DataFrame, max_rows: int = 10) -> str:
    if frame.empty:
        return '<div class="empty">No rows yet</div>'
    frame = frame.tail(max_rows).fillna("")
    headers = "".join(f"<th>{html.escape(str(col))}</th>" for col in frame.columns)
    rows = []
    for _, row in frame.iterrows():
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
        rows.append(f"<tr>{cells}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _metric(label: str, value: str, detail: str = "") -> str:
    return f'<div class="metric"><div class="label">{html.escape(label)}</div><div class="value">{html.escape(value)}</div><div class="detail">{html.escape(detail)}</div></div>'


def main() -> None:
    PAPER.mkdir(parents=True, exist_ok=True)
    status = _read_json(PAPER / "paper_trading_status.json")
    scanner = _read_json(PAPER / "day0_scanner_dry_run_summary.json")
    tax = _read_json(SPRINT_27 / "tax_adjusted_yield.json")
    market = scanner.get("market") or {}
    metrics = [
        _metric("Readiness", "Ready" if status.get("ready") else "Check", f"Missing {len(status.get('missing_files', []))}"),
        _metric("Sessions", str(status.get("sessions_logged", 0)), "30-session paper test"),
        _metric("Production CAGR", _pct(tax.get("production_cagr_est")), "4.81% net idle yield"),
        _metric("Max DD", _pct(tax.get("max_drawdown_at_rate")), "production estimate"),
        _metric("Scanner Date", str(scanner.get("scan_date", "-")), f"{scanner.get('symbols_scanned', 0)} symbols"),
        _metric("Signals", f"V4b {scanner.get('v4b_signals', 0)} | VCP {scanner.get('vcp_signals', 0)}", str(market.get("regime_label", "-"))),
    ]
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Disha Paper Trading Dashboard</title>
  <style>
    body {{ margin:0; background:#f4f6f7; color:#17212b; font-family:Segoe UI, Arial, sans-serif; }}
    .page {{ max-width:1480px; margin:0 auto; padding:24px; }}
    .top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:16px; }}
    h1 {{ margin:0; font-size:28px; letter-spacing:0; }}
    h2 {{ margin:0 0 12px; font-size:16px; letter-spacing:0; }}
    p {{ color:#5f6f7d; margin:6px 0 0; }}
    .stamp {{ color:#60717f; font-size:13px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:12px; margin-bottom:12px; }}
    .metric,.panel {{ background:#fff; border:1px solid #dce3e8; border-radius:8px; box-shadow:0 1px 2px rgba(20,31,42,.04); }}
    .metric {{ padding:14px; min-height:76px; }}
    .label {{ color:#647482; font-size:12px; font-weight:700; text-transform:uppercase; }}
    .value {{ margin-top:8px; font-size:22px; font-weight:750; }}
    .detail {{ margin-top:4px; color:#6d7b86; font-size:12px; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .panel {{ padding:14px; min-width:0; }}
    .wide {{ grid-column:1 / -1; }}
    .facts {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }}
    .facts span {{ background:#eef5f2; border:1px solid #cfe1d9; color:#1f5b4c; border-radius:6px; padding:6px 8px; font-size:12px; font-weight:700; }}
    .table-wrap {{ overflow-x:auto; }}
    table {{ border-collapse:collapse; width:100%; font-size:12px; }}
    th,td {{ padding:8px; border-bottom:1px solid #e6ebef; text-align:left; white-space:nowrap; }}
    th {{ background:#eef2f6; font-weight:700; }}
    tr:nth-child(even) td {{ background:#fafbfc; }}
    .empty {{ color:#657482; padding:12px; background:#fafbfc; border-radius:6px; }}
    ul {{ margin:0; padding-left:18px; line-height:1.6; }}
    @media(max-width:1100px) {{ .metrics {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} .grid {{ grid-template-columns:1fr; }} }}
    @media(max-width:700px) {{ .page {{ padding:14px; }} .metrics {{ grid-template-columns:1fr 1fr; }} .top {{ flex-direction:column; }} }}
  </style>
</head>
<body>
<main class="page">
  <div class="top">
    <div><h1>Disha Paper Trading</h1><p>Operational dashboard for V4b + VCP + idle-yield paper trading.</p></div>
    <div class="stamp">Generated from local artifacts</div>
  </div>
  <section class="metrics">{''.join(metrics)}</section>
  <section class="grid">
    <div class="panel">
      <h2>Caveats</h2>
      <ul>
        <li>09:15 bid-ask spread validation needs live order-book data.</li>
        <li>AMFI NAV source selected; daily NAV workflow needs manual confirmation.</li>
        <li>MF redemption/sweep workflow needs 20-session paper validation.</li>
      </ul>
    </div>
    <div class="panel">
      <h2>Latest Scanner</h2>
      <div class="facts">
        <span>Regime: {html.escape(str(market.get('regime_label', '-')))}</span>
        <span>VCP gate: {html.escape(str(market.get('vcp_market_gate', '-')))}</span>
        <span>NIFTY 60D: {_pct(market.get('nifty_return_60d'))}</span>
      </div>
      {_table(_read_csv(PAPER / 'day0_scanner_dry_run_signals.csv'))}
    </div>
    <div class="panel wide"><h2>Order Sheet</h2>{_table(_read_csv(PAPER / 'day1_order_sheet.csv'))}</div>
    <div class="panel wide"><h2>MF Sweep</h2>{_table(_read_csv(PAPER / 'mf_sweep_log.csv'))}</div>
    <div class="panel wide"><h2>Fill Quality</h2>{_table(_read_csv(PAPER / 'fill_quality_log.csv'))}</div>
    <div class="panel wide"><h2>Positions</h2>{_table(_read_csv(PAPER / 'position_ledger.csv'))}</div>
  </section>
</main>
</body>
</html>"""
    OUT.write_text(html_text, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()

