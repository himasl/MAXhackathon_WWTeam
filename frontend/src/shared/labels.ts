import type { SourceType, StepCategory } from "./api/types";

export const CATEGORY_LABELS: Record<StepCategory, string> = {
  REGISTRATION: "Регистрация",
  HEALTHCARE: "Здоровье",
  EDUCATION: "Учёба",
  TRANSPORT: "Транспорт",
  SOCIAL_SUPPORT: "Поддержка",
  OTHER: "Другое",
};

export const SOURCE_LABELS: Record<SourceType, string> = {
  OFFICIAL: "Официальный источник",
  MOCK: "Демонстрационные данные",
  OTHER: "Другой источник",
};

const dateFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" });
const fullDateFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

export function formatDate(value: string | null, withYear = false): string | null {
  if (!value) return null;
  return (withYear ? fullDateFormat : dateFormat).format(new Date(value));
}

export function greeting(now = new Date()): string {
  const hour = now.getHours();
  if (hour < 6) return "Доброй ночи";
  if (hour < 12) return "Доброе утро";
  if (hour < 18) return "Добрый день";
  return "Добрый вечер";
}
