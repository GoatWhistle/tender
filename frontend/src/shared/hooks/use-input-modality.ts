import { useEffect } from "react";

const MODIFIERS = new Set(["Shift", "Control", "Alt", "Meta", "CapsLock"]);

export function useInputModality(): void {
  useEffect(() => {
    const html = document.documentElement;
    const keyboard = (e: KeyboardEvent) => {
      if (!MODIFIERS.has(e.key)) html.setAttribute("data-modality", "keyboard");
    };
    const pointer = () => html.setAttribute("data-modality", "pointer");
    window.addEventListener("keydown", keyboard, true);
    window.addEventListener("pointerdown", pointer, true);
    return () => {
      window.removeEventListener("keydown", keyboard, true);
      window.removeEventListener("pointerdown", pointer, true);
      html.removeAttribute("data-modality");
    };
  }, []);
}
