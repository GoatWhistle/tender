import { useEffect, useRef, useState } from "react";
import { motionMs } from "./motion-ms";

export function useLoadingIndicator(
  busy: boolean,
  delayToken: `--${string}` = "--delay-spinner",
  holdToken: `--${string}` = "--hold-indicator",
): boolean {
  const [visible, setVisible] = useState(false);
  const shownAt = useRef(0);

  useEffect(() => {
    if (busy) {
      const timer = window.setTimeout(() => {
        shownAt.current = performance.now();
        setVisible(true);
      }, motionMs(delayToken));
      return () => window.clearTimeout(timer);
    }
    if (!visible) return;
    const rest = Math.max(0, motionMs(holdToken) - (performance.now() - shownAt.current));
    const timer = window.setTimeout(() => setVisible(false), rest);
    return () => window.clearTimeout(timer);
  }, [busy, visible, delayToken, holdToken]);

  return visible;
}
