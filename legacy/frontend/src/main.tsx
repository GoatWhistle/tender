import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "./styles.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { Shell } from "./components/Shell";
import { Seller } from "./pages/Seller";
import { PortalShell } from "./app/portal-shell/portal-shell";
import { RootError } from "./app/root-error/root-error";
import { SellPage } from "./pages/sell-page/sell-page";
import { CatalogPage } from "./pages/catalog-page/catalog-page";
import { HomePage } from "./pages/home-page/home-page";
import { NotFoundPage } from "./pages/not-found-page/not-found-page";
import { ProductPage } from "./pages/product-page/product-page";

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [{ path: "/sell/classic", element: <Seller /> }],
  },
  {
    element: <PortalShell />,
    errorElement: <RootError />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/catalog", element: <CatalogPage /> },
      { path: "/catalog/:slug", element: <CatalogPage /> },
      { path: "/product/:id", element: <ProductPage /> },
      { path: "/sell", element: <SellPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
