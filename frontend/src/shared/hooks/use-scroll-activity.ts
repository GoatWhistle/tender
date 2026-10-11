import { useEffect } from "react";
import { motionMs } from "../motion/motion-ms";

export function useScrollActivity(): void {
  useEffect(() => {
    const html = document.documentElement;
    let timer: number | undefined;
    const idle = () => html.removeAttribute("data-scrolling");
    const onScroll = () => {
      html.setAttribute("data-scrolling", "");
      window.clearTimeout(timer);
      timer = window.setTimeout(idle, motionMs("--scrollbar-idle"));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.clearTimeout(timer);
      idle();
    };
  }, []);
}
