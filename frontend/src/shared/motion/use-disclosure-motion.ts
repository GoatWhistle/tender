import { useLayoutEffect, useRef, useState } from "react"
export function useDisclosureMotion<T extends HTMLElement = HTMLDivElement>(
  initialOpen: boolean,
  offset = "-4px",
) {
  const [open, setOpen] = useState(initialOpen)
  const [present, setPresent] = useState(initialOpen)
  const ref = useRef<T>(null)
  function toggle() {
    if (!open) setPresent(true)
    setOpen(!open)
  }
  useLayoutEffect(() => {
    const element = ref.current
    if (!present || !element) return
    if (
      matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.input === "keyboard"
    ) {
      if (!open) setPresent(false)
      return
    }
    const tokens = getComputedStyle(document.documentElement)
    const animation = element.animate(
      open
        ? [
            { opacity: 0, transform: `translateY(${offset})` },
            { opacity: 1, transform: "translateY(0)" },
          ]
        : [
            { opacity: 1, transform: "translateY(0)" },
            { opacity: 0, transform: `translateY(${offset})` },
          ],
      {
        duration: Number.parseFloat(tokens.getPropertyValue(open ? "--dur-base" : "--dur-exit")),
        easing: tokens.getPropertyValue("--ease-out").trim(),
      },
    )
    let cancelled = false
    void animation.finished
      .then(() => {
        if (!cancelled && !open) setPresent(false)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      animation.cancel()
    }
  }, [open, present, offset])
  return { ref, open, present, toggle }
}
