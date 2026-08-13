// Shared classifier for the universal "Import & Analyze" input, used by both the
// Discovery box and the pipeline box so they behave identically.

export const SUPPORTED_HOSTS = ['zillow.com', 'realtor.com', 'redfin.com', 'landwatch.com', 'airbnb.com', 'loopnet.com']

/** Classify the input and build the import request body, or return an error. */
export function buildImportBody(raw: string): { body?: Record<string, string>; error?: string } {
  const value = raw.trim()
  if (!value) return { error: 'Enter a street address or a listing URL to analyze.' }
  if (/^https?:\/\//i.test(value) || value.startsWith('www.') || /\.[a-z]{2,}\//i.test(value)) {
    let url: URL
    try { url = new URL(value.startsWith('http') ? value : `https://${value}`) } catch { return { error: 'That looks like a URL but could not be parsed. Check for typos.' } }
    const host = url.hostname.replace(/^www\./, '')
    if (!SUPPORTED_HOSTS.some((domain) => host === domain || host.endsWith(`.${domain}`))) {
      return { error: `${host} is not a supported listing site. Paste a Zillow, Realtor, Redfin, or LandWatch URL, or a street address.` }
    }
    return { body: { listing_url: url.toString() } }
  }
  if (/^MLS[-\s#]/i.test(value) || /^[A-Z]{1,3}[-\s]?\d{4,}$/i.test(value)) return { body: { mls_number: value } }
  return { body: { raw_address: value } }
}
