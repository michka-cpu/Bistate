# Release Notes — QA End-to-End Pass

Branch: `qa/e2e-pass-fixes`
Scope: full end-to-end QA of the running app (frontend `:5173`, API `:8000`), fixes, and regression coverage.

**Guardrails honored:** no changes to underwriting formulas, weights, thresholds, hard constraints, or workbook source-of-truth logic. Disclosed unavailable/unconfigured provider results (valuation "Unavailable", provider health) were treated as expected behavior, not bugs.

---

## Bugs found

| # | Severity | Area | Symptom |
|---|----------|------|---------|
| 1 | High | Discovery search | Every search returned the entire stored listings table; county / town / ZIP / price / acreage / bedrooms / property-type filters had **no effect**, and "No listings match these filters." was unreachable once any listing existed. |
| 2 | High | Property Intelligence | `GET /api/properties/{id}/intelligence` returned **HTTP 500** for any property with acreage/taxes/HOA; the UI tab showed "Property intelligence could not be loaded." |
| 3 | Medium | Import de-duplication | Addresses differing only by punctuation or whitespace (`742 Evergreen Terrace.`, `742  Evergreen  Terrace`) were imported as **duplicates** instead of being rejected. |
| 4 | Medium | Exports | Property CSV/PDF/XLSX export endpoints existed and worked, but there was **no UI control** to trigger them (dead `ExportMenu` stub). |
| 5 | Low | Import provenance | LandWatch listing URLs imported with `listing_source = "manual"` instead of `"LandWatch"`, inconsistent with discovery treating LandWatch as a first-class source. |

### Root causes
1. `api/discovery.py::search_listings` used the match predicate only to gate inserts, then returned `select(DiscoveredListing)…` unfiltered.
2. `services/property_intelligence.py` synthesizes diligence facts stamped with the property's persisted `updated_at`, which SQLite returns **tz-naive**; `services/enrichment.py::is_stale` subtracted it from a tz-aware `now()` → `TypeError: can't subtract offset-naive and offset-aware datetimes`.
3. `api/acquisition.py::import_property` de-dup used SQL `ilike` (case-insensitive only) with no punctuation/whitespace normalization.
4. `components/ExportMenu.tsx` was a placeholder stub imported by no one; the dashboard hero never rendered export links.
5. `services/listing_providers.py::PROVIDERS` omitted a LandWatch domain adapter, so LandWatch URLs fell through to the generic ("manual") provider.

---

## Bugs fixed

All five are fixed in this branch and verified live against rebuilt containers (API responses + browser).

1. **Discovery filters respected.** Search response is now filtered by the submitted query through a shared `listing_matches_filters()` helper (also used by the sample provider), so all filters take effect and the empty-state message is reachable. Persisted listings still retain their watchlist state across searches.
2. **Property Intelligence no longer 500s.** `is_stale` normalizes naive timestamps to UTC (and tolerates non-string values), so staleness checks never mix naive/aware datetimes. The tab renders coverage, red flags, opportunities, and provider diagnostics.
3. **Robust duplicate detection.** Import de-dup normalizes addresses (casefold + strip punctuation + collapse whitespace) before comparison, so punctuation-, spacing-, and capitalization-only variants are recognized as duplicates (`409`). Listing-URL de-dup is unchanged.
4. **Exports reachable.** `ExportMenu` is now a real component wired to the export endpoints and placed in the property hero (CSV / XLSX always; PDF memo appears once underwriting output exists).
5. **Correct LandWatch provenance.** Added a LandWatch domain provider so LandWatch imports are labeled `"LandWatch"`.

---

## Tests added

**Backend (`pytest`) — 40 passing (5 new):**
- `test_discovery_api.py::test_search_returns_only_listings_matching_the_submitted_filters` — non-matching filters return `[]`; price bounds trim the set (BUG 1).
- `test_property_intelligence.py::test_intelligence_endpoint_succeeds_for_persisted_property_with_acreage` — API-level regression for the intelligence 500 (BUG 2).
- `test_live_intelligence.py::test_is_stale_treats_naive_timestamps_as_utc` — unit test for the staleness fix (BUG 2).
- `test_acquisition_api.py::test_import_rejects_duplicate_addresses_differing_only_by_punctuation_or_spacing` (BUG 3).
- `test_acquisition_api.py::test_import_labels_landwatch_urls_with_their_provider` (BUG 5).

**Frontend (`vitest`) — 8 passing (3 new):**
- `export-menu.test.tsx` — CSV/XLSX always render; PDF only with underwriting (BUG 4). *(2 tests)*
- `search.test.tsx::shows the empty-results message when a filtered search returns no matches` (BUG 1, UI side).

**End-to-end (`Playwright`, newly added) — 8 passing:**
- `e2e/discovery.spec.ts` — filtered search excludes non-matches; blank search returns provider listings; watchlist add/remove; pipeline reachable. *(4 tests)*
- `e2e/pipeline.spec.ts` — import + hero exports; duplicate-by-punctuation rejection; Property Intelligence loads for an acreage-bearing property; tab navigation. *(4 tests)*

Playwright was added with the smallest necessary config (`playwright.config.ts`, `test:e2e` script, `@playwright/test` dev dep), targeting the already-running app via `E2E_BASE_URL` (default `http://localhost:5173`).

**Also verified green:** `npm run build` (tsc + vite) and `eslint --max-warnings=0`.

---

## Remaining known issues

Not addressed in this branch (out of scope for the QA fixes, or deliberate/disclosed behavior):

1. **Poor address extraction from URL-only imports.** Redfin/LandWatch/generic URLs with a trailing numeric id produce property names/addresses like `"98765"` or `"123456"` (the last path slug). This is a heuristic limitation of importing without a licensed listing feed; it is not fabricated data, but it is a visible UX wart. *(Low)*
2. **Duplicate detection does not canonicalize street suffixes.** `123 Main St` and `123 Main Street` are still treated as distinct. Left intentionally — abbreviation expansion risks false-positive merges and needs a real address-normalization library. *(Low)*
3. **Naive CSV escaping.** `exports/csv` replaces commas with spaces rather than quoting fields, so values containing commas are altered. *(Low)*
4. **Valuation is always "Unavailable"** and all providers report unconfigured/disabled — expected, by design, until licensed feeds/credentials are configured. Not a bug. *(Expected)*
5. **Discovered listings accumulate indefinitely** and there is no pagination on properties or listings; fine at current scale. *(Low)*
6. **Source is not volume-mounted in Docker.** The running app is served from built images, so changes require `docker compose up -d --build` to appear. *(Process note)*
7. **Frontend tech debt.** `PropertyDetailPage.tsx` is a large `@ts-nocheck` monolith; several placeholder components remain (`ActivityTimeline`, `InvestmentMemo`, `PropertyCard`, etc.) unused. *(Maintainability)*

---

## Suggested next priorities (ranked)

1. **Wire the e2e suite into CI** (GitHub Actions): boot API + web, run `pytest`, `vitest`, and `playwright test` on every PR. Highest leverage — the three regressions in this pass would have been caught automatically.
2. **Introduce shared, tested address normalization** used by both import de-dup and display, and extend de-dup to street-suffix canonicalization behind tests (resolves known issues #1 and #2).
3. **Harden exports:** proper CSV quoting; confirm PDF/XLSX contents against persisted values; surface an explicit "underwrite first" affordance where the PDF link is hidden (resolves #3).
4. **Audit tz-aware datetimes end to end.** The intelligence 500 was one instance of naive/aware mixing; store/read timestamps consistently as UTC-aware to prevent recurrence elsewhere.
5. **Persist and expose provider/enrichment errors in the UI** so unavailable vs. failed states are distinguishable to users (the API already returns `provider_errors`).
6. **Frontend maintainability:** split `PropertyDetailPage.tsx`, remove `@ts-nocheck`, and delete or implement the unused placeholder components.
