/* eslint-disable no-undef */
// @ts-nocheck
export function KpiGrid({ property }: { property: Property }) {
  const output = property.underwriting_output
  const dashboard = output?.dashboard ?? {}
  const capRate = dashboard.noi_before_debt && dashboard.purchase_price ? dashboard.noi_before_debt / dashboard.purchase_price : null
  const estimate = Boolean(property.financials_are_estimates)
  const confidence = property.confidence_score
  const lowConfidence = confidence != null && confidence < 40
  // Financial cells derived from the workbook are unreliable when core inputs are missing.
  const values = [
    ['Overall score', score(property.overall_score), 'score', false], ['Cash required', money(dashboard.total_cash_required), 'money', estimate],
    ['Cash-on-cash', percent(dashboard.cash_on_cash_return), 'return', estimate], ['IRR', percent(output?.projection.levered_irr), 'return', estimate],
    ['Cap rate', percent(capRate), 'return', estimate], ['Debt coverage', dashboard.dscr ? `${dashboard.dscr.toFixed(2)}×` : '—', 'ratio', estimate],
    ['Renovation', money(dashboard.renovation_contingency), 'money', estimate], ['Confidence', score(property.confidence_score), 'score', false],
  ]
  return <section className={`kpi-grid ${estimate ? 'kpi-estimate' : ''}`}>{values.map(([label, value, kind, flag]) => <article key={label} className={label === 'Confidence' && lowConfidence ? 'kpi-low' : ''}><span>{label}{flag ? <em className="kpi-estimate-tag"> · est</em> : null}</span><strong className={kind}>{value}</strong></article>)}</section>
}
function money(value){ return value == null ? "—" : value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }) }
function percent(value){ return value == null ? "—" : `${(value * 100).toFixed(1)}%` }
function score(value){ return value == null ? "—" : `${Math.round(value)}/100` }
