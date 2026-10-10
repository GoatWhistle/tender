import { useTranslation } from "react-i18next"
import { BrowserRouter, Route, Routes } from "react-router"
import { CatalogPage } from "@/pages/catalog/catalog"
import { SupplierPage } from "@/pages/supplier/supplier"
import { useInputModality } from "@/shared/motion/primitives"
import { Brand } from "@/shared/ui/brand"
import { Button } from "@/shared/ui/button"
import styles from "./app.module.css"
export function App() {
  const { t, i18n } = useTranslation(["portal"])
  useInputModality()
  function toggleTheme() {
    const theme = document.documentElement.dataset.theme === "light" ? "dark" : "light"
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem("theme", theme)
    } catch {
      return
    }
  }
  return (
    <BrowserRouter>
      <div className={styles.app}>
        <header className={styles.header}>
          <Brand />
          <span className={styles.headerDivider} />
          <h1 className={styles.headerLabel}>{t("portal:support")}</h1>
          <div className={styles.controls}>
            <Button
              variant="ghost"
              icon="language"
              title={t("portal:locale")}
              aria-label={t("portal:locale")}
              onClick={() => {
                void i18n.changeLanguage(i18n.language === "ru" ? "en" : "ru")
              }}
            >
              {i18n.language.toUpperCase()}
            </Button>
            <Button
              variant="ghost"
              icon="moon"
              title={t("portal:theme")}
              aria-label={t("portal:theme")}
              onClick={toggleTheme}
            />
          </div>
        </header>
        <main className={styles.main}>
          <div className={styles.body}>
            <Routes>
              <Route path="/catalog/:code" element={<CatalogPage />} />
              <Route path="*" element={<SupplierPage />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
