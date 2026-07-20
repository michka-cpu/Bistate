def _property(client):
    return client.post('/api/properties/import', json={'raw_address':'1 Main St, Beacon, NY 12508'}).json()

def test_preferences_status_and_activity_are_persisted(client):
    prop = _property(client); property_id = prop['id']
    updated = client.put(f'/api/properties/{property_id}', json={'is_favorite': True, 'is_pinned': True, 'status': 'Under Contract'})
    assert updated.status_code == 200
    assert updated.json()['is_favorite'] is True and updated.json()['is_pinned'] is True
    reread = client.get(f'/api/properties/{property_id}').json()
    assert reread['status'] == 'Under Contract'
    events = client.get(f'/api/properties/{property_id}/activity').json()
    assert any(event['event_type'] == 'status_changed' for event in events)

def test_exports_return_persisted_property_data(client):
    prop = _property(client); property_id = prop['id']
    assert client.get(f'/api/properties/{property_id}/exports/csv').status_code == 200
    assert client.get(f'/api/properties/{property_id}/exports/pdf').status_code == 200
    assert client.get(f'/api/properties/{property_id}/exports/xlsx').status_code == 200
