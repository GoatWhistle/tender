import { flushSync } from "react-dom";
import { prefersReducedMotion } from "./motion-ms";

type Starter = (update: () => void) => unknown;

export function withViewTransition(update: () => void): void {
  const start = (document as Document & { startViewTransition?: Starter }).startViewTransition;
  const keyboard = document.documentElement.getAttribute("data-modality") === "keyboard";
  if (!start || keyboard || prefersReducedMotion()) {
    update();
    return;
  }
  start.call(document, () => flushSync(update));
}
