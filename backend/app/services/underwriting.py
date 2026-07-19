from math import pow

from app.schemas.underwriting import UnderwritingInputs, UnderwritingResult


def _pmt(rate: float, periods: int, principal: float) -> float:
    return principal / periods if rate == 0 else principal * rate * pow(1 + rate, periods) / (pow(1 + rate, periods) - 1)


def calculate(inputs: UnderwritingInputs) -> UnderwritingResult:
    """Literal implementation of the primary workbook's Scenario A cell formulas."""
    i = inputs
    down_payment = i.purchase_price * i.down_payment
    loan_amount = i.purchase_price - down_payment
    acquisition = {
        "purchase_price": i.purchase_price, "down_payment": down_payment, "loan_amount": loan_amount,
        "closing_costs": i.purchase_price * i.closing_cost_percent, "lender_points_fees": loan_amount * i.lender_points_percent,
        "renovation_budget": i.renovation_budget, "renovation_contingency": i.renovation_budget * i.renovation_contingency,
        "furniture_design_setup": i.furniture_setup, "inspection_septic_well_survey": 6500, "permit_architect_engineering": 12000,
        "technology_locks_cameras_wifi": 7000, "initial_linen_kitchen_supplies": 6000, "wedding_venue_setup": 25000,
        "initial_reserve": i.initial_reserve,
    }
    acquisition["total_project_cost"] = i.purchase_price + sum(v for k, v in acquisition.items() if k not in {"purchase_price", "down_payment", "loan_amount", "total_project_cost"})
    acquisition["total_cash_required"] = down_payment + sum(v for k, v in acquisition.items() if k not in {"purchase_price", "down_payment", "loan_amount", "total_project_cost", "total_cash_required"})
    occupied_days = i.available_rental_days * i.occupancy
    stays = occupied_days / i.average_stay
    gross_lodging = occupied_days * i.nightly_rate + stays * i.cleaning_fee
    weddings = i.shtick_weddings + i.other_weddings
    venue_rental = weddings * i.wedding_venue_fee
    shtick_production = i.shtick_weddings * i.shtick_production_revenue
    other_production = i.other_weddings * i.other_event_production_revenue
    buyout = weddings * i.wedding_buyout_revenue
    add_ons = weddings * i.wedding_add_ons
    other_private = i.other_private_events * 7500
    # Deliberately mirrors Revenue Model B19 and B20: B19 excludes B18; B20 includes B10 and B18.
    gross_wedding_event = venue_rental + shtick_production + other_production + buyout + add_ons
    revenue = {"available_rental_days": i.available_rental_days, "occupied_lodging_days": occupied_days, "number_of_stays": stays,
        "nightly_lodging_revenue": occupied_days * i.nightly_rate, "cleaning_fee_revenue": stays * i.cleaning_fee,
        "gross_lodging_revenue": gross_lodging, "venue_rental_revenue": venue_rental, "shtick_production_revenue": shtick_production,
        "other_wedding_production_revenue": other_production, "wedding_lodging_buyout_revenue": buyout,
        "wedding_add_ons_commissions": add_ons, "other_private_event_revenue": other_private,
        "gross_wedding_event_revenue": gross_wedding_event, "total_gross_revenue": gross_lodging + other_private}
    operating_costs = {"property_tax": i.property_tax, "insurance": i.insurance, "utilities": i.utilities,
        "internet_software_monitoring": i.internet_software_monitoring, "turnover_cleaning": stays * i.turnover_cleaning_cost,
        "platform_fees": gross_lodging * i.platform_fee, "property_management": gross_lodging * i.management_fee,
        "revenue_leakage_cancellations": gross_lodging * i.cancellation_leakage,
        "maintenance_reserve": (i.purchase_price + i.renovation_budget) * i.maintenance_reserve_percent,
        "capital_replacement_reserve": (i.purchase_price + i.renovation_budget) * i.capital_replacement_reserve_percent,
        "snow_landscaping_pest": i.snow_landscaping_pest, "septic_well_generator_reserve": i.septic_well_generator_reserve,
        "accounting_bookkeeping": i.accounting_bookkeeping, "str_permit_fees": i.str_permit_fees,
        "wedding_event_direct_costs": other_private * i.event_direct_cost, "event_insurance_permits": i.event_insurance_permits,
        "security_shuttle_noise_logistics": weddings * i.noise_shuttle_security_per_event}
    operating_costs["total_operating_expenses"] = sum(operating_costs.values())
    monthly_payment = _pmt(i.mortgage_rate / 12, i.loan_term_years * 12, loan_amount)
    annual_debt_service = monthly_payment * 12
    monthly_rate = i.mortgage_rate / 12
    balance = loan_amount
    interest = 0.0
    for _ in range(12):
        period_interest = balance * monthly_rate
        interest += period_interest
        balance -= monthly_payment - period_interest
    financing = {"monthly_principal_interest": monthly_payment, "annual_debt_service": annual_debt_service, "year_1_interest": interest, "year_1_principal": annual_debt_service - interest}
    rental_allocation = i.available_rental_days / (i.personal_use_days + i.available_rental_days)
    building_basis = i.purchase_price * i.building_allocation + i.renovation_budget
    standard_depreciation = building_basis * rental_allocation / 27.5
    bonus_depreciation = building_basis * i.cost_seg_allocation * rental_allocation
    deductions = standard_depreciation + bonus_depreciation + interest * rental_allocation + i.property_tax * rental_allocation + (operating_costs["total_operating_expenses"] - i.property_tax - i.insurance) * rental_allocation
    tax = {"building_basis": building_basis, "rental_allocation": rental_allocation, "standard_depreciation": standard_depreciation, "cost_seg_eligible_basis": bonus_depreciation, "bonus_depreciation": bonus_depreciation, "potential_year_1_tax_deduction": deductions, "potential_tax_value": deductions * i.tax_rate}
    # Dashboard references Revenue Model B19 (not B20), exactly as authored.
    noi = gross_wedding_event - operating_costs["total_operating_expenses"]
    pre_tax_cash_flow = noi - annual_debt_service
    dashboard = {"purchase_price": i.purchase_price, "renovation_contingency": i.renovation_budget * (1 + i.renovation_contingency),
        "total_project_cost": acquisition["total_project_cost"], "total_cash_required": acquisition["total_cash_required"],
        "gross_lodging_revenue": gross_lodging, "gross_wedding_event_revenue": other_private, "total_gross_revenue": gross_wedding_event,
        "operating_expenses": operating_costs["total_operating_expenses"], "noi_before_debt": noi, "annual_debt_service": annual_debt_service,
        "pre_tax_cash_flow": pre_tax_cash_flow, "dscr": noi / annual_debt_service, "potential_year_1_tax_value": tax["potential_tax_value"],
        "after_tax_cash_flow": pre_tax_cash_flow + tax["potential_tax_value"], "cash_on_cash_return": pre_tax_cash_flow / acquisition["total_cash_required"],
        "break_even_gross_revenue": operating_costs["total_operating_expenses"] + annual_debt_service}
    return UnderwritingResult(acquisition=acquisition, revenue=revenue, operating_costs=operating_costs, financing=financing, tax=tax, dashboard=dashboard)
