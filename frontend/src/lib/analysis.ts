// Presentation-only gate for property-specific results. When a property's identity is
// unresolved or the critical underwriting inputs are missing, the workbook falls back to
// default assumptions that are NOT results for this property. These helpers decide when to
// withhold those numbers. They do not touch the underwriting model.

type GateProperty = { listing_incomplete?: boolean; financials_are_estimates?: boolean; missing_core_inputs?: string[] }

const LABELS: Record<string, string> = { asking_price: 'Asking price (purchase price)', annual_taxes: 'Annual taxes', acreage: 'Acreage', bedrooms: 'Bedrooms', bathrooms: 'Bathrooms', square_feet: 'Square feet' }

export function analysisIncomplete(property?: GateProperty | null): boolean {
  return Boolean(property?.listing_incomplete) || Boolean(property?.financials_are_estimates)
}

export function requiredInputs(property?: GateProperty | null): string[] {
  const needs: string[] = []
  if (property?.listing_incomplete) needs.push('A resolved street address (city, state, ZIP)')
  const missing = Array.isArray(property?.missing_core_inputs) ? property!.missing_core_inputs : []
  // Asking price is the critical input that makes financials property-specific; list it first.
  if (missing.includes('asking_price')) needs.push(LABELS.asking_price)
  missing.filter((key) => key !== 'asking_price').forEach((key) => needs.push(LABELS[key] ?? key))
  return needs
}
