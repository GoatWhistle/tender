import { httpApi } from "./http";
import type { StorefrontApi } from "./types";

// Мок с фикстурами грузится отдельным чанком и только когда нужен.
function lazyMock(): StorefrontApi {
  const load = () => import("./mock/mock").then((m) => m.mockApi);
  return {
    categories: () => load().then((a) => a.categories()),
    positions: (category) => load().then((a) => a.positions(category)),
    position: (code) => load().then((a) => a.position(code)),
    products: (query) => load().then((a) => a.products(query)),
    product: (id) => load().then((a) => a.product(id)),
  };
}

// VITE_API=http — настоящий бэкенд; иначе мок.
export const api: StorefrontApi = import.meta.env.VITE_API === "http" ? httpApi : lazyMock();

export * from "./types";
