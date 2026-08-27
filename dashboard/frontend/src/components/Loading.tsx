/** Shared loading indicator for pages and sections (replaces bare “Loading…” text). */

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return (
    <p className="he-loading-block" role="status" aria-live="polite" aria-busy="true">
      <span className="he-loading-dot" aria-hidden />
      {label}
    </p>
  )
}
