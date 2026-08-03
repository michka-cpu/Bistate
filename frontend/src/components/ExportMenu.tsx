/** Download links for a property's persisted exports.
 *
 * The API generates every export from stored values only; the PDF memo requires
 * underwriting output, so that link is offered only once it exists. */
export function ExportMenu({ propertyId, hasUnderwriting }: { propertyId: number; hasUnderwriting: boolean }) {
  const base = `/api/properties/${propertyId}/exports`
  return (
    <div className="export-menu" role="group" aria-label="Export property">
      <span className="export-label">Export</span>
      <a className="export-link" href={`${base}/csv`} data-testid="export-csv">CSV</a>
      <a className="export-link" href={`${base}/xlsx`} data-testid="export-xlsx">XLSX</a>
      {hasUnderwriting && <a className="export-link" href={`${base}/pdf`} data-testid="export-pdf">PDF</a>}
    </div>
  )
}
