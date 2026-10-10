import { useEffect, useRef, useState } from "react"
import type { RagSession } from "@/entities/rag"

export interface NarrowingStep {
  readonly label: string
  readonly before: number
  readonly after: number
}

export function useNarrowing(session: RagSession | null): {
  readonly steps: readonly NarrowingStep[]
  readonly start: number
  readonly left: number
} {
  const [steps, setSteps] = useState<readonly NarrowingStep[]>([])
  const [start, setStart] = useState(0)
  const seen = useRef<{ id: string; count: number; answered: readonly string[] } | null>(null)

  useEffect(() => {
    if (!session) {
      seen.current = null
      setSteps([])
      setStart(0)
      return
    }
    const answered = Object.keys(session.answers ?? {})
    const count = session.candidates.length
    const previous = seen.current
    seen.current = { id: session.id, count, answered }
    if (!previous || previous.id !== session.id) {
      setSteps([])
      setStart(count)
      return
    }
    const added = answered.filter((name) => !previous.answered.includes(name))
    if (!added.length) return
    setSteps((current) => [
      ...current,
      ...added.map((label) => ({ label, before: previous.count, after: count })),
    ])
  }, [session])

  return { steps, start, left: session?.candidates.length ?? 0 }
}
