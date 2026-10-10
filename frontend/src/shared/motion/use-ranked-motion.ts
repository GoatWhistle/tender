import { useLayoutEffect, useRef, useState } from "react"

interface Identified {
  readonly id: string
}
function motionAllowed() {
  return !matchMedia("(prefers-reduced-motion: reduce)").matches
}
function timing(token: string) {
  const style = getComputedStyle(document.documentElement)
  return {
    duration: Number.parseFloat(style.getPropertyValue(token)),
    easing: style.getPropertyValue("--ease-out").trim(),
  }
}
export function useRankedMotion<T extends Identified>(items: readonly T[], finalized: boolean) {
  const [visible, setVisible] = useState(items)
  const [phase, setPhase] = useState(finalized ? "ready" : "waiting")
  const listRef = useRef<HTMLOListElement>(null)
  const positions = useRef(new Map<string, { top: number; left: number }>())
  const latest = useRef(items)
  latest.current = items
  useLayoutEffect(() => {
    if (!finalized) {
      setVisible(items)
      setPhase("waiting")
      return
    }
    const nodes = Array.from(listRef.current?.children ?? []).filter(
      (node): node is HTMLElement => node instanceof HTMLElement,
    )
    if (!motionAllowed() || !nodes.length) {
      setVisible(items)
      setPhase("ready")
      return
    }
    const kept = new Set(items.map((item) => item.id))
    const outgoing = nodes.filter((node) => !kept.has(node.dataset.id ?? ""))
    if (!outgoing.length) {
      setVisible(items)
      setPhase("ready")
      return
    }
    setPhase("exiting")
    let cancelled = false
    const animations = outgoing.map((node) =>
      node.animate(
        [
          { transform: "translateX(0)", opacity: 1 },
          { transform: "translateX(96px)", opacity: 0 },
        ],
        {
          ...timing("--dur-rank-exit"),
          delay: timing("--dur-rank-mark").duration,
          fill: "forwards",
        },
      ),
    )
    void Promise.all(animations.map((animation) => animation.finished))
      .then(() => {
        if (cancelled) return
        positions.current = new Map(
          nodes
            .filter((node) => kept.has(node.dataset.id ?? ""))
            .map((node) => [node.dataset.id ?? "", node.getBoundingClientRect()]),
        )
        setPhase("moving")
        setVisible(latest.current)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      for (const animation of animations) animation.cancel()
    }
  }, [items, finalized])
  useLayoutEffect(() => {
    if (!visible.length || !positions.current.size) return
    const before = positions.current
    positions.current = new Map()
    const nodes = Array.from(listRef.current?.children ?? []).filter(
      (node): node is HTMLElement => node instanceof HTMLElement,
    )
    const animations = nodes.flatMap((node) => {
      const previous = before.get(node.dataset.id ?? "")
      if (previous === undefined) return []
      const current = node.getBoundingClientRect()
      const x = previous.left - current.left
      const y = previous.top - current.top
      return [
        node.animate(
          [{ transform: `translate(${x}px, ${y}px)` }, { transform: "translate(0, 0)" }],
          timing("--dur-rank-move"),
        ),
      ]
    })
    let cancelled = false
    void Promise.all(animations.map((animation) => animation.finished))
      .then(() => {
        if (!cancelled) setPhase("ready")
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      for (const animation of animations) animation.cancel()
    }
  }, [visible])
  return { visible, phase, listRef }
}
