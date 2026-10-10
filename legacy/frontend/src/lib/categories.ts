// Категории хакатона и их адреса в витрине.
export const CATEGORIES = [
  { name: "Одежда", slug: "odezhda", index: "01" },
  { name: "Мебель", slug: "mebel", index: "02" },
  { name: "Инструменты", slug: "instrumenty", index: "03" },
] as const;

export type CategoryName = (typeof CATEGORIES)[number]["name"];

export const bySlug = (slug?: string) => CATEGORIES.find((c) => c.slug === slug);
export const byName = (name?: string) => CATEGORIES.find((c) => c.name === name);
