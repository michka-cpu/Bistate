from datetime import date
from app.models.comparable_property import ComparableProperty
from app.models.property import Property
from app.services.valuation import value_property

def test_weighted_valuation_persists_similarity_and_explainability():
    prop = Property(name='Subject', address='1 Main', city='Hudson', state='NY', asking_price=500000, property_type='Single Family', bedrooms=3, bathrooms=2, acreage=4, square_feet=2000)
    comp = ComparableProperty(address='2 Main', sale_price=550000, square_feet=2100, bedrooms=3, bathrooms=2, acreage=4.5, property_type='Single Family', distance_miles=1, sale_date=date.today(), source='Licensed MLS', verification_status='verified', provenance={'provider': 'MLS'})
    prop.comparable_properties.append(comp)
    result = value_property(prop)
    assert result['estimated_value'] is not None
    assert result['pricing_signal'] == 'Undervalued'
    assert result['comparables'][0]['similarity_score'] > 80
    assert result['provenance']['method'] == 'weighted similarity'
