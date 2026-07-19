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


def test_scenario_b_sources_uses_and_declining_balance(client) -> None:
    result = client.post("/api/underwriting/calculate", json={"scenario": "B"}).json()
    assert result["scenario"] == "B"
    assert result["acquisition"]["loan_amount"] == 375000
    assert result["financing"]["annual_debt_service"] > 0
    balances = [year["loan_balance"] for year in result["projection"]["years"]]
    assert all(next_balance < balance for balance, next_balance in zip(balances, balances[1:]))


def test_zero_revenue_affordability_statuses(client) -> None:
    review = client.post("/api/underwriting/calculate", json={}).json()
    assert review["zero_revenue_affordability"]["status"] == "NEEDS_REVIEW"
    required = review["zero_revenue_affordability"]["monthly_owner_cash_requirement"]
    assert client.post("/api/underwriting/calculate", json={"zero_revenue_monthly_affordability_ceiling": required}).json()["zero_revenue_affordability"]["status"] == "PASS"
    assert client.post("/api/underwriting/calculate", json={"zero_revenue_monthly_affordability_ceiling": required - 1}).json()["zero_revenue_affordability"]["status"] == "FAIL"


def test_renovation_variance_and_unverified_comparables(client) -> None:
    result = client.post("/api/underwriting/calculate", json={"renovation_budget": 150000}).json()
    renovation = result["renovation"]
    assert renovation["underwriting_renovation_budget"] == 150000
    assert (renovation["low_total"], renovation["detailed_base_total"], renovation["high_total"], renovation["variance"]) == (92000, 170000, 395000, 20000)
    assert all(comp["sample"] and not comp["verified"] for comp in result["comparables"]["short_term_rental"])
