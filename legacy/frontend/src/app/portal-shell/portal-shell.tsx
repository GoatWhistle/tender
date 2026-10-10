import "../../shared/styles/global.css";
import { useEffect, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { LocaleSwitch } from "../../features/locale-switch";
import { ThemeSwitch } from "../../features/theme-switch";
import { useInputModality } from "../../shared/hooks/use-input-modality";
import { useScrollActivity } from "../../shared/hooks/use-scroll-activity";
import { LocaleProvider, t } from "../../shared/i18n";
import { ThemeProvider } from "../../shared/theme";
import logo from "../../shared/assets/portal-logo.svg";
import styles from "./portal-shell.module.css";

function Frame({ children }: { readonly children: ReactNode }) {
  const { pathname } = useLocation();
  useScrollActivity();
  useInputModality();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return (
    <div data-portal className={styles.shell}>
      <a className={styles.skip} href="#portal-main">
        {t("common:portal.skip")}
      </a>
      <header className={styles.header}>
        <Link to="/" className={styles.logo} aria-label={t("common:portal.logo")}>
          <img src={logo} alt="" width={180} height={40} />
        </Link>
        <nav className={styles.nav} aria-label={t("common:nav.label")}>
          <NavLink to="/catalog" className={styles.link}>
            {t("common:nav.catalog")}
          </NavLink>
          <NavLink to="/sell" className={styles.link}>
            {t("common:nav.sell")}
          </NavLink>
        </nav>
        <div className={styles.settings} role="group" aria-label={t("common:settings")}>
          <LocaleSwitch />
          <ThemeSwitch />
        </div>
      </header>
      <main id="portal-main" className={styles.main} tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}

export function PortalShell({ children }: { readonly children?: ReactNode }) {
  return (
    <ThemeProvider>
      <LocaleProvider>
        {(locale) => <Frame key={locale}>{children ?? <Outlet />}</Frame>}
      </LocaleProvider>
    </ThemeProvider>
  );
}
