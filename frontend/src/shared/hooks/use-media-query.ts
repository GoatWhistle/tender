import { useSyncExternalStore } from "react";

export const BREAKPOINT = {
  phone: "(max-width: 47.99rem)",
  tablet: "(max-width: 63.99rem)",
} as const;

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", notify);
      return () => list.removeEventListener("change", notify);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
