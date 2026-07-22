def test_search_persists_separate_discovered_listings(client):
    response = client.post('/api/discovery/search', json={'county': 'Columbia', 'min_price': 400000, 'bedrooms': 3})
    assert response.status_code == 200
    listings = response.json()
    assert {item['listing_source'] for item in listings} == {'Zillow', 'Realtor', 'Redfin', 'LandWatch'}
    assert client.get('/api/properties').json() == []


def test_watchlist_and_analyze_imports_discovery_listing(client):
    listing = client.post('/api/discovery/search', json={}).json()[0]
    watched = client.put(f"/api/discovery/listings/{listing['id']}/watchlist", json={'is_watchlisted': True})
    assert watched.status_code == 200 and watched.json()['is_watchlisted'] is True
    analyzed = client.post(f"/api/discovery/listings/{listing['id']}/analyze")
    assert analyzed.status_code == 201
    assert analyzed.json()['asking_price'] == listing['asking_price']
