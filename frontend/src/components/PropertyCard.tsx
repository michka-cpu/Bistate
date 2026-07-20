type Props = { title: string; subtitle: string; score: number }
export function PropertyCard({ title, subtitle, score }: Props) { return <article><strong>{title}</strong><span>{subtitle}</span><b>{score}</b></article> }
