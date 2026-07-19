from pydantic import BaseModel, ConfigDict, Field


class UnderwritingInputs(BaseModel):
    """Primary workbook assumptions; values are Scenario A defaults unless supplied."""

    purchase_price: float = Field(500_000, ge=0)
    renovation_budget: float = Field(150_000, ge=0)
    renovation_contingency: float = Field(0.15, ge=0)
    furniture_setup: float = Field(35_000, ge=0)
    down_payment: float = Field(0.20, ge=0, le=1)
    mortgage_rate: float = Field(0.0675, ge=0)
    loan_term_years: int = Field(30, gt=0)
    closing_cost_percent: float = Field(0.04, ge=0)
    lender_points_percent: float = Field(0.01, ge=0)
    property_tax: float = Field(9_000, ge=0)
    insurance: float = Field(5_000, ge=0)
    initial_reserve: float = Field(30_000, ge=0)
    personal_use_days: float = Field(90, ge=0)
    available_rental_days: float = Field(230, ge=0)
    nightly_rate: float = Field(425, ge=0)
    occupancy: float = Field(0.50, ge=0, le=1)
    average_stay: float = Field(3, gt=0)
    cleaning_fee: float = Field(225, ge=0)
    platform_fee: float = Field(0.03, ge=0)
    management_fee: float = Field(0, ge=0)
    cancellation_leakage: float = Field(0.03, ge=0)
    shtick_weddings: float = Field(4, ge=0)
    other_weddings: float = Field(2, ge=0)
    other_private_events: float = Field(4, ge=0)
    wedding_venue_fee: float = Field(12_000, ge=0)
    shtick_production_revenue: float = Field(18_000, ge=0)
    other_event_production_revenue: float = Field(7_500, ge=0)
    wedding_buyout_revenue: float = Field(6_500, ge=0)
    wedding_add_ons: float = Field(2_500, ge=0)
    event_direct_cost: float = Field(0.38, ge=0)
    event_insurance_permits: float = Field(5_000, ge=0)
    noise_shuttle_security_per_event: float = Field(2_500, ge=0)
    utilities: float = Field(7_200, ge=0)
    internet_software_monitoring: float = Field(2_400, ge=0)
    turnover_cleaning_cost: float = Field(260, ge=0)
    maintenance_reserve_percent: float = Field(0.015, ge=0)
    capital_replacement_reserve_percent: float = Field(0.01, ge=0)
    snow_landscaping_pest: float = Field(6_000, ge=0)
    septic_well_generator_reserve: float = Field(3_500, ge=0)
    accounting_bookkeeping: float = Field(4_500, ge=0)
    str_permit_fees: float = Field(2_500, ge=0)
    tax_rate: float = Field(0.40, ge=0)
    building_allocation: float = Field(0.80, ge=0, le=1)
    cost_seg_allocation: float = Field(0.20, ge=0, le=1)


class UnderwritingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acquisition: dict[str, float]
    revenue: dict[str, float]
    operating_costs: dict[str, float]
    financing: dict[str, float]
    tax: dict[str, float]
    dashboard: dict[str, float]
