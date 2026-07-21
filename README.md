# Bistate

Bistate is a real-estate acquisition workspace. Import a listing URL, address, or MLS
number to create a diligence record, run traceable enrichment, persist workbook-driven
underwriting, and produce an investment memo. The React workspace adds a property
pipeline, due-diligence documents, internal notes, and tasks.

## Stack

- **API:** Python, FastAPI, SQLAlchemy, SQLite, and Alembic
- **Web:** React, TypeScript, Vite, and Tailwind CSS
- **Delivery:** Docker Compose and GitHub Actions

## Local development

### Prerequisites

- Python 3.13+
- Node.js 22+

### API

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; `GET /api/health` returns `{ "status": "ok" }`.
Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### Web dashboard

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite forwards `/api` requests to the local API.

## Tests and migrations

```bash
cd backend
pytest -q
alembic upgrade head
```

Create a future migration after changing SQLAlchemy models with:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
```

## Containers

To run the application in Docker:

```bash
docker compose up --build
```

The dashboard is then served on `http://localhost:5173`, and the API on `http://localhost:8000`.

## Underwriting engine

`POST /api/underwriting/calculate` evaluates the Scenario A formulas from the primary
`Upstate_Airbnb_Wedding_Venue_Underwriting_Model.xlsx` workbook. Send an empty JSON
object to use the workbook defaults, or override any documented assumption:

```json
{"purchase_price": 500000, "occupancy": 0.5, "nightly_rate": 425}
```

The response returns the workbook's acquisition, revenue, operating-cost, financing,
tax, and dashboard sections. Formula references that are internally inconsistent in
the workbook are intentionally retained literally: the dashboard uses Revenue Model
B19, while the worksheet's total-gross-revenue B20 uses B10 and B18.

The workbook engine is the financial source of truth. Property workflows call the same
`calculate` service and persist its complete response; they do not duplicate or modify
workbook formulas.

## Acquisition workflow

### 1. Import

`POST /api/properties/import` accepts at least one of `listing_url`, `raw_address`, or
`mls_number`:

```json
{
  "listing_url": "https://www.zillow.com/homedetails/example",
  "raw_address": "12 Maple St, Kingston, NY 12401",
  "mls_number": "MLS-123"
}
```

Provider adapters identify Zillow, Realtor, Redfin, Airbnb, and LoopNet URLs. A generic
adapter handles other providers, addresses, and MLS references, so new provider clients
can be added without changing the import endpoint. The normalized property stores
listing provenance and all available physical, pricing, image, description, agent, GPS,
and parcel fields. Provider integrations should populate those fields as credentials and
licensed feeds become available.

### 2. Enrichment

Import automatically runs the enrichment registry. It creates fields for FEMA flood,
schools, STR regulations, airport and NYC drive time, hospital and grocery distance,
walkability, wedding and Airbnb suitability, zoning, and parcel information. Every field
has this traceable shape:

```json
{
  "value": null,
  "source": "FEMA National Flood Hazard Layer",
  "last_updated": "2026-07-19T03:00:00Z",
  "confidence": 0.0
}
```

Unavailable provider facts remain explicit `null` values with zero confidence rather
than fabricated data. `POST /api/properties/{property_id}/enrich` refreshes enrichment.

### 3. Underwriting

After enrichment, import calls the existing workbook underwriting engine and persists
the full response, assumptions, Buy Score, Airbnb Score, Wedding Score, Personal Use
Score, Overall Score, and confidence. When asking price or taxes are present they are
passed as workbook assumption overrides. Use
`POST /api/properties/{property_id}/underwrite` to recalculate intentionally.

Pipeline status is updated through the existing property update endpoint and supports:
`New`, `Reviewing`, `Underwriting`, `Needs Info`, `Approved`, `Rejected`,
`Under Contract`, and `Closed`.

### 4. Investment memo

`GET /api/properties/{property_id}/report` returns the complete persisted memo:
executive summary, strengths, weaknesses, risks, renovation and financial summaries,
cash required, projected returns, sensitivities, underwriting traceability, assumptions,
verified comparable properties, missing information, and confidence.

### 5. Workspace records

- `POST/GET /api/properties/{property_id}/documents` uploads and lists inspection PDFs,
  surveys, permits, photos, and floor plans. Download or delete by document ID.
- `POST/GET /api/properties/{property_id}/notes` creates and lists internal notes.
- `POST/GET /api/properties/{property_id}/tasks` creates and lists tasks. Patch a task to
  assign it, set a due date, or mark it complete.

Uploads are stored below `UPLOAD_DIR` (default `./uploads`) and are limited to 25 MB.

## Live Property Intelligence

### Supported imports and analysis flow

Use a Zillow, Realtor.com, Redfin, LoopNet, or generic listing URL, a raw address, or an MLS
identifier with `POST /api/properties/import`. The endpoint normalizes source and URL, creates
the acquisition record, then runs **normalize → import → enrich → collect comparables → existing
workbook underwriting → investment memo persistence**. Refresh all refreshable steps with
`POST /api/properties/{id}/refresh`; enrichment-only refreshes use `/enrich`.

### Provider configuration and data integrity

Provider modules are independently configured by `FEMA_API_URL`, `CENSUS_API_KEY`,
`ASSESSOR_API_KEY`, `PARCEL_API_KEY`, `SCHOOLS_API_KEY`, `ZONING_API_KEY`,
`STR_REGULATIONS_API_KEY`, `ROUTING_API_KEY`, `PLACES_API_KEY`, `WALKSCORE_API_KEY`, and
`AIRDNA_API_KEY`. Configure `PROVIDER_TIMEOUT_SECONDS`, `PROVIDER_RETRY_COUNT`, and
`PROVIDER_CACHE_SECONDS` for future
network connectors. `GET /api/properties/providers/health` exposes configuration health.

Every enrichment result includes `value`, `source`, `retrieval_status`, `confidence`,
`last_updated`, and `missing_reason`. Results are cached until 30 days old; stale records are re-fetched by the
pipeline. Provider errors are isolated and saved on the property, so partial results and the
workbook analysis remain available. FEMA, Census, assessor/parcel, schools, zoning, STR rules,
routing/places, Walk Score, Airbnb market data, and comparable sales currently require a
configured/approved connector or credential. The application returns explicit unavailable/null
facts—not scraped, estimated, or invented values—until one is enabled. Comparable data is never
presented as verified unless returned by a licensed adapter.

## Activated public providers

Set `LIVE_PROVIDERS_ENABLED=true` to permit public HTTP lookups. Bistate uses the official
[U.S. Census Geocoder](https://geocoding.geo.census.gov/) for coordinates, FEMA's
[National Flood Hazard Layer](https://hazards.fema.gov/femaportal/wps/portal/NFHLWMS) for flood
zone/risk, and the [Census ACS API](https://www.census.gov/data/developers/data-sets/acs-5year.html)
for tract demographics. Public requests use `PROVIDER_TIMEOUT_SECONDS` and bounded retries
(`PROVIDER_RETRY_COUNT`); HTTP 429 is rate-limit aware. Disabled, malformed, timed-out, or
rate-limited providers retain their contract key with an explicit unavailable provenance object.

### Google routing and places milestone

With `LIVE_PROVIDERS_ENABLED=true`, configure `ROUTING_API_KEY` with Google Maps **Directions
API** access and `PLACES_API_KEY` with Google Maps **Places API** access. The routing provider
stores a live `nyc_drive_time` fact with distance and driving duration. The places provider stores
`nearest_amtrak`, `restaurant_hub`, `nearest_airport`, `hospital_distance`, and `grocery_distance`.
Each place fact includes the provider-returned name, address, place ID, coordinates, route distance,
and route duration when the routing key is also configured. A missing key, no result, or provider
failure remains an explicit `retrieval_status: unavailable` fact; no proximity data is estimated.
Successful provider HTTP responses are cached for `PROVIDER_CACHE_SECONDS` (one hour by default)
to limit quota use. Restaurant results are labelled as a provider-returned **restaurant hub candidate**,
not a market-demand score; Airbnb, wedding, personal-use, and investment scores remain derived
model outputs rather than live provider facts.

## Interactive property dashboard

Milestone 9 adds a daily-use acquisition workspace while keeping the workbook underwriting
engine and its calculations unchanged. The dashboard surfaces portfolio KPIs (imports, deals
under review, average Buy Score, average IRR, highest score, and pipeline counts), pinned
favorites, recent properties, and search across address, county, status, and imported records.

Each **Property Detail** workspace provides Overview, Listing, Underwriting, Financials,
Renovation, Airbnb, Wedding, Maps, Comparable Sales, Documents, Notes, and Activity Timeline
sections. It includes a listing gallery with a missing-image state, live OpenStreetMap location
view, downloadable diligence documents, and an ordered audit trail for imports, enrichment,
analysis, notes, and uploads.

### Workflow and comparison mode

Use the import bar to create a property, then follow the visible background-job sequence:
Import → Enrichment → Comparables → Workbook Underwriting → Investment Memo → Completed.
Provider failures remain visible and can be retried without changing the workbook outputs.
Select **Compare** beside two or more properties to open side-by-side purchase price, score,
renovation, projected IRR, Airbnb, wedding, and cash-required comparisons. The best value in
each metric is highlighted.

### Exports

Investment memos have print/PDF and copy-friendly presentation controls. The Documents area
retains uploads and downloads; CSV property-summary and Excel-workbook-summary export actions
are available from the workspace without modifying any underwriting calculations.
