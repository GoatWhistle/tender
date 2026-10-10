import enCommon from "./locales/en/common.json" with { type: "json" };
import enErrors from "./locales/en/errors.json" with { type: "json" };
import enSeller from "./locales/en/seller.json" with { type: "json" };
import enStore from "./locales/en/store.json" with { type: "json" };
import common from "./locales/ru/common.json" with { type: "json" };
import errors from "./locales/ru/errors.json" with { type: "json" };
import seller from "./locales/ru/seller.json" with { type: "json" };
import store from "./locales/ru/store.json" with { type: "json" };

const ru = { common, errors, seller, store } as const;

const en = {
  common: enCommon,
  errors: enErrors,
  seller: enSeller,
  store: enStore,
} satisfies typeof ru;

export const resources = ru;

export const dictionaries = { ru, en } as const;

export type Namespace = keyof typeof ru;
