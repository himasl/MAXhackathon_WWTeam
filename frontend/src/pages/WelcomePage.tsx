import { LanguageSwitch } from "../features/LanguageSwitch";
import { t } from "../shared/i18n";
import { Button, Screen } from "../shared/ui";
import { Illustration } from "../shared/ui/Illustration";

export function WelcomePage({ onStart }: { onStart: () => void }) {
  return (
    <Screen footer={<Button onClick={onStart}>{t("Составить маршрут", "Build my route")}</Button>}>
      <div className="topbar">
        <LanguageSwitch />
      </div>
      <Illustration scene="welcome" />
      <div className="intro">
        <span className="badge">{t("Маршрут", "Marshrut")}</span>
        <h1>{t("Переехали на учёбу? Мы рядом", "Moved to study? We're here to help")}</h1>
        <p className="intro__subtitle">
          {t(
            "Разберёмся спокойно и по порядку: регистрация, поликлиника, проезд и поддержка студентов — только то, что нужно именно вам.",
            "Step by step and without stress: registration, clinic, transport and student support — only what applies to you.",
          )}
        </p>
      </div>
      <ul className="soft-list" aria-label={t("Как это работает", "How it works")}>
        <li className="soft-card soft-card--static">
          <span className="soft-card__title">{t("Около минуты", "About a minute")}</span>
          <span className="soft-card__meta">
            {t("несколько коротких вопросов о вашей ситуации", "a few short questions about your situation")}
          </span>
        </li>
        <li className="soft-card soft-card--static">
          <span className="soft-card__title">{t("Шаг за шагом", "Step by step")}</span>
          <span className="soft-card__meta">
            {t("что сделать, какие документы взять и куда идти", "what to do, which documents to take and where to go")}
          </span>
        </li>
        <li className="soft-card soft-card--static">
          <span className="soft-card__title">{t("Бот напомнит", "The bot reminds you")}</span>
          <span className="soft-card__meta">
            {t("о следующем шаге и рекомендуемом сроке", "about the next step and its recommended date")}
          </span>
        </li>
      </ul>
      <p className="disclaimer">
        {t(
          "«Маршрут» — не государственный сервис и не принимает юридически значимых решений. У каждого шага указан официальный источник и дата его проверки.",
          "Marshrut is not a government service and makes no legal decisions. Every step links to an official source with the date it was checked.",
        )}
      </p>
    </Screen>
  );
}
