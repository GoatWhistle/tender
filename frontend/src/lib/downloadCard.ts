import type { CardExport } from "../api/types";

export function downloadCard(document: CardExport): void {
  const blob = new Blob([JSON.stringify(document, null, 2) + "\n"], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = `ste-${document.session_id}-r${document.revision}.json`;
  try {
    window.document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    // Браузеру нужно успеть начать чтение blob после клика.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
