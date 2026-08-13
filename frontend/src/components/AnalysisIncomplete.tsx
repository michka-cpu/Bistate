// @ts-nocheck
import { requiredInputs } from '../lib/analysis'

// Renders the explicit "analysis incomplete" state in place of default-workbook numbers.
export function AnalysisIncomplete({ property, heading = 'Analysis incomplete', context = 'scores and returns' }) {
  const needs = requiredInputs(property)
  return (
    <section className="panel analysis-incomplete">
      <div className="panel-title"><span>{heading}</span></div>
      <p>Property-specific {context} can't be produced yet. Showing the workbook's default assumptions here would misrepresent them as results for this property, so they are withheld until the required inputs exist:</p>
      <ul className="required-inputs">{needs.length ? needs.map((item) => <li key={item}>{item}</li>) : <li>Confirm the property identity and enter the asking price.</li>}</ul>
    </section>
  )
}
