import type { ReactNode } from 'react'

export type DemoFlowStep = {
  /** What the user clicks or does */
  press: string
  /** What appears on screen after */
  see: string
  /** Optional next action */
  then?: string
}

type DemoFlowGuideProps = {
  title?: string
  intro?: ReactNode
  steps: DemoFlowStep[]
}

/**
 * Repeatable pattern for demos: each step is Press → See → (optional) Then.
 * Keeps reviewer-facing flows obvious without reading long paragraphs.
 */
export function DemoFlowGuide({ title = 'What to click — what happens next', intro, steps }: DemoFlowGuideProps) {
  return (
    <aside className="he-demo-flow" aria-label={title}>
      <div className="he-demo-flow-title">{title}</div>
      {intro ? <div className="he-demo-flow-intro">{intro}</div> : null}
      <ol className="he-demo-flow-steps">
        {steps.map((s, i) => (
          <li key={i}>
            <span className="he-demo-flow-line">
              <strong className="he-demo-flow-k">Press:</strong> {s.press}
            </span>
            <span className="he-demo-flow-line">
              <strong className="he-demo-flow-k">See:</strong> {s.see}
            </span>
            {s.then ? (
              <span className="he-demo-flow-line">
                <strong className="he-demo-flow-k">Then:</strong> {s.then}
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </aside>
  )
}
