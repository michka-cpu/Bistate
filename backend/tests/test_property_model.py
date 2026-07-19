from app.models.property import Property


def test_property_model_accepts_core_attributes() -> None:
    property_record = Property(
        name="Maple House",
        address="12 Maple Street",
        city="Kingston",
        state="NY",
    )

    assert property_record.name == "Maple House"
    assert property_record.state == "NY"
