import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { PortalShell } from "./app/portal-shell/portal-shell";
import { RootError } from "./app/root-error/root-error";
import { CardPage } from "./pages/card-page/card-page";
import { CatalogPage } from "./pages/catalog-page/catalog-page";
import { HomePage } from "./pages/home-page/home-page";
import { NotFoundPage } from "./pages/not-found-page/not-found-page";
import { PositionPage } from "./pages/position-page/position-page";
import { SellPage } from "./pages/sell-page/sell-page";

const router = createBrowserRouter([
  {
    element: <PortalShell />,
    errorElement: <RootError />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/sell", element: <SellPage /> },
      { path: "/cards/:id", element: <CardPage /> },
      { path: "/catalog", element: <CatalogPage /> },
      { path: "/catalog/:code", element: <PositionPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

const root = document.getElementById("root");
if (root)
  createRoot(root).render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
