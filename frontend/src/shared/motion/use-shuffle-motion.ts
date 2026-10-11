import { useEffect, useLayoutEffect, useRef, useState } from "react"

function token(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
function rows(list: HTMLElement | null) {
  return Array.from(list?.children ?? []).filter(
    (node): node is HTMLElement => node instanceof HTMLElement,
  )
}
function swapped(order: readonly number[]) {
  const next = [...order]
  const first = Math.floor(Math.random() * next.length)
  const offset = 1 + Math.floor(Math.random() * (next.length - 1))
  const second = (first + offset) % next.length
  const value = next[first] ?? 0
  next[first] = next[second] ?? 0
  next[second] = value
  return next
}
export function useShuffleMotion(count: number) {
  const [order, setOrder] = useState(() => Array.from({ length: count }, (_, index) => index))
  const listRef = useRef<HTMLOListElement>(null)
  const before = useRef(new Map<string, number>())
  const running = useRef<Animation[]>([])
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || count < 2) return
    const timer = window.setInterval(
      () => {
        before.current = new Map(
          rows(listRef.current).map((node) => [
            node.dataset.id ?? "",
            node.getBoundingClientRect().top,
          ]),
        )
        setOrder(swapped)
      },
      Number.parseFloat(token("--dur-shuffle-hold")),
    )
    return () => window.clearInterval(timer)
  }, [count])
  useLayoutEffect(() => {
    const previous = before.current
    if (!order.length || !previous.size) return
    before.current = new Map()
    for (const animation of running.current) animation.cancel()
    const options = {
      duration: Number.parseFloat(token("--dur-rank-move")),
      easing: token("--ease-out"),
    }
    running.current = rows(listRef.current).flatMap((node) => {
      const top = previous.get(node.dataset.id ?? "")
      const shift = top === undefined ? 0 : top - node.getBoundingClientRect().top
      if (!shift) return []
      return [
        node.animate(
          [{ transform: `translateY(${shift}px)` }, { transform: "translateY(0)" }],
          options,
        ),
      ]
    })
  }, [order])
  useEffect(
    () => () => {
      for (const animation of running.current) animation.cancel()
    },
    [],
  )
  return { order, listRef }
}
