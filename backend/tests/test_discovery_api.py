def test_search_persists_separate_discovered_listings(client):
    response = client.post('/api/discovery/search', json={'county': 'Columbia', 'min_price': 400000, 'bedrooms': 3})
    assert response.status_code == 200
    listings = response.json()
    assert {item['listing_source'] for item in listings} == {'Zillow', 'Realtor', 'Redfin', 'LandWatch'}
    assert client.get('/api/properties').json() == []


def test_search_returns_only_listings_matching_the_submitted_filters(client):
    # Seed the persistent listings table with a broad search.
    assert len(client.post('/api/discovery/search', json={}).json()) == 4

    # A filter that matches no sample listing must return an empty result, not the whole table.
    assert client.post('/api/discovery/search', json={'county': 'Nowhere'}).json() == []
    assert client.post('/api/discovery/search', json={'town': 'Albany'}).json() == []
    assert client.post('/api/discovery/search', json={'property_type': 'Land'}).json() == []
    assert client.post('/api/discovery/search', json={'bedrooms': 5}).json() == []
    assert client.post('/api/discovery/search', json={'postal_code': '99999'}).json() == []

    # Sample listings are priced 475k/500k/525k/550k; a max_price bound trims the set.
    capped = client.post('/api/discovery/search', json={'max_price': 480000}).json()
    assert [item['asking_price'] for item in capped] == [475000]

    floored = client.post('/api/discovery/search', json={'min_price': 520000}).json()
    assert sorted(item['asking_price'] for item in floored) == [525000, 550000]


def test_watchlist_and_analyze_imports_discovery_listing(client):
    listing = client.post('/api/discovery/search', json={}).json()[0]
    watched = client.put(f"/api/discovery/listings/{listing['id']}/watchlist", json={'is_watchlisted': True})
    assert watched.status_code == 200 and watched.json()['is_watchlisted'] is True
    analyzed = client.post(f"/api/discovery/listings/{listing['id']}/analyze")
    assert analyzed.status_code == 201
    assert analyzed.json()['asking_price'] == listing['asking_price']
