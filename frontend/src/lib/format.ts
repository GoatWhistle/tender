const rub = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });

export const price = (x: number) => `${rub.format(x)} ₽`;

// Наименования ОКЕИ → обозначения для карточки.
const UNITS: Record<string, string> = {
  Сантиметр: "см",
  Миллиметр: "мм",
  Метр: "м",
  Килограмм: "кг",
  Грамм: "г",
  "Литр; кубический дециметр": "л",
  Ватт: "Вт",
  Киловатт: "кВт",
  Вольт: "В",
  "Ампер-час": "А·ч",
  "Оборот в минуту": "об/мин",
  "Дюйм (25,4 мм)": "″",
  Штука: "шт",
  Градус: "°",
  "Квадратный метр": "м²",
  "Ньютон-метр": "Н·м",
  "Удар в минуту": "уд/мин",
  Джоуль: "Дж",
  Децибел: "дБ",
};

export const unit = (u: string | null) => (u ? (UNITS[u] ?? u) : "");

/** Запись значения с коротким обозначением: «79 Литр; кубический дециметр» → «79 л». */
export function shortLabel(label: string, u: string | null): string {
  if (!u || !label.endsWith(u)) return label;
  return `${label.slice(0, -u.length).trimEnd()} ${unit(u)}`.trim();
}

export const plural = (n: number, one: string, few: string, many: string) => {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
};
