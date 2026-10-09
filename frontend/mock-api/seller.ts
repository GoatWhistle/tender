// Мок карточки поставщика: правила на словаре КТРУ вместо моделей. Повторяет поведение,
// которое ждём от бэкенда: извлечь характеристики из описания, нормализовать единицы,
// найти ошибки, сузить кандидатов КТРУ и задать один следующий вопрос.
import type {
  Candidate,
  ExportedCard,
  Fact,
  Issue,
  Message,
  Question,
  QuestionOption,
  SessionState,
  SessionStatus,
} from "../src/api/types.ts";
import { Missing } from "./catalog.ts";

type Bound = "greater" | "greaterOrEqual" | "less" | "lessOrEqual" | null;

export type SValue = {
  code: string;
  label: string;
  unit: string | null;
  concrete: number | null;
  min: number | null;
  min_op: Bound;
  max: number | null;
  max_op: Bound;
};

export type SChar = {
  code: string;
  name: string;
  quantitative: boolean;
  required: boolean;
  values: SValue[];
};

export type SPosition = {
  code: string;
  name: string;
  category: string;
  okpd2: string;
  characteristics: SChar[];
};

export class Conflict extends Error {}

// ---------- Текст ----------

const STOP = new Set(["для", "или", "без", "при", "под", "над", "из", "на", "от", "до", "по", "с", "и", "в"]);

const norm = (s: string) => s.toLowerCase().replace(/ё/g, "е");

const stem = (w: string) => (w.length <= 4 ? w : w.slice(0, w.length - (w.length <= 6 ? 1 : 2)));

/** Слова совпадают с точностью до окончания. */
function same(a: string, b: string): boolean {
  const sa = stem(a);
  const sb = stem(b);
  if (sa === sb) return true;
  const [short, long] = sa.length <= sb.length ? [sa, sb] : [sb, sa];
  return short.length >= 4 && long.length - short.length <= 2 && long.startsWith(short);
}

const ENDINGS = [
  "ыми", "ими", "ого", "его", "ому", "ему", "ами", "ями", "ый", "ий", "ой", "ая", "яя", "ое", "ее",
  "ые", "ие", "ых", "их", "ую", "юю", "ом", "ем", "ам", "ям", "ах", "ях", "ов", "ев", "ей", "ью",
  "ия", "ии", "ь", "ю", "я", "а", "ы", "и", "е", "у", "о", "й",
];

/** Основа без окончания: отличает словоформу («мощностью») от опечатки («деревяный»). */
function root(w: string): string {
  const e = ENDINGS.find((x) => w.endsWith(x) && w.length - x.length >= 3);
  return e ? w.slice(0, -e.length) : w;
}

// Служебные слова в названиях характеристик: по ним характеристику в тексте не узнать.
const GENERIC = new Set([
  "наличие",
  "функции",
  "функция",
  "возможность",
  "работы",
  "количество",
  "тип",
  "вид",
  "максимальный",
  "максимальная",
  "минимальный",
  "минимальная",
  "обрабатываемого",
]);

type Token = { word: string; start: number; end: number };

function tokens(text: string): Token[] {
  return [...norm(text).matchAll(/[a-zа-я]+/g)].map((m) => ({
    word: m[0],
    start: m.index!,
    end: m.index! + m[0].length,
  }));
}

const keyWords = (s: string) => (norm(s).match(/[a-zа-я]+/g) ?? []).filter((w) => w.length >= 3 && !STOP.has(w));

function levenshtein(a: string, b: string): number {
  const row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let prev = row[0];
    row[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const tmp = row[j];
      row[j] = Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1));
      prev = tmp;
    }
  }
  return row[b.length];
}

const overlaps = (a: string | null, b: string | null) =>
  !!a && !!b && (a.includes(b) || b.includes(a));

const fmt = (x: number) =>
  (Number.isInteger(x) ? String(x) : String(Math.round(x * 100) / 100)).replace(".", ",");

// ---------- Единицы ----------

type Dim = { dim: string; factor: number };

const UNIT_ALIASES: Record<string, Dim> = {
  мм: { dim: "length", factor: 1 },
  см: { dim: "length", factor: 10 },
  дм: { dim: "length", factor: 100 },
  м: { dim: "length", factor: 1000 },
  г: { dim: "mass", factor: 1 },
  кг: { dim: "mass", factor: 1000 },
  вт: { dim: "power", factor: 1 },
  квт: { dim: "power", factor: 1000 },
  в: { dim: "voltage", factor: 1 },
  л: { dim: "volume", factor: 1 },
  "об/мин": { dim: "rpm", factor: 1 },
  шт: { dim: "count", factor: 1 },
};

const OKEI: Record<string, string> = {
  Миллиметр: "мм",
  Сантиметр: "см",
  Дециметр: "дм",
  Метр: "м",
  Грамм: "г",
  Килограмм: "кг",
  Ватт: "вт",
  Киловатт: "квт",
  Вольт: "в",
  "Литр; кубический дециметр": "л",
  "Оборот в минуту": "об/мин",
  Штука: "шт",
};

const DIM_NAMES: Record<string, string> = {
  length: "длины",
  mass: "массы",
  power: "мощности",
  voltage: "напряжения",
  volume: "объёма",
  rpm: "частоты вращения",
  count: "количества",
};

const SHORT: Record<string, string> = {
  мм: "мм",
  см: "см",
  дм: "дм",
  м: "м",
  г: "г",
  кг: "кг",
  вт: "Вт",
  квт: "кВт",
  в: "В",
  л: "л",
  "об/мин": "об/мин",
  шт: "шт",
};

const charUnit = (c: SChar) => c.values.find((v) => v.unit)?.unit ?? null;

function contains(v: SValue, x: number): boolean {
  if (v.concrete !== null) return Math.abs(v.concrete - x) < 1e-9;
  if (v.min === null && v.max === null) return false;
  if (v.min !== null && !(v.min_op === "greater" ? x > v.min : x >= v.min)) return false;
  if (v.max !== null && !(v.max_op === "less" ? x < v.max : x <= v.max)) return false;
  return true;
}

const NUMBER = /(\d+(?:[.,]\d+)?)\s*(об\/мин|квт|мм|см|дм|кг|вт|шт|м|г|в|л)?(?![a-zа-я])/g;

// Взаимоисключающие слова в названиях позиций: «деревянный» исключает «металлический».
const RIVALS = [
  ["деревян", "металлич", "пластмас"],
  ["мужск", "женск"],
  ["детск", "взросл"],
];

// ---------- Сессия ----------

type Pick = { code: string; label: string; source: "answer" | "edit" } | "unknown" | "removed";

type Session = {
  id: string;
  revision: number;
  texts: string[];
  chosen: string | null;
  picks: Map<string, Pick>;
  log: Message[];
  questionId: string | null;
};

type Extracted = { facts: Fact[]; issues: Issue[] };

export function createSeller(positions: SPosition[]) {
  const sessions = new Map<string, Session>();
  let seq = 0;

  const vocab = [
    ...new Set(
      positions.flatMap((p) => [
        ...keyWords(p.name),
        ...p.characteristics.flatMap((c) => [
          ...keyWords(c.name),
          ...c.values.flatMap((v) => (v.unit ? [] : keyWords(v.label))),
        ]),
      ]),
    ),
  ].filter((w) => w.length >= 5);

  /** Исправить опечатки по словарю КТРУ. */
  function correct(text: string): { text: string; issues: Issue[] } {
    const issues: Issue[] = [];
    let out = text;
    for (const t of tokens(text)) {
      if (t.word.length < 6 || /[a-z]/.test(t.word)) continue;
      if (vocab.some((v) => root(v) === root(t.word) || stem(v) === stem(t.word))) continue;
      let best: { word: string; d: number } | null = null;
      for (const v of vocab) {
        const d = levenshtein(t.word, v);
        if (d <= (t.word.length >= 8 ? 2 : 1) && (!best || d < best.d)) best = { word: v, d };
      }
      if (!best) continue;
      const orig = text.slice(t.start, t.end);
      out = out.slice(0, t.start) + best.word + out.slice(t.end);
      issues.push({
        id: `typo-${t.start}`,
        kind: "typo",
        title: `Опечатка: «${orig}»`,
        detail: `Такого слова нет в справочнике КТРУ. Похоже на «${best.word}» — прочитали так.`,
        quote: orig,
        suggestion: best.word,
        fact_key: null,
      });
    }
    return { text: out, issues };
  }

  const quoteOf = (text: string, start: number, end: number) =>
    text.slice(Math.max(0, start), Math.min(text.length, end)).trim();

  /** Характеристики по набору позиций: ключ — название характеристики. */
  function extract(text: string, scope: SPosition[]): Extracted {
    const facts = new Map<string, Fact>();
    const issues: Issue[] = [];
    const toks = tokens(text);
    const lower = norm(text);

    const chars = new Map<string, SChar[]>();
    for (const p of scope)
      for (const c of p.characteristics) chars.set(c.name, [...(chars.get(c.name) ?? []), c]);

    const findAll = (w: string) => toks.filter((t) => same(t.word, w));
    const distinct = (name: string) => keyWords(name).filter((w) => !GENERIC.has(w));
    const nameHits = (name: string) => distinct(name).flatMap(findAll);
    // слова из названий позиций («шкаф», «стол») не делают значение найденным
    const typeWords = new Set(scope.flatMap((p) => keyWords(p.name)));

    // качественные: кандидаты «характеристика → значение», затем жадно по близости к названию
    type Match = { name: string; v: SValue; hits: Token[]; score: number; dist: number };
    const matches: Match[] = [];
    for (const [name, list] of chars) {
      if (list[0].quantitative) continue;
      const labels = [...new Map(list.flatMap((c) => c.values).map((v) => [v.label, v])).values()];
      const near = nameHits(name);
      if (labels.every((v) => ["да", "нет"].includes(norm(v.label)))) {
        const words = distinct(name);
        const hits = words.map((w) => findAll(w)[0]);
        if (!words.length || hits.some((h) => !h)) continue;
        const first = Math.min(...hits.map((h) => h.start));
        const no = /(без|нет)\s+$/.test(lower.slice(Math.max(0, first - 8), first));
        const v = labels.find((x) => norm(x.label) === (no ? "нет" : "да"));
        if (v) matches.push({ name, v, hits: hits as Token[], score: 1, dist: 0 });
        continue;
      }
      for (const v of labels) {
        const words = keyWords(v.label);
        if (!words.length) continue;
        const own = words.filter((w) => ![...typeWords].some((t) => same(t, w)));
        const hits = words.flatMap((w) => findAll(w).slice(0, 1));
        const ownHits = own.flatMap((w) => findAll(w).slice(0, 1));
        // все слова значения или хотя бы половина собственных, если их несколько
        const full = hits.length === words.length && (ownHits.length > 0 || own.length === 0);
        if (!full && (words.length < 2 || ownHits.length * 2 < own.length || !ownHits.length)) continue;
        const dist = near.length
          ? Math.min(...near.flatMap((n) => hits.map((h) => Math.abs(n.start - h.start))))
          : 1000;
        matches.push({ name, v, hits, score: hits.length / words.length, dist });
      }
    }
    matches.sort((a, b) => b.score - a.score || a.dist - b.dist || b.hits.length - a.hits.length);
    const consumed = new Set<number>();
    for (const m of matches) {
      if (facts.has(m.name) || m.hits.some((h) => consumed.has(h.start))) continue;
      m.hits.forEach((h) => consumed.add(h.start));
      const start = Math.min(...m.hits.map((h) => h.start));
      const end = Math.max(...m.hits.map((h) => h.end));
      const before = lower.slice(Math.max(0, start - 4), start);
      facts.set(m.name, fact(m.name, m.v.label, m.v.code, null, null, quoteOf(text, /без\s$/.test(before) ? start - 4 : start, end)));
    }

    // «название: значение», которого нет в справочнике
    for (const [name, list] of chars) {
      if (list[0].quantitative || facts.has(name)) continue;
      const nameRe = keyWords(name).map((w) => stem(w)).join("[а-я]*\\s+");
      const m = new RegExp(`${nameRe}[а-я]*\\s*:\\s*([а-яa-z-]+)`).exec(lower);
      if (!m) continue;
      const labels = [...new Set(list.flatMap((c) => c.values.map((v) => v.label)))];
      const quote = quoteOf(text, m.index, m.index + m[0].length);
      const value = text.slice(m.index + m[0].length - m[1].length, m.index + m[0].length);
      facts.set(name, { ...fact(name, value, null, null, null, quote), state: "error", note: "Нет в справочнике" });
      issues.push({
        id: `value-${name}`,
        kind: "unknown_value",
        title: `«${name}»: значения «${value}» нет в КТРУ`,
        detail: `Допустимые значения: ${labels.slice(0, 8).join(", ")}${labels.length > 8 ? "…" : ""}.`,
        quote,
        suggestion: null,
          fact_key: name,
      });
    }

    // количественные: все отличительные слова названия перед числом, затем число [единица];
    // иначе — число с единицей, если по размерности подходит ровно одна характеристика
    const used = new Set<number>();
    const numbers = [...lower.matchAll(NUMBER)].filter((m) => !/\d[xх*×]$/.test(lower.slice(0, m.index!)));
    const quantitative = [...chars]
      .filter(([, list]) => list[0].quantitative)
      .sort(([a], [b]) => distinct(b).length - distinct(a).length);

    const place = (name: string, list: SChar[], m: RegExpMatchArray, quoteStart: number) => {
      used.add(m.index!);
      const x = Number(m[1].replace(",", "."));
      const unitText = m[2] ?? null;
      const target = charUnit(list[0]);
      const targetAlias = target ? OKEI[target] : undefined;
      const quote = quoteOf(text, quoteStart, m.index! + m[0].length);
      let value = x;
      let raw: string | null = null;
      if (unitText && targetAlias && unitText !== targetAlias) {
        const from = UNIT_ALIASES[unitText];
        const to = UNIT_ALIASES[targetAlias];
        if (from.dim !== to.dim) {
          facts.set(name, { ...fact(name, `${m[1]} ${SHORT[unitText]}`, null, target, null, quote), state: "error", note: "Не та единица" });
          issues.push({
            id: `unit-${name}`,
            kind: "unit",
            title: `«${name}»: ${SHORT[unitText]} — единица ${DIM_NAMES[from.dim]}`,
            detail: `«${name}» измеряется в единицах ${DIM_NAMES[to.dim]} (${SHORT[targetAlias]}). Проверьте число и единицу.`,
            quote,
            suggestion: null,
          fact_key: name,
          });
          return;
        }
        value = (x * from.factor) / to.factor;
        raw = `${m[1]} ${SHORT[unitText]}`;
      }
      const shown = `${fmt(value)}${targetAlias ? ` ${SHORT[targetAlias]}` : ""}`;
      const allowed = list.flatMap((c) => c.values);
      const hit = allowed.find((v) => contains(v, value));
      if (!hit) {
        facts.set(name, { ...fact(name, shown, null, target, raw, quote), state: "error", note: "Вне допустимых значений" });
        issues.push({
          id: `range-${name}`,
          kind: "range",
          title: `«${name}»: ${shown} вне допустимых значений`,
          detail: `По КТРУ допустимо: ${[...new Set(allowed.map((v) => v.label))].slice(0, 6).join("; ")}. Возможно, ошибка в числе или единице.`,
          quote,
          suggestion: null,
          fact_key: name,
        });
        return;
      }
      // открытая сверху граница: «≥ 35 мм» формально допускает и 400 мм
      if (hit.max === null && hit.min !== null && hit.min > 0 && value > hit.min * 5) {
        facts.set(name, { ...fact(name, shown, hit.code, target, raw, quote), state: "error", note: "Неправдоподобно" });
        issues.push({
          id: `implausible-${name}`,
          kind: "range",
          title: `«${name}»: ${shown} — неправдоподобно много`,
          detail: `Формально подходит под «${hit.label}», но в разы больше нижней границы. Проверьте число и единицу измерения или подтвердите значение в таблице.`,
          quote,
          suggestion: null,
          fact_key: name,
        });
        return;
      }
      facts.set(name, fact(name, shown, hit.code, target, raw, quote));
    };

    for (const [name, list] of quantitative) {
      const words = distinct(name);
      if (!words.length) continue;
      for (const m of numbers) {
        if (used.has(m.index!)) continue;
        const window = toks.filter((t) => t.end <= m.index! && m.index! - t.start < 48);
        const hits = words.map((w) => window.filter((t) => same(t.word, w)).at(-1));
        if (hits.some((h) => !h)) continue;
        const last = Math.max(...hits.map((h) => h!.end));
        // между названием и числом — только знаки и пара коротких слов
        if (m.index! - last > 16 || /\d/.test(lower.slice(last, m.index!))) continue;
        // цитата — от ближайшего к числу слова названия, без начала фразы
        const close = hits.filter((h) => m.index! - h!.start < 32);
        place(name, list, m, close.length ? Math.min(...close.map((h) => h!.start)) : m.index!);
        break;
      }
    }
    for (const m of numbers) {
      if (used.has(m.index!) || !m[2]) continue;
      const dim = UNIT_ALIASES[m[2]].dim;
      const fits = quantitative.filter(([name, list]) => {
        const u = charUnit(list[0]);
        return !facts.has(name) && u && OKEI[u] && UNIT_ALIASES[OKEI[u]].dim === dim;
      });
      if (fits.length === 1) place(fits[0][0], fits[0][1], m, m.index!);
    }

    return { facts: [...facts.values()], issues };
  }

  function fact(
    name: string,
    value: string,
    valueCode: string | null,
    unit: string | null,
    raw: string | null,
    quote: string | null,
  ): Fact {
    return {
      key: name,
      name,
      quote,
      raw,
      value,
      value_code: valueCode,
      unit,
      source: "description",
      state: "accepted",
      note: null,
    };
  }

  function retrieve(text: string) {
    const toks = tokens(text);
    const has = (w: string) => toks.some((t) => same(t.word, w));
    const scored = positions.map((p) => {
      const words = keyWords(p.name);
      const matched = words.filter(has);
      return { p, type: words.length > 0 && has(words[0]), score: matched.length, full: matched.length === words.length };
    });
    let found = scored.filter((s) => s.type);
    if (!found.length) found = scored.filter((s) => s.score > 0);
    return found.sort((a, b) => b.score - a.score);
  }

  function rivalReason(p: SPosition, text: string): string | null {
    const toks = tokens(text);
    for (const group of RIVALS) {
      const mine = group.find((g) => keyWords(p.name).some((w) => w.startsWith(g)));
      if (!mine) continue;
      const other = toks.find((t) => group.some((g) => g !== mine && t.word.startsWith(g)));
      if (other && !toks.some((t) => t.word.startsWith(mine)))
        return `В описании «${other.word}», а позиция — «${p.name}»`;
    }
    return null;
  }

  function conflictReason(p: SPosition, facts: Fact[]): string | null {
    for (const f of facts) {
      if (f.state !== "accepted") continue;
      const c = p.characteristics.find((x) => x.name === f.name);
      if (!c) continue;
      if (!c.quantitative && !c.values.some((v) => v.label === f.value))
        return `«${f.name}: ${f.value}» нет среди допустимых значений позиции`;
    }
    return null;
  }

  function analyze(s: Session): SessionState {
    const corrected = correct(s.texts.join("\n"));
    const text = corrected.text;
    const issues: Issue[] = [...corrected.issues];
    const found = retrieve(text);
    const retrieved = found.map((f) => f.p);

    // первый проход — по всем найденным позициям, чтобы исключить несовместимые
    const pre = extract(text, retrieved);
    const candidates: Candidate[] = found.map(({ p }) => {
      const reason =
        (s.chosen && s.chosen !== p.code ? "Выбрана другая позиция" : null) ??
        rivalReason(p, text) ??
        conflictReason(p, pre.facts);
      return { code: p.code, name: p.name, category: p.category, compatible: !reason, reason };
    });
    const compatible = found.filter(({ p }) => candidates.find((c) => c.code === p.code)!.compatible);

    let position: SPosition | null = null;
    if (s.chosen) position = positions.find((p) => p.code === s.chosen) ?? null;
    else if (compatible.length === 1) position = compatible[0].p;
    else {
      const full = compatible.filter((c) => c.full);
      if (full.length === 1 && compatible.every((c) => c === full[0] || c.score < full[0].score))
        position = full[0].p;
    }

    // второй проход — по выбранной позиции: коды значений именно её
    const ex = position ? extract(text, [position]) : pre;
    issues.push(...ex.issues);
    let facts = ex.facts;

    if (position) {
      const pos = position;
      // ответы и правки перекрывают извлечённое из описания
      for (const [key, pick] of s.picks) {
        if (pick === "unknown") continue;
        facts = facts.filter((f) => f.key !== key);
        if (pick === "removed") continue;
        const c = pos.characteristics.find((x) => x.name === key);
        if (!c) continue;
        facts.push({ ...fact(key, pick.label, pick.code, charUnit(c), null, null), source: pick.source });
      }
      const order = new Map(pos.characteristics.map((c, i) => [c.name, i]));
      facts.sort((a, b) => (order.get(a.key) ?? 99) - (order.get(b.key) ?? 99));
      for (const f of pre.facts)
        if (!order.has(f.key) && !facts.some((x) => x.key === f.key || overlaps(x.quote, f.quote)))
          issues.push({
            id: `foreign-${f.key}`,
            kind: "not_in_position",
            title: `«${f.name}» не относится к позиции`,
            detail: `У позиции «${pos.name}» нет характеристики «${f.name}», значение «${f.value}» в карточку не попадёт.`,
            quote: f.quote,
            suggestion: null,
            fact_key: null,
          });
    }

    if (!found.length)
      issues.push({
        id: "no-match",
        kind: "no_match",
        title: "Не удалось определить товар",
        detail:
          "Начните описание с названия товара, как в каталоге: например, «стол письменный», «шуруповерт», «халат». Затем перечислите материал, размеры и другие характеристики.",
        quote: null,
        suggestion: null,
        fact_key: null,
      });
    else if (!compatible.length)
      issues.push({
        id: "no-compatible",
        kind: "no_match",
        title: "Ни одна позиция КТРУ не подходит",
        detail:
          "Характеристики противоречат всем найденным позициям. Посмотрите причины исключения в списке кандидатов и исправьте описание или значение.",
        quote: null,
        suggestion: null,
        fact_key: null,
      });

    const filled = new Set(facts.filter((f) => f.state === "accepted").map((f) => f.key));
    const required = position?.characteristics.filter((c) => c.required) ?? [];
    const missing = required.filter((c) => !filled.has(c.name));
    const unknown = (c: SChar) => s.picks.get(c.name) === "unknown";

    let next: Question | null = null;
    if (!position && compatible.length > 1)
      next = {
        id: `q${s.revision}-position`,
        kind: "position",
        text: "Какой именно это товар?",
        hint: `Под описание подходят ${compatible.length} позиций КТРУ — выберите одну, остальные отсеются.`,
        options: compatible.slice(0, 8).map(({ p }) => ({ code: p.code, label: p.name })),
        allow_unknown: false,
      };
    else if (position) {
      const ask = missing.find((c) => !unknown(c));
      if (ask)
        next = {
          id: `q${s.revision}-${ask.code}`,
          kind: "characteristic",
          text: `${ask.name}?`,
          hint: "Обязательная характеристика позиции КТРУ: без неё карточку не опубликовать.",
          options: ask.values.slice(0, 12).map((v) => ({ code: v.code, label: v.label })),
          allow_unknown: true,
        };
    }
    s.questionId = next?.id ?? null;

    const status: SessionStatus = !compatible.length
      ? "no_match"
      : next
        ? "needs_clarification"
        : missing.length
          ? "draft"
          : "complete";

    const editable: Record<string, QuestionOption[]> = {};
    for (const c of position?.characteristics ?? [])
      editable[c.name] = c.values.map((v) => ({ code: v.code, label: v.label }));

    return {
      session_id: s.id,
      revision: s.revision,
      status,
      messages: s.log,
      facts,
      issues,
      candidates: candidates.sort((a, b) => Number(b.compatible) - Number(a.compatible)),
      candidate_counts: {
        retrieved: retrieved.length,
        compatible: compatible.length,
        excluded: retrieved.length - compatible.length,
      },
      position: position && {
        code: position.code,
        name: position.name,
        category: position.category,
        okpd2: position.okpd2,
      },
      card_complete: !!position && missing.length === 0,
      required: required.map((c) => c.name),
      missing_required: missing.map((c) => c.name),
      editable,
      next_question: next,
    };
  }

  const session = (id: string) => {
    const s = sessions.get(id);
    if (!s) throw new Missing(id);
    return s;
  };

  const bump = (s: Session) => {
    s.revision += 1;
    return analyze(s);
  };

  return {
    create(text: string): SessionState {
      const s: Session = {
        id: `s${++seq}`,
        revision: 0,
        texts: [],
        chosen: null,
        picks: new Map(),
        log: [],
        questionId: null,
      };
      sessions.set(s.id, s);
      return this.message(s.id, text);
    },

    get: (id: string) => analyze(session(id)),

    message(id: string, text: string): SessionState {
      const s = session(id);
      if (!text.trim()) throw new Conflict("Пустое описание");
      s.texts.push(text.trim());
      s.log.push({ role: "user", text: text.trim() });
      return bump(s);
    },

    answer(id: string, questionId: string, option: string | null): SessionState {
      const s = session(id);
      const state = analyze(s);
      const q = state.next_question;
      if (!q || q.id !== questionId) throw new Conflict("Вопрос устарел — обновите состояние");
      if (q.kind === "position") {
        const o = q.options.find((x) => x.code === option);
        if (!o) throw new Conflict("Нет такого варианта");
        s.chosen = o.code;
        s.log.push({ role: "user", text: `Это «${o.label}»` });
      } else {
        const name = q.text.replace(/\?$/, "");
        if (option === null) {
          s.picks.set(name, "unknown");
          s.log.push({ role: "user", text: `${name}: не знаю` });
        } else {
          const o = q.options.find((x) => x.code === option);
          if (!o) throw new Conflict("Нет такого варианта");
          s.picks.set(name, { code: o.code, label: o.label, source: "answer" });
          s.log.push({ role: "user", text: `${name}: ${o.label}` });
        }
      }
      return bump(s);
    },

    editFact(id: string, key: string, valueCode: string | null): SessionState {
      const s = session(id);
      const state = analyze(s);
      if (valueCode === null) {
        s.picks.set(key, "removed");
        s.log.push({ role: "user", text: `Удалено: ${key}` });
        return bump(s);
      }
      const o = state.editable[key]?.find((x) => x.code === valueCode);
      if (!o) throw new Conflict("Значение не из справочника позиции");
      s.picks.set(key, { code: o.code, label: o.label, source: "edit" });
      s.log.push({ role: "user", text: `${key}: ${o.label}` });
      return bump(s);
    },

    export(id: string): ExportedCard {
      const state = analyze(session(id));
      const pos = state.position ? positions.find((p) => p.code === state.position!.code) : undefined;
      return {
        draft: !state.card_complete,
        position_code: state.position?.code ?? null,
        position_name: state.position?.name ?? null,
        characteristics: state.facts
          .filter((f) => f.state === "accepted")
          .map((f) => ({
            code: pos?.characteristics.find((c) => c.name === f.key)?.code ?? f.key,
            name: f.name,
            value: f.value,
            value_code: f.value_code,
          })),
        missing_required: state.missing_required,
      };
    },
  };
}
