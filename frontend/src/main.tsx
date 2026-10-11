import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { App } from "./app/app"
import "./shared/i18n/setup"
import "./shared/styles/global.css"

const queryClient = new QueryClient({
  defaultOptions: { mutations: { retry: false }, queries: { retry: 1 } },
})
const root = document.getElementById("root")
if (root)
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  )
