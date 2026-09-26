/**
 * Two interface languages: Russian (default) and English for international students.
 * Texts are written in place as pairs — t("Маршрут", "Route") — so a screen stays
 * readable in both languages. Scenario texts are translated on the server
 * (Accept-Language), so the whole key scenario is available in English.
 */

export type Lang = "ru" | "en";

const STORAGE_KEY = "marshrut.lang";

function initialLang(): Lang {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("lang");
    if (fromUrl === "en" || fromUrl === "ru") return fromUrl;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "ru") return stored;
  } catch {
    // Storage may be unavailable; fall back to Russian.
  }
  return "ru";
}

let current: Lang = typeof window === "undefined" ? "ru" : initialLang();

export function lang(): Lang {
  return current;
}

export function t(ru: string, en: string): string {
  return current === "en" ? en : ru;
}

/** Switch the language and reload, so data from the server comes in that language too. */
export function switchLang(next: Lang): void {
  current = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // The choice then lasts until the page is closed.
  }
  document.documentElement.lang = next;
  window.location.reload();
}

export function locale(): string {
  return current === "en" ? "en-GB" : "ru-RU";
}

/** Russian plural forms; English uses one/other. */
export function plural(count: number, forms: [string, string, string], en: [string, string]): string {
  if (current === "en") return count === 1 ? en[0] : en[1];
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}
