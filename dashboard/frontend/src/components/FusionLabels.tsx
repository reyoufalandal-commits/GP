import type { FusionParts } from '../utils/labelDisplay'
import { fusionParts, supervisedFamilyParts } from '../utils/labelDisplay'

function TwoLineLabel({ parts }: { parts: FusionParts }) {
  const same = parts.friendly === parts.raw
  return (
    <span className="he-fusion-count-label">
      <span className="he-fusion-count-friendly">{parts.friendly}</span>
      {!same ? <span className="he-fusion-count-tech">{parts.raw}</span> : null}
    </span>
  )
}

/** Sidebar / summary rows for fusion decision counts. */
export function FusionDecisionCountLabel({ raw }: { raw: string }) {
  return <TwoLineLabel parts={fusionParts(raw)} />
}

/** “Known attack types” breakdown — clarifies multiclass “Benign” as normal traffic. */
export function SupervisedFamilyCountLabel({ raw }: { raw: string }) {
  return <TwoLineLabel parts={supervisedFamilyParts(raw)} />
}
