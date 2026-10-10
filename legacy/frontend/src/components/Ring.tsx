// Кольцо заполненности обязательных характеристик — единственное место для цвета данных.
type Props = { filled: number; total: number; size?: number; label?: boolean };

export function Ring({ filled, total, size = 44, label = true }: Props) {
  const share = total ? filled / total : 1;
  const r = 15;
  const c = 2 * Math.PI * r;
  const tone = share === 1 ? "ring--full" : share >= 0.5 ? "ring--part" : "ring--low";
  return (
    <span
      className={`ring ${tone}`}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Обязательные характеристики: ${filled} из ${total}`}
    >
      <svg viewBox="0 0 36 36" aria-hidden="true">
        <circle className="ring__track" cx="18" cy="18" r={r} />
        <circle
          className="ring__value"
          cx="18"
          cy="18"
          r={r}
          strokeDasharray={`${c * share} ${c}`}
          transform="rotate(-90 18 18)"
        />
      </svg>
      {label && (
        <span className="ring__text" aria-hidden="true">
          {filled}/{total}
        </span>
      )}
    </span>
  );
}
