import { useEffect, useState } from "react";
import { t } from "../../shared/i18n";
import { motionMs } from "../../shared/motion";
import { Button } from "../../shared/ui/button/button";
import styles from "./product-page.module.css";

export function CopyCode({ code }: { readonly code: string }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const timer = window.setTimeout(() => setDone(false), motionMs("--dur-draw") * 2);
    return () => window.clearTimeout(timer);
  }, [done]);
  return (
    <Button
      icon={done ? "check" : "products"}
      onClick={() => void navigator.clipboard?.writeText(code).then(() => setDone(true))}
    >
      <span key={String(done)} className={styles.swap} aria-live="polite">
        {t(done ? "store:product.copied" : "store:product.copy")}
      </span>
    </Button>
  );
}
