def test_search_includes_monticello_and_catskills_markets(client):
    # Monticello (Sullivan County) is a required target market; each source lists it.
    listings = client.post('/api/discovery/search', json={'town': 'Monticello'}).json()
    assert {item['listing_source'] for item in listings} == {'Zillow', 'Realtor', 'Redfin', 'LandWatch'}
    assert {item['city'] for item in listings} == {'Monticello'}
    assert all(item['county'] == 'Sullivan' for item in listings)
    assert client.get('/api/properties').json() == []


def test_search_covers_the_catskills_counties(client):
    for county in ('Sullivan', 'Delaware', 'Ulster'):
        found = client.post('/api/discovery/search', json={'county': county}).json()
        assert found, f'expected sample listings for {county} County'
        assert all(item['county'] == county for item in found)


def test_search_persists_separate_discovered_listings(client):
    response = client.post('/api/discovery/search', json={'county': 'Sullivan', 'min_price': 400000, 'bedrooms': 3})
    assert response.status_code == 200
    listings = response.json()
    assert {item['listing_source'] for item in listings} == {'Zillow', 'Realtor', 'Redfin', 'LandWatch'}
    assert client.get('/api/properties').json() == []


def test_search_returns_only_listings_matching_the_submitted_filters(client):
    # Seed the persistent listings table with a broad search: four sources x N markets.
    seeded = client.post('/api/discovery/search', json={}).json()
    assert len(seeded) > 4

    # A filter that matches no sample listing must return an empty result, not the whole table.
    assert client.post('/api/discovery/search', json={'county': 'Nowhere'}).json() == []
    assert client.post('/api/discovery/search', json={'town': 'Albany'}).json() == []
    assert client.post('/api/discovery/search', json={'bedrooms': 9}).json() == []
    assert client.post('/api/discovery/search', json={'postal_code': '99999'}).json() == []

    # Land parcels are present and isolable by the property-type filter.
    land = client.post('/api/discovery/search', json={'property_type': 'Land'}).json()
    assert land and {item['property_type'] for item in land} == {'Land'}

    # A max_price bound trims the set to only the cheaper listings.
    capped = client.post('/api/discovery/search', json={'max_price': 320000}).json()
    assert capped and all(item['asking_price'] <= 320000 for item in capped)


def test_watchlist_and_analyze_imports_discovery_listing(client):
    listing = client.post('/api/discovery/search', json={}).json()[0]
    watched = client.put(f"/api/discovery/listings/{listing['id']}/watchlist", json={'is_watchlisted': True})
    assert watched.status_code == 200 and watched.json()['is_watchlisted'] is True
    analyzed = client.post(f"/api/discovery/listings/{listing['id']}/analyze")
    assert analyzed.status_code == 201
    assert analyzed.json()['asking_price'] == listing['asking_price']
