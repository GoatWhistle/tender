import { useEffect, useRef, useState } from "react";
import { motionMs } from "./motion-ms";

export type PresenceState = "open" | "closing" | "closed";

export function usePresence(open: boolean, exitToken: `--${string}` = "--dur-exit"): PresenceState {
  const [state, setState] = useState<PresenceState>(open ? "open" : "closed");
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (open) {
      setState("open");
      return;
    }
    setState((s) => (s === "closed" ? s : "closing"));
    timer.current = window.setTimeout(() => setState("closed"), motionMs(exitToken));
    return () => window.clearTimeout(timer.current);
  }, [open, exitToken]);

  return state;
}
