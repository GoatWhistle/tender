import i18n from "i18next"
import { initReactI18next } from "react-i18next"
import { resources } from "./resources"

function initialLanguage() {
  try {
    return localStorage.getItem("locale") || "ru"
  } catch {
    return "ru"
  }
}
function applyLanguage(language: string) {
  document.documentElement.lang = language
  document.title = resources[language === "en" ? "en" : "ru"].portal.title
  try {
    localStorage.setItem("locale", language)
  } catch {
    return
  }
}
i18n.on("languageChanged", applyLanguage)
void i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage(),
  fallbackLng: "ru",
  defaultNS: "portal",
  interpolation: { escapeValue: false },
})

export { i18n }
