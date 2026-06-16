from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app, get_rolling_portfolio_service, get_service


class FakeCockpitService:
    def dashboard(self):
        return {"read_only": True, "portfolio": {"nav": 100}}

    def latest_recommendations(self, model: str = "swing_v2_1", limit: int = 20):
        return {"model": model, "limit": limit, "recommendations": [{"rank": 1, "symbol": "ABC", "score": 90}]}

    def recommendation_explanation(self, symbol: str, recommendation_type: str = "swing_v2_1", business_date=None):
        return {
            "symbol": symbol,
            "recommendation_type": recommendation_type,
            "business_date": str(business_date) if business_date else None,
            "feature_snapshot": {"adx_14": 25, "final_score": 90},
        }

    def portfolio(self, portfolio_id: int | None = None):
        return {"summary": {"portfolio_id": portfolio_id or 1}, "positions": [], "trades": []}

    def portfolio_attribution(self, portfolio_id: int | None = None):
        return {"portfolio_id": portfolio_id or 1, "position_contribution": [{"symbol": "ABC"}]}

    def trades(self, portfolio_id: int | None = None, limit: int = 100):
        return {"trades": [{"trade_id": 1, "portfolio_id": portfolio_id or 1}], "limit": limit}

    def pipeline_status(self):
        return {"summary": {"status": "success"}, "steps": []}

    def research_metrics(self):
        return {"summary": {"phase2e_available": True}}

    def health(self):
        return {
            "status": "ok",
            "research_db": {"connected": True},
            "angel_db": {"connected": True},
            "paper_portfolio": {"configured": True, "exists": True},
        }


class FakeRollingPortfolioService:
    def defaults(self, recommendation_model: str = "swing_v2_1"):
        return {
            "default_start_date": "2022-05-26",
            "earliest_recommendation_date": "2022-05-26",
            "latest_recommendation_date": "2026-06-12",
            "recommendation_dates": 954,
            "recommendation_rows": 7978,
            "recommendation_model": recommendation_model,
            "source": "pilot_phase2a.recommendations_daily",
        }

    def simulate(self, request):
        return {
            "status": "completed",
            "parameters": {
                "requested_start_date": request.start_date.isoformat(),
                "weeks": request.weeks,
                "initial_capital": request.initial_capital,
                "recommendation_model": request.recommendation_model,
            },
            "summary": {
                "portfolio_size": 10,
                "max_candidate_rank": 5,
                "open_positions": 5,
                "cash": 500000,
                "equity": 1000000,
                "mark_date": "2026-06-12",
                "recommendation_model": request.recommendation_model,
            },
            "weekly_log": [{"week_number": 1, "recommendations": [{"symbol": "ABC", "rank": 1}]}],
            "positions": [{"symbol": "ABC"}],
            "trades": [],
            "financial_year_returns": [{"financial_year": "FY2022-23", "return_pct": 0.10}],
        }


def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///research-test.db")
    monkeypatch.setenv("ANGEL_DATABASE_URL", "sqlite:///angel-test.db")
    monkeypatch.setenv("PAPER_PORTFOLIO_ID", "1")
    app.dependency_overrides[get_service] = lambda: FakeCockpitService()
    return TestClient(app)


def test_dashboard_endpoint_is_read_only_summary(monkeypatch):
    response = client(monkeypatch).get("/dashboard")

    assert response.status_code == 200
    assert response.json()["read_only"] is True


def test_recommendations_latest_endpoint_accepts_model_and_limit(monkeypatch):
    response = client(monkeypatch).get("/recommendations/latest?model=swing_v2_1&limit=5")

    payload = response.json()
    assert response.status_code == 200
    assert payload["model"] == "swing_v2_1"
    assert payload["limit"] == 5
    assert payload["recommendations"][0]["symbol"] == "ABC"


def test_recommendation_explanation_endpoint(monkeypatch):
    response = client(monkeypatch).get("/recommendations/ABC/explanation?recommendation_type=swing_v2_1")

    payload = response.json()
    assert response.status_code == 200
    assert payload["symbol"] == "ABC"
    assert payload["feature_snapshot"]["final_score"] == 90


def test_portfolio_endpoint(monkeypatch):
    response = client(monkeypatch).get("/portfolio?portfolio_id=7")

    assert response.status_code == 200
    assert response.json()["summary"]["portfolio_id"] == 7


def test_portfolio_attribution_endpoint(monkeypatch):
    response = client(monkeypatch).get("/portfolio/attribution?portfolio_id=7")

    assert response.status_code == 200
    assert response.json()["portfolio_id"] == 7
    assert response.json()["position_contribution"][0]["symbol"] == "ABC"


def test_trades_endpoint(monkeypatch):
    response = client(monkeypatch).get("/trades?portfolio_id=7&limit=10")

    assert response.status_code == 200
    assert response.json()["trades"][0]["portfolio_id"] == 7


def test_pipeline_status_endpoint(monkeypatch):
    response = client(monkeypatch).get("/pipeline/status")

    assert response.status_code == 200
    assert response.json()["summary"]["status"] == "success"


def test_research_metrics_endpoint(monkeypatch):
    response = client(monkeypatch).get("/research/metrics")

    assert response.status_code == 200
    assert response.json()["summary"]["phase2e_available"] is True


def test_rolling_portfolio_simulation_endpoint(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///research-test.db")
    monkeypatch.setenv("ANGEL_DATABASE_URL", "sqlite:///angel-test.db")
    monkeypatch.setenv("PAPER_PORTFOLIO_ID", "1")
    app.dependency_overrides[get_rolling_portfolio_service] = lambda: FakeRollingPortfolioService()
    test_client = TestClient(app)

    response = test_client.post(
        "/research/rolling-portfolio/simulate",
        json={"start_date": "2026-05-04", "weeks": 2, "initial_capital": 1000000},
    )

    assert response.status_code == 200
    assert response.json()["summary"]["portfolio_size"] == 10
    assert response.json()["summary"]["max_candidate_rank"] == 5
    assert response.json()["parameters"]["weeks"] == 2

    app.dependency_overrides.pop(get_rolling_portfolio_service, None)


def test_rolling_portfolio_defaults_endpoint(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///research-test.db")
    monkeypatch.setenv("ANGEL_DATABASE_URL", "sqlite:///angel-test.db")
    monkeypatch.setenv("PAPER_PORTFOLIO_ID", "1")
    app.dependency_overrides[get_rolling_portfolio_service] = lambda: FakeRollingPortfolioService()
    test_client = TestClient(app)

    response = test_client.get("/research/rolling-portfolio/defaults")

    assert response.status_code == 200
    assert response.json()["default_start_date"] == "2022-05-26"
    assert response.json()["source"] == "pilot_phase2a.recommendations_daily"

    app.dependency_overrides.pop(get_rolling_portfolio_service, None)


def test_health_endpoint(monkeypatch):
    response = client(monkeypatch).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
