import type { SourceType, StepCategory, StepStatus } from "./api/types";
import { locale, t } from "./i18n";

// The language is fixed for the page's lifetime (switching reloads), so constants are fine.
export const CATEGORY_LABELS: Record<StepCategory, string> = {
  REGISTRATION: t("Регистрация", "Registration"),
  HEALTHCARE: t("Здоровье", "Health"),
  EDUCATION: t("Учёба", "Studies"),
  TRANSPORT: t("Транспорт", "Transport"),
  SOCIAL_SUPPORT: t("Поддержка", "Support"),
  OTHER: t("Другое", "Other"),
};

export const SOURCE_LABELS: Record<SourceType, string> = {
  OFFICIAL: t("Официальный источник", "Official source"),
  MOCK: t("Демонстрационные данные", "Demo data"),
  OTHER: t("Другой источник", "Other source"),
};

export const STATUS_LABELS: Record<StepStatus, string> = {
  TODO: t("Предстоит", "To do"),
  IN_PROGRESS: t("В процессе", "In progress"),
  DONE: t("Выполнено", "Done"),
  SKIPPED: t("Пропущено", "Skipped"),
};

const dateFormat = new Intl.DateTimeFormat(locale(), { day: "numeric", month: "long" });
const fullDateFormat = new Intl.DateTimeFormat(locale(), {
  day: "numeric",
  month: "long",
  year: "numeric",
});
const weekdayFormat = new Intl.DateTimeFormat(locale(), {
  weekday: "long",
  day: "numeric",
  month: "long",
});

export function formatDate(value: string | null, withYear = false): string | null {
  if (!value) return null;
  return (withYear ? fullDateFormat : dateFormat).format(new Date(value));
}

export function formatWeekday(value: Date): string {
  return weekdayFormat.format(value);
}

export function greeting(now = new Date()): string {
  const hour = now.getHours();
  if (hour < 6) return t("Доброй ночи", "Good night");
  if (hour < 12) return t("Доброе утро", "Good morning");
  if (hour < 18) return t("Добрый день", "Good afternoon");
  return t("Добрый вечер", "Good evening");
}
