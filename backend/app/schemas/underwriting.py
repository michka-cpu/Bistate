from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UnderwritingInputs(BaseModel):
    """Workbook assumptions.  Omitted values use the selected workbook scenario."""

    scenario: Literal["A", "B"] = "A"
    purchase_price: float | None = Field(None, ge=0)
    renovation_budget: float | None = Field(None, ge=0)
    renovation_contingency: float | None = Field(None, ge=0)
    furniture_setup: float | None = Field(None, ge=0)
    down_payment: float | None = Field(None, ge=0, le=1)
    mortgage_rate: float | None = Field(None, ge=0)
    loan_term_years: int | None = Field(None, gt=0)
    closing_cost_percent: float | None = Field(None, ge=0)
    lender_points_percent: float | None = Field(None, ge=0)
    property_tax: float | None = Field(None, ge=0)
    insurance: float | None = Field(None, ge=0)
    initial_reserve: float | None = Field(None, ge=0)
    personal_use_days: float | None = Field(None, ge=0)
    available_rental_days: float | None = Field(None, ge=0)
    nightly_rate: float | None = Field(None, ge=0)
    occupancy: float | None = Field(None, ge=0, le=1)
    average_stay: float | None = Field(None, gt=0)
    cleaning_fee: float | None = Field(None, ge=0)
    platform_fee: float | None = Field(None, ge=0)
    management_fee: float | None = Field(None, ge=0)
    cancellation_leakage: float | None = Field(None, ge=0)
    shtick_weddings: float | None = Field(None, ge=0)
    other_weddings: float | None = Field(None, ge=0)
    other_private_events: float | None = Field(None, ge=0)
    wedding_venue_fee: float | None = Field(None, ge=0)
    shtick_production_revenue: float | None = Field(None, ge=0)
    other_event_production_revenue: float | None = Field(None, ge=0)
    wedding_buyout_revenue: float | None = Field(None, ge=0)
    wedding_add_ons: float | None = Field(None, ge=0)
    event_direct_cost: float | None = Field(None, ge=0)
    event_insurance_permits: float | None = Field(None, ge=0)
    noise_shuttle_security_per_event: float | None = Field(None, ge=0)
    utilities: float | None = Field(None, ge=0)
    internet_software_monitoring: float | None = Field(None, ge=0)
    turnover_cleaning_cost: float | None = Field(None, ge=0)
    maintenance_reserve_percent: float | None = Field(None, ge=0)
    capital_replacement_reserve_percent: float | None = Field(None, ge=0)
    snow_landscaping_pest: float | None = Field(None, ge=0)
    septic_well_generator_reserve: float | None = Field(None, ge=0)
    accounting_bookkeeping: float | None = Field(None, ge=0)
    str_permit_fees: float | None = Field(None, ge=0)
    tax_rate: float | None = Field(None, ge=0)
    building_allocation: float | None = Field(None, ge=0, le=1)
    cost_seg_allocation: float | None = Field(None, ge=0, le=1)
    annual_adr_growth: float | None = Field(None, ge=0)
    annual_operating_expense_inflation: float | None = Field(None, ge=0)
    annual_property_appreciation: float | None = Field(None, ge=0)
    selling_cost_percent: float | None = Field(None, ge=0)
    zero_revenue_monthly_affordability_ceiling: float | None = Field(None, ge=0)


class UnderwritingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str
    assumptions: dict[str, Any]
    acquisition: dict[str, float]
    renovation: dict[str, Any]
    revenue: dict[str, float]
    operating_costs: dict[str, float]
    financing: dict[str, float]
    tax: dict[str, float]
    dashboard: dict[str, float]
    zero_revenue_affordability: dict[str, Any]
    sensitivity: dict[str, Any]
    projection: dict[str, Any]
    comparables: dict[str, Any]
    traceability: dict[str, Any]
