import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { api, unwrap } from "@/shared/api/client"
import type { components } from "@/shared/api/schema.gen"
import type { Extra, RagSession, Search } from "./types"

export function useRagWorkflow() {
  const [search, setSearch] = useState<Search | null>(null)
  const [session, setSession] = useState<RagSession | null>(null)
  const [draft, setDraft] = useState("")
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [verdict, setVerdict] = useState<components["schemas"]["VerdictOut"] | null>(null)
  const [automatic, setAutomatic] = useState(true)
  const [operation, setOperation] = useState("checking")
  const task = useMutation({ mutationFn: (action: () => Promise<void>) => action(), retry: false })
  function run(name: string, action: () => Promise<void>) {
    if (task.isPending) return
    setOperation(name)
    task.mutate(action)
  }
  async function retrieve(value: Search) {
    setOperation("searching")
    const params = { path: { search_id: value.id } }
    const candidates = unwrap(await api.POST("/searches/{search_id}/candidates", { params }))
    setSearch(candidates)
    setOperation("ranking")
    setSearch(unwrap(await api.POST("/searches/{search_id}/rerank", { params })))
  }
  function submit() {
    if (!draft.trim()) return
    run("checking", async () => {
      setAutomatic(true)
      setSession(null)
      setResult(null)
      const value = unwrap(await api.POST("/searches", { body: { description: draft.trim() } }))
      setSearch(value)
      if (!value.fixes.length && !value.issues.length) await retrieve(value)
    })
  }
  function confirm() {
    if (!search) return
    if (draft.trim() !== search.description) {
      submit()
      return
    }
    setDraft(search.corrected)
    run("searching", () => retrieve(search))
  }
  function choose(code: string, auto = false) {
    if (!search) return
    run("selecting", async () => {
      setSession(
        unwrap(
          await api.POST("/searches/{search_id}/select", {
            params: { path: { search_id: search.id } },
            body: { code, automatic: auto },
          }),
        ),
      )
      setVerdict(null)
      setDraft("")
    })
  }
  function answer(body: { option: number } | { text: string }) {
    if (!session) return
    run("answering", async () =>
      setSession(
        unwrap(
          await api.POST("/sessions/{session_id}/answer", {
            params: { path: { session_id: session.id } },
            body,
          }),
        ),
      ),
    )
  }
  function pick(code: string) {
    if (!session) return
    run("selecting", async () =>
      setSession(
        unwrap(
          await api.POST("/sessions/{session_id}/pick", {
            params: { path: { session_id: session.id } },
            body: { code },
          }),
        ),
      ),
    )
  }
  function values(name: string, selected: string[]) {
    if (!session) return
    run("updating", async () =>
      setSession(
        unwrap(
          await api.PATCH("/sessions/{session_id}/characteristics", {
            params: { path: { session_id: session.id } },
            body: { values: { [name]: selected } },
          }),
        ),
      ),
    )
  }
  function number(name: string, value: number | null) {
    if (!session) return
    run("updating", async () =>
      setSession(
        unwrap(
          await api.PUT("/sessions/{session_id}/characteristics/number", {
            params: { path: { session_id: session.id } },
            body: { name, value },
          }),
        ),
      ),
    )
  }
  function describe(text: string, done: () => void) {
    if (!session || !text.trim()) return
    run("answering", async () => {
      const updated = unwrap(
        await api.POST("/sessions/{session_id}/messages", {
          params: { path: { session_id: session.id } },
          body: { text },
        }),
      )
      setSession(updated)
      if (updated.stage !== "done") setResult(null)
      setVerdict(null)
      done()
    })
  }
  function addExtra(body: Extra, done: () => void) {
    if (!session) return
    run("validating", async () => {
      const response = unwrap(
        await api.POST("/sessions/{session_id}/extras", {
          params: { path: { session_id: session.id } },
          body,
        }),
      )
      setVerdict(response)
      setSession(response.session)
      if (response.accepted) done()
    })
  }
  function removeExtra(n: number) {
    if (!session) return
    run("updating", async () =>
      setSession(
        unwrap(
          await api.DELETE("/sessions/{session_id}/extras/{n}", {
            params: { path: { session_id: session.id, n } },
          }),
        ),
      ),
    )
  }
  function finish() {
    if (!session) return
    run("saving", async () => {
      const params = { path: { session_id: session.id } }
      setResult(unwrap(await api.POST("/sessions/{session_id}/finish", { params })))
      setSession(unwrap(await api.GET("/sessions/{session_id}", { params })))
    })
  }
  function reset() {
    setSearch(null)
    setSession(null)
    setResult(null)
    setDraft("")
    setVerdict(null)
    task.reset()
  }
  return {
    automatic,
    search,
    session,
    draft,
    setDraft,
    result,
    verdict,
    operation,
    busy: task.isPending,
    error: task.error,
    submit,
    confirm,
    choose,
    answer,
    pick,
    values,
    number,
    describe,
    addExtra,
    removeExtra,
    finish,
    reset,
    back: () => {
      setAutomatic(false)
      setSession(null)
      setResult(null)
      setVerdict(null)
      task.reset()
    },
    retry: () => {
      if (task.variables) task.mutate(task.variables)
    },
  }
}
export type RagWorkflowState = ReturnType<typeof useRagWorkflow>
