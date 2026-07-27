import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ExportMenu } from '../components/ExportMenu'

afterEach(() => cleanup())

describe('ExportMenu', () => {
  it('always offers CSV and XLSX exports wired to the property endpoints', () => {
    render(<ExportMenu propertyId={7} hasUnderwriting={false} />)
    expect(screen.getByTestId('export-csv')).toHaveAttribute('href', '/api/properties/7/exports/csv')
    expect(screen.getByTestId('export-xlsx')).toHaveAttribute('href', '/api/properties/7/exports/xlsx')
    // The PDF memo requires underwriting output, so it is hidden until that exists.
    expect(screen.queryByTestId('export-pdf')).not.toBeInTheDocument()
  })

  it('offers the PDF memo export once the property has underwriting output', () => {
    render(<ExportMenu propertyId={7} hasUnderwriting={true} />)
    expect(screen.getByTestId('export-pdf')).toHaveAttribute('href', '/api/properties/7/exports/pdf')
  })
})
