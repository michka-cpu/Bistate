from pytest import approx


def test_default_underwriting_matches_primary_workbook_regression(client) -> None:
    response = client.post("/api/underwriting/calculate", json={})
    assert response.status_code == 200
    result = response.json()
    assert result["acquisition"]["total_project_cost"] == 818000
    assert result["acquisition"]["total_cash_required"] == 418000
    assert result["revenue"]["gross_lodging_revenue"] == 57500
    assert result["revenue"]["gross_wedding_event_revenue"] == 213000
    assert result["operating_costs"]["total_operating_expenses"] == approx(101166.66666666667)
    assert result["financing"]["annual_debt_service"] == approx(31132.708635274335)
    assert result["dashboard"]["noi_before_debt"] == approx(111833.33333333333)
    assert result["dashboard"]["after_tax_cash_flow"] == approx(153448.58483464245)


def test_underwriting_recalculates_from_overrides(client) -> None:
    response = client.post("/api/underwriting/calculate", json={"occupancy": 0.6, "nightly_rate": 500})
    assert response.status_code == 200
    result = response.json()
    assert result["revenue"]["occupied_lodging_days"] == 138
    assert result["revenue"]["nightly_lodging_revenue"] == 69000
