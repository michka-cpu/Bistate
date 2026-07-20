// @ts-nocheck
export function PropertyGallery({ images }) { return <article className="panel"><div className="panel-title"><span>Listing gallery</span></div>{images.length ? <div className="chip-list">{images.map((image) => <a key={image} href={image} target="_blank" rel="noreferrer">Listing photo ↗</a>)}</div> : <p className="muted">No listing images available.</p>}</article> }
