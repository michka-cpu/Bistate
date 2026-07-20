// @ts-nocheck
export function ExportMenu({ propertyId }) { return <div className="export-menu"><a href={`/api/properties/${propertyId}/exports/csv`}>Export CSV</a><a href={`/api/properties/${propertyId}/exports/pdf`}>Export PDF</a><a href={`/api/properties/${propertyId}/exports/xlsx`}>Export Excel</a></div> }
