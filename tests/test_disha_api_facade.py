from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app, get_disha_service


class FakeDishaService:
    def health(self):
        return {"status": "ok", "artifacts": {"locked_rules": {"exists": True}}}

    def readiness(self):
        return {"status": "ok", "paper": {"ready": True}, "scanner": {"latest_rows": 0}}

    def locked_rules(self):
        return {"portfolio": {"name": "Disha Mean Reversion Setup"}}

    def backtest_summary(self):
        return {"portfolio": {"cagr": "12.32%"}, "sleeves": {"v4b_mean_reversion": {"allocation": "15%"}}}

    def market_regime(self):
        return {"latest": {"regime_label": "UPTREND"}, "total_sessions": 100}

    def signals_today(self):
        return {"count": 1, "signals": [{"symbol": "LTIM", "v4b_entry_signal": True}]}

    def portfolio_summary(self):
        return {"summary": {"open_positions": 0, "equity_estimate": 1000000.0}}

    def paper_status(self):
        return {"ready": True, "sessions_logged": 1}

    def paper_logs(self, limit: int = 50):
        return {"limit": limit, "logs": {"paper_trade_log": [{"session": 1}]}}


def client():
    app.dependency_overrides[get_disha_service] = lambda: FakeDishaService()
    return TestClient(app)


def test_disha_health_endpoint():
    response = client().get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_disha_readiness_endpoint():
    response = client().get("/api/readiness")

    assert response.status_code == 200
    assert response.json()["paper"]["ready"] is True


def test_locked_rules_endpoint():
    response = client().get("/api/rules/locked")

    assert response.status_code == 200
    assert response.json()["portfolio"]["name"] == "Disha Mean Reversion Setup"


def test_backtest_summary_endpoint():
    response = client().get("/api/backtest/summary")

    assert response.status_code == 200
    assert response.json()["portfolio"]["cagr"] == "12.32%"


def test_market_regime_endpoint():
    response = client().get("/api/market/regime")

    assert response.status_code == 200
    assert response.json()["latest"]["regime_label"] == "UPTREND"


def test_signals_today_endpoint():
    response = client().get("/api/signals/today")

    assert response.status_code == 200
    assert response.json()["signals"][0]["symbol"] == "LTIM"


def test_portfolio_summary_endpoint():
    response = client().get("/api/portfolio/summary")

    assert response.status_code == 200
    assert response.json()["summary"]["open_positions"] == 0


def test_paper_status_endpoint():
    response = client().get("/api/paper/status")

    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_paper_logs_endpoint_accepts_limit():
    response = client().get("/api/paper/logs?limit=10")

    assert response.status_code == 200
    assert response.json()["limit"] == 10
