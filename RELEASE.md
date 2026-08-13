# Release Notes

## Acceptance fix — valid address reported "Import failed" / "incomplete"; financial-failure gating

A full US address (`139 County Route 21c, Ghent, NY 12075`) entered in the pipeline **Import & analyze** box returned **"Import failed"** and then an incomplete-listing banner. Root causes (both general, reproduced in-browser):

1. **Duplicate treated as failure.** The pipeline import handler (`DashboardPage.importProperty`) sent the correct full `raw_address`; the backend correctly returned **409** (the property already existed), but the handler did `if (!response.ok) throw 'Import failed'` — so an *already-imported* address surfaced as a hard error instead of opening the existing property. (Discovery's box handled 409; the pipeline box did not.) Fixed by unifying both boxes on a shared `buildImportBody` classifier and handling **409 → open existing / 422 → clear message**. A valid address now imports once and opens the property; a re-entry opens the same record — never "Import failed", never an unresolved duplicate, never a "Resolve" prompt.
2. **Geocoded address left "incomplete".** When the naive comma-parser couldn't extract a locality it stored `Unknown/NA`, and the live geocoder resolved coordinates/county but **never backfilled city/state** — so a geocodable address stayed flagged incomplete. Fixed: the Census geocoder now **backfills city/state/ZIP from the authoritative match** (placeholders only, never user values) and excludes placeholder locality from its query; import decides resolution **after** enrichment. The API also normalizes whitespace-only identifiers to reject empty imports.

**Financial-failure gating (presentation only — no underwriting change).** When identity is unresolved or the critical inputs for property-specific underwriting are absent, the app no longer displays default-workbook outputs as if they were results (Overall 71/100, $418k cash, 19.3% CoC, 22.3% IRR, 22.4% cap, 3.59× DSCR, $172.5k renovation). Those areas — the hero KPI row, the Overview score/financial summary, and the Financials/Underwriting/Renovation tabs — are replaced with an explicit **"Analysis incomplete"** state listing exactly what is required (asking price, taxes, acreage, beds/baths, sq ft, and a resolved address). Numbers reappear automatically once the inputs exist. The underwriting engine, weights, thresholds, and workbook logic are untouched.

**Manual verification** (`139 County Route 21c, Ghent, NY 12075`, both import boxes): opens property id=5 with **no "Import failed"** and **no incomplete banner**; status **Reviewing**. Populated (live/verifiable): matched address `139 CO RD 21C, GHENT, NY, 12075`, city **Ghent**, state **NY**, ZIP **12075**, county **Columbia**, coordinates **42.2612 / −73.6057**, census tract 000700, **elevation 741.1 ft** (USGS). Unavailable (disclosed, not invented): **FEMA flood** — public NFHL service returning error 400 (temporarily rate-limited); **ACS demographics** — needs a free `census_api_key`; assessor/parcel/zoning/STR/schools/walkability/routing/places — need their keys. Property facts (price, taxes, beds/baths, acreage) have no free source and stay empty. **Confidence ≈ 5/100**; financial results correctly gated as "Analysis incomplete".

**Tests added:** backend regression classes — full address, abbreviated road forms (`Co Rd`, `County Route`, `State Route`), duplicate re-entry (409 + id), partial address (incomplete), full-address listing URL, invalid/whitespace/malformed input, geocoder locality backfill. Frontend — `buildImportBody` classification, pipeline-box duplicate opens existing (no "Import failed"), analysis-incomplete gating. E2e — pipeline-box duplicate opens the property; the punctuation-variant test updated to the corrected open-existing behavior. Suites: **backend 58, frontend build/lint/15, Playwright 16** — all green.

---

# Release Notes — Core User Journey

Branch: `fix/core-user-journey`
Scope: make Bistate a single obvious workflow — **Find → Import/enrich → Review → Analyze → Compare → Decide** — so a user can analyze a *known* property without understanding the "Listing Discovery" vs. "Pipeline" split. Fixes to listing identity and misleading financial presentation, plus regression coverage.

**Guardrails honored:** no changes to the calibrated underwriting formulas, weights, thresholds, hard constraints, or scoring methodology. The workbook engine (`services/underwriting.py`) and score derivation (`services/acquisition.py`) are untouched. All new signals are **derived, read-only, and additive** — the numeric outputs are identical; only their labeling and provenance changed. Disclosed unavailable/unconfigured provider results are surfaced honestly, never replaced with invented values.

---

## The core problem

There were two competing full-screen workflows. The **Listing Discovery** page offered only structured filters (County / Town / ZIP / …); to analyze a *known* address or listing URL you had to leave it, open the **Pipeline**, and use a separate import bar. Worse, the results a user did get were misleading:

- Zillow URLs ending `…/215394889_zpid/` became property **names** like "215394889 Zpid, Unknown, NA".
- With live providers off (default) and no asking price, the workbook ran on **defaults**, so every input-less property displayed identical **Overall 71/100, IRR 22.3%, Cap 22.4%, Cash $418k** — while **Confidence read 0/100**, with nothing labeling the figures as estimates.

---

## Bugs found & fixed

| # | Severity | Area | Symptom → Fix |
|---|----------|------|---------------|
| 1 | High | Workflow | No universal entry point on Discovery; a known property couldn't be analyzed without navigating to the Pipeline. → Added a prominent **"Paste an address or listing URL" / "Search & Analyze"** input above the (now secondary) "Discover properties" filters; on submit it imports, enriches, underwrites, and **navigates to the property detail view** with progress shown. |
| 2 | High | Listing identity | Raw provider IDs masqueraded as names/addresses (`215394889 Zpid`, `Unknown, NA`). → Rewrote `listing_providers.py` with per-provider URL parsing (Zillow/Redfin/Realtor/LandWatch). A URL that yields only an opaque id is **not** turned into a fake address; it is marked **`listing_incomplete`** with an explicit "Listing information incomplete" state and a **Resolve/Retry** action. No address is ever invented. |
| 3 | High | Misleading results | High scores/returns shown as authoritative alongside 0/100 confidence. → Added derived, read-only `financials_are_estimates` + `missing_core_inputs`. When core inputs are missing the workbook still runs (unchanged), but the UI labels every input-derived figure **"· est"**, shows an **estimate banner**, and flags low confidence. |
| 4 | High | Detail hierarchy | No "Personal Use" / "Risks & Missing Data" tabs; Overview lacked scores, key financials, and any "why". → Rebuilt Overview (score summary, key financials with estimate labeling, **"Why this scored this way"** — positives, risks, hard-constraint failures, missing info) and reordered/added tabs: Overview, Listing, Financials, Airbnb, Wedding Venue, Personal Use, Property Intelligence, Comparable Sales, Risks & Missing Data, … |
| 5 | High | De-duplication | Distinct incomplete listings (different zpid-only URLs) collapsed into one because they share the `Unknown/NA` placeholder address. → Incomplete listings de-duplicate by **URL only**, never by the placeholder locality. |
| 6 | Medium | Provider disclosure | That live enrichment never ran was only discoverable deep inside the Intelligence tab. → A disclosure banner ("Live enrichment providers are not configured…") now appears on the detail view and in Risks & Missing Data. |
| 7 | Medium | Cross-format dedup | A listing URL that resolves to an already-imported address was not recognized as the same property. → URL slugs now normalize to real addresses and dedupe against typed addresses. |

### Key root causes
- `listing_providers.py::_address_from_url` title-cased the last URL path segment and `_parse_address` filled `city="Unknown"`, `state="NA"` — so provider ids became names. Rewritten with street-number detection, per-provider id stripping (e.g. Realtor `_M…`), and locality recovery from path segments (e.g. Redfin `/NY/Hudson/…`).
- `services/acquisition.py::underwrite_property` calls `calculate(UnderwritingInputs(**payload))`; an empty payload (no `asking_price`) runs the full **default** workbook scenario. Behavior preserved; now disclosed via `financials_are_estimates`.

---

## What changed

**Backend (no scoring changes):**
- `services/listing_providers.py` — full rewrite: robust per-provider URL → address parsing, `needs_resolution` + `provider_reference`, no fabricated addresses.
- `schemas/property.py` — added derived `computed_field`s: `missing_core_inputs`, `financials_are_estimates`, `listing_incomplete` (also flags legacy `Unknown/NA` rows automatically).
- `api/acquisition.py` — import sets status `Needs Info` for unresolved listings; new `POST /properties/{id}/resolve` (retry from URL or complete with a supplied address); incomplete listings de-dup by URL only.

**Frontend:**
- `pages/SearchPage.tsx` — universal "Search & Analyze" input above secondary "Discover properties" filters; input classification, unsupported-site/malformed/blank handling, progress steps, duplicate → open-existing.
- `App.tsx` / `pages/DashboardPage.tsx` — search/import navigates to the property detail; estimate + provider-disclosure banners; incomplete-listing banner with inline Resolve; "← Discovery"; sidebar shows "Listing information incomplete" instead of "Unknown, NA".
- `components/PropertyDetailPage.tsx` — new Overview (ScoreSummary, KeyFinancials, WhyPanel), new tabs (Personal Use, Wedding Venue, Risks & Missing Data), Listing provenance panel, estimate labels.
- `components/KPICards.tsx` — "· est" tags on input-derived KPIs; low-confidence emphasis.

---

## Tests

**Backend (`pytest`) — 45 passing (new/updated):**
- `test_import_marks_provider_id_only_urls_incomplete` — zpid-only URL → `listing_incomplete`, `Needs Info`, honest name.
- `test_resolve_completes_an_incomplete_listing` — resolve with a supplied address.
- `test_distinct_incomplete_listings_are_not_deduplicated` — different zpid URLs stay distinct; identical URL still 409.
- `test_redfin_and_realtor_urls_resolve_locality` — Redfin `/NY/Hudson/…` and Realtor `_M…` resolve city/state.
- `test_financials_are_flagged_as_estimates_until_core_inputs_exist`.
- Updated `test_import_rejects_normalized_duplicate_address_and_url` to assert the improved cross-format (URL↔address) dedup.

**Frontend (`vitest`) — 10 passing (new):**
- `search.test.tsx` — universal search routes an address through import into the detail view; unsupported site rejected before any request.

**End-to-end (`Playwright`) — 15 passing (7 new in `e2e/journey.spec.ts`):**
universal address import → detail; estimate labeling; zpid-only incomplete → resolve; blank rejected; unsupported site rejected; new diligence tabs navigable; duplicate opens the existing property. Existing discovery/pipeline specs remain green.

**Also verified:** `npm run build` (tsc + vite), `eslint --max-warnings=0`, and a manual API sweep across real Zillow/Realtor/Redfin/LandWatch URLs, partial address, and MLS number. No console errors in the browser.

---

## Enrichment redesign — automatic live coverage

Goal: a normal address should auto-populate the maximum *verifiable* coverage on import, with no manual steps and nothing invented.

- **Keyless public providers run automatically.** `live_providers_enabled` now defaults **on** (set explicitly in `docker-compose.yml`; the pytest suite sets it `false` via `conftest.py` to stay hermetic). On import, keyless government sources run with no configuration: the **U.S. Census geocoder/geographies**, **FEMA NFHL flood**, and a new **USGS EPQS elevation** adapter.
- **One geocoder call populates the record.** The geocoder switched to `/geographies/onelineaddress`, so a single keyless request resolves coordinates **and** census geographies. Verified `latitude`, `longitude`, `postal_code`, and `county` are persisted onto the property (never overwriting user-entered values), and the tract is reused in-run by the demographics adapter.
- **Honest credential gating.** The ACS *data* API now requires a free Census key, so `census_demographics` self-gates on `census_api_key` (and actually sends it) — genuinely unavailable, with an actionable reason, until configured. Google routing/places remain gated on their keys.
- **Resilient, non-poisoning HTTP.** FEMA's public ArcGIS endpoint intermittently returns an HTTP-200 error envelope; these are now surfaced as a clear, retryable provider error (not a vague "malformed" or a fabricated determination) and are **not cached**, so a transient failure no longer pins for the cache TTL. Transient failures refresh their reason; a previously-live fact is still preserved across a blip.
- **Verified against the real address.** `139 County Route 21c, Ghent, NY` now resolves to `139 CO RD 21C, GHENT, NY, 12075`, county **Columbia**, coords `42.2612, -73.6057`, elevation ~741 ft — all live/verifiable. Demographics (needs the free key) and FEMA (rate-limited during testing) are disclosed as unavailable, not invented. Confidence rose from 0 → ~5 on real coverage.

**Underwriting untouched:** no change to formulas, weights, thresholds, hard constraints, or scoring. Enrichment only supplies facts and provenance.

New tests (backend): geocoder locality/geography population and no-overwrite; elevation parsing; demographics key gating; FEMA error-envelope disclosure; error envelopes are not cached. Suite: **51 passing**, hermetic.

---

## Remaining known limitations

1. **URL parsing is heuristic, not a licensed feed.** Land/parcel URLs (LandWatch) and zpid-only Zillow links legitimately carry no street address, so they are marked incomplete (correct, not fabricated) and require Resolve.
2. **Property facts (price, taxes, beds/baths, acreage) have no free public source** and remain empty for address-only imports — they need a listing/assessor feed or manual entry, and are never invented. Free keyless enrichment covers location, county, tract, ZIP, elevation, and (when the service is up) flood status.
3. **Some providers need free/paid keys:** ACS demographics needs a free Census key; Google routing/places, assessor, parcel, zoning, STR, schools, and walkability need their respective keys. All are honestly "unavailable" until configured.
4. **FEMA's public NFHL service is rate-limited/flaky.** It returns real flood determinations when healthy but was erroring during testing; the flood field is disclosed as temporarily unavailable and repopulates on refresh once the service recovers.
5. **Financials are workbook estimates until inputs are entered.** With no asking price, figures come from the default scenario and are labeled as estimates; enter asking price/taxes for property-specific returns.
6. **"Investment Score" and "Risk Score" are not separate model outputs.** Represented honestly by the Buy score and by the Risk summary / hard-constraint list rather than invented numbers.
7. **Legacy `Unknown/NA` rows** are now flagged incomplete with a Resolve action but retain their original stored names until resolved (no destructive backfill was performed).
8. **Naive CSV escaping** and unbounded listing accumulation from the prior pass are unchanged. *(Low)*
9. **`PropertyDetailPage.tsx` remains a large `@ts-nocheck` module.** Grew with this work; a future split is warranted.

---

## Suggested next priorities
1. Wire `pytest` + `vitest` + `playwright` into CI so these journeys are guarded automatically.
2. Add a free Census API key (and optionally Google routing/places keys) to unlock demographics and drive-time coverage on top of the now-automatic keyless providers.
3. Split `PropertyDetailPage.tsx` and remove `@ts-nocheck`.
4. Optional server-side address canonicalization (street-suffix expansion) behind tests to strengthen dedup further.
