import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownReaderProps = {
  /** Markdown source (e.g. LLM incident report). */
  markdown: string
  /** Extra class on the wrapper (use with `he-markdown-readme`). */
  className?: string
}

/**
 * Renders Markdown like a README: headings, lists, tables, fenced code — not a raw &lt;pre&gt; block.
 */
export function MarkdownReader({ markdown, className }: MarkdownReaderProps) {
  return (
    <div className={className ?? 'he-markdown-readme'}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
    </div>
  )
}
