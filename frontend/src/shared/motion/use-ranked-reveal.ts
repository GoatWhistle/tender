import { type RefObject, useLayoutEffect, useRef } from "react"

export function useRankedReveal(ref: RefObject<HTMLOListElement | null>, ready: boolean) {
  const codePositions = useRef(new Map<string, number>())
  useLayoutEffect(() => {
    if (!ready && ref.current) {
      codePositions.current = new Map(
        Array.from(ref.current.children).map((row) => [
          (row as HTMLElement).dataset.id ?? "",
          row.querySelector("[data-rank-code]")?.getBoundingClientRect().left ?? 0,
        ]),
      )
    }
    if (!ready || !ref.current || matchMedia("(prefers-reduced-motion: reduce)").matches) return
    const tokens = getComputedStyle(document.documentElement)
    const duration = Number.parseFloat(tokens.getPropertyValue("--dur-rank-reveal"))
    const easing = tokens.getPropertyValue("--ease-rank-reveal").trim()
    const animations = Array.from(ref.current.children).flatMap((row, index) => {
      const arrow = row.querySelector<HTMLElement>("[data-rank-arrow]")
      const differences = row.querySelector<HTMLElement>("[data-rank-differences]")
      if (!arrow || !differences) return []
      const distance = Math.max(
        0,
        arrow.getBoundingClientRect().left - differences.getBoundingClientRect().left,
      )
      const delay = index * Number.parseFloat(tokens.getPropertyValue("--rank-reveal-stagger"))
      const code = row.querySelector<HTMLElement>("[data-rank-code]")
      const before = codePositions.current.get((row as HTMLElement).dataset.id ?? "")
      const codeAnimations =
        code && before !== undefined
          ? [
              code.animate(
                [
                  { transform: `translateX(${before - code.getBoundingClientRect().left}px)` },
                  { transform: "translateX(0)" },
                ],
                { duration, delay, easing, fill: "backwards" },
              ),
            ]
          : []
      return [
        ...codeAnimations,
        arrow.animate(
          [
            { transform: `translateX(-${distance}px)`, opacity: 0 },
            { transform: "translateX(0)", opacity: 1 },
          ],
          { duration, delay, easing, fill: "backwards" },
        ),
        differences.animate(
          [
            { opacity: 0, transform: "translateX(var(--rank-reveal-offset))" },
            { opacity: 1, transform: "translateX(0)" },
          ],
          {
            duration: Number.parseFloat(tokens.getPropertyValue("--dur-rank-details")),
            delay: delay + duration * 0.65,
            easing,
            fill: "backwards",
          },
        ),
      ]
    })
    return () => {
      for (const animation of animations) animation.cancel()
    }
  }, [ready, ref])
}
