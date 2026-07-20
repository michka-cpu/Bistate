/* eslint-disable no-unused-vars */
type Props = { value: string; onChange: (value: string) => void }
export function SearchBar({ value, onChange }: Props) { return <input aria-label="Search properties" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Search address, county, status…" /> }
