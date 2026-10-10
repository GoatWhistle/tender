import { getLocale } from "./locale";
import { dictionaries, resources, type Namespace } from "./resources";

type Leaves<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string
    ? `${P}${K}`
    : T[K] extends Record<string, unknown>
      ? Leaves<T[K], `${P}${K}.`>
      : never;
}[keyof T & string];

type PluralBase<K extends string> = K extends `${infer B}_one` ? B : never;

type Keys<N extends Namespace> = Leaves<(typeof resources)[N]>;

export type MessageKey = {
  [N in Namespace]: `${N}:${Keys<N> | PluralBase<Keys<N>>}`;
}[Namespace];

export type Vars = Record<string, string | number>;

const plurals = { ru: new Intl.PluralRules("ru"), en: new Intl.PluralRules("en") };
const numbers = { ru: new Intl.NumberFormat("ru"), en: new Intl.NumberFormat("en") };

function lookup(ns: Namespace, path: string): string | undefined {
  let node: unknown = dictionaries[getLocale()][ns];
  for (const part of path.split(".")) {
    if (typeof node !== "object" || node === null) return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : undefined;
}

function fill(template: string, vars: Vars): string {
  return template.replace(/\{\{\s*(\w+)(?:\s*,\s*number)?\s*\}\}/g, (_, name: string) => {
    const value = vars[name];
    if (value === undefined) return "";
    return typeof value === "number" ? numbers[getLocale()].format(value) : value;
  });
}

export function t(key: MessageKey, vars: Vars = {}): string {
  const [ns, path] = key.split(":") as [Namespace, string];
  const count = vars.count;
  const plural =
    typeof count === "number"
      ? lookup(ns, `${path}_${plurals[getLocale()].select(count)}`)
      : undefined;
  const template = plural ?? lookup(ns, path) ?? lookup(ns, `${path}_many`) ?? key;
  return fill(template, vars);
}

export function hasKey(key: string): key is MessageKey {
  const [ns, path] = key.split(":");
  return ns in resources && path !== undefined && lookup(ns as Namespace, path) !== undefined;
}
