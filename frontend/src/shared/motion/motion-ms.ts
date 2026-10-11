const FALLBACK_MS = 200;

function root(): Element {
  return document.querySelector("[data-portal]") ?? document.documentElement;
}

export function motionMs(token: `--${string}`): number {
  if (typeof window === "undefined") return FALLBACK_MS;
  const raw = getComputedStyle(root()).getPropertyValue(token).trim();
  const value = Number.parseFloat(raw);
  if (Number.isNaN(value)) return FALLBACK_MS;
  return raw.endsWith("s") && !raw.endsWith("ms") ? value * 1000 : value;
}

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}
