import { errorMessage, friendlyApiMessage } from '../api/client'

type ErrProps = { message?: string | null; error?: unknown; friendly?: boolean }

/** Shows API or client errors; prefers FastAPI `detail` when `error` is an ApiError. */
export function Err({ message, error, friendly = true }: ErrProps) {
  const text =
    message != null && message !== ''
      ? message
      : error != null
        ? friendly
          ? friendlyApiMessage(error)
          : errorMessage(error)
        : null
  if (!text) return null
  return <pre className="he-err">{text}</pre>
}

export function JsonView({ data }: { data: unknown }) {
  return <pre className="he-json">{JSON.stringify(data, null, 2)}</pre>
}
