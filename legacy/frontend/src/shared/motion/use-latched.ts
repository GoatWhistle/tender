import { useRef, type ReactNode } from "react";

export function useLatched(value: ReactNode, keep: boolean): ReactNode {
  const last = useRef<ReactNode>(value);
  if (value !== null && value !== undefined && value !== false) last.current = value;
  return keep ? last.current : value;
}
