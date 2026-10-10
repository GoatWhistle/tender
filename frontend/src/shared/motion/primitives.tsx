import { type ReactNode, useEffect, useRef } from "react"
import styles from "./primitives.module.css"
export function Swap({
  swapKey,
  children,
}: {
  readonly swapKey: string
  readonly children: ReactNode
}) {
  return (
    <div key={swapKey} className={styles.enter} data-state="entered">
      {children}
    </div>
  )
}
export function useInputModality() {
  useEffect(() => {
    const pointer = () => {
      document.documentElement.dataset.input = "pointer"
    }
    const keyboard = () => {
      document.documentElement.dataset.input = "keyboard"
    }
    window.addEventListener("pointerdown", pointer)
    window.addEventListener("keydown", keyboard)
    return () => {
      window.removeEventListener("pointerdown", pointer)
      window.removeEventListener("keydown", keyboard)
    }
  }, [])
}
export function RerankMotion({
  children,
  leaving,
}: {
  readonly children: ReactNode
  readonly leaving: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (
      !leaving ||
      !ref.current ||
      matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.input === "keyboard"
    )
      return
    const tokens = getComputedStyle(document.documentElement)
    const animation = ref.current.animate(
      [
        { transform: "translateX(0)", opacity: 1 },
        { transform: "translateX(48px)", opacity: 0 },
      ],
      {
        duration: Number.parseFloat(tokens.getPropertyValue("--dur-exit")),
        easing: tokens.getPropertyValue("--ease-out").trim(),
        fill: "forwards",
      },
    )
    return () => animation.cancel()
  }, [leaving])
  return (
    <div ref={ref} className={styles.result} data-state={leaving ? "exiting" : "entered"}>
      {children}
    </div>
  )
}
export function Spinner() {
  return <span className={styles.spinner} aria-hidden="true" />
}
