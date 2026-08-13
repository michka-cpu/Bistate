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

## Remaining known limitations

1. **URL parsing is heuristic, not a licensed feed.** Land/parcel URLs (LandWatch) and zpid-only Zillow links legitimately carry no street address, so they are marked incomplete (correct, not fabricated) and require Resolve. Facts (beds/baths/price/flood/comps) still need enrichment providers.
2. **Live enrichment providers are unconfigured by default** (`live_providers_enabled=false`), so enrichment, valuation, and live comparables are unavailable — disclosed in the UI, never invented. Configure credentials to populate them.
3. **Financials are workbook estimates until inputs are entered.** With no asking price, figures come from the default scenario and are labeled as estimates; enter asking price/taxes for property-specific returns.
4. **"Investment Score" and "Risk Score" are not separate model outputs.** Represented honestly by the Buy score and by the Risk summary / hard-constraint list rather than invented numbers.
5. **Legacy `Unknown/NA` rows** are now flagged incomplete with a Resolve action but retain their original stored names until resolved (no destructive backfill was performed).
6. **Naive CSV escaping** and unbounded listing accumulation from the prior pass are unchanged. *(Low)*
7. **`PropertyDetailPage.tsx` remains a large `@ts-nocheck` module.** Grew with this work; a future split is warranted.

---

## Suggested next priorities
1. Wire `pytest` + `vitest` + `playwright` into CI so these journeys are guarded automatically.
2. Configure at least the free public providers (Census geocoder/ACS, FEMA) so imports geocode and coverage rises without paid feeds.
3. Split `PropertyDetailPage.tsx` and remove `@ts-nocheck`.
4. Optional server-side address canonicalization (street-suffix expansion) behind tests to strengthen dedup further.
