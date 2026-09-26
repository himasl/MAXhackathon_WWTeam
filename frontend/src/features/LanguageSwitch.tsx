import { api } from "../shared/api/client";
import { lang, switchLang } from "../shared/i18n";

/** Русский / English: the key scenario for international students is available in English. */
export function LanguageSwitch() {
  const current = lang();
  const next = current === "ru" ? "en" : "ru";
  return (
    <button
      type="button"
      className="lang-switch"
      onClick={async () => {
        // The bot writes in the same language; before sign-in this simply fails.
        await api.setLanguage(next).catch(() => undefined);
        switchLang(next);
      }}
      lang={next}
      aria-label={current === "ru" ? "Switch to English" : "Переключить на русский"}
    >
      {current === "ru" ? "English" : "Русский"}
    </button>
  );
}
