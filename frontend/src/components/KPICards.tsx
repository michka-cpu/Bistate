/* eslint-disable no-undef */
// @ts-nocheck
export function KpiGrid({ property }: { property: Property }) {
  const output = property.underwriting_output
  const dashboard = output?.dashboard ?? {}
  const capRate = dashboard.noi_before_debt && dashboard.purchase_price ? dashboard.noi_before_debt / dashboard.purchase_price : null
  const values = [
    ['Overall score', score(property.overall_score), 'score'], ['Cash required', money(dashboard.total_cash_required), 'money'],
    ['Cash-on-cash', percent(dashboard.cash_on_cash_return), 'return'], ['IRR', percent(output?.projection.levered_irr), 'return'],
    ['Cap rate', percent(capRate), 'return'], ['Debt coverage', dashboard.dscr ? `${dashboard.dscr.toFixed(2)}×` : '—', 'ratio'],
    ['Renovation', money(dashboard.renovation_contingency), 'money'], ['Confidence', score(property.confidence_score), 'score'],
  ]
  return <section className="kpi-grid">{values.map(([label, value, kind]) => <article key={label}><span>{label}</span><strong className={kind}>{value}</strong></article>)}</section>
}
function money(value){ return value == null ? "—" : value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }) }
function percent(value){ return value == null ? "—" : `${(value * 100).toFixed(1)}%` }
function score(value){ return value == null ? "—" : `${Math.round(value)}/100` }
