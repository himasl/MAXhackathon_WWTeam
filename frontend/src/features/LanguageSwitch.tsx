import { lang, switchLang } from "../shared/i18n";

/** Русский / English: the key scenario for international students is available in English. */
export function LanguageSwitch() {
  const current = lang();
  const next = current === "ru" ? "en" : "ru";
  return (
    <button
      type="button"
      className="lang-switch"
      onClick={() => switchLang(next)}
      lang={next}
      aria-label={current === "ru" ? "Switch to English" : "Переключить на русский"}
    >
      {current === "ru" ? "English" : "Русский"}
    </button>
  );
}
