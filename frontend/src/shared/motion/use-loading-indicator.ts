import { useEffect, useState } from "react"

export function useLoadingIndicator(busy: boolean) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (!busy) {
      setVisible(false)
      return
    }
    const tokens = getComputedStyle(document.documentElement)
    const delay = Number.parseFloat(tokens.getPropertyValue("--loading-delay"))
    const timer = window.setTimeout(() => setVisible(true), delay)
    return () => window.clearTimeout(timer)
  }, [busy])
  return busy && visible
}
