import { Button, Screen } from "../shared/ui";
import { Illustration } from "../shared/ui/Illustration";

export function WelcomePage({ onStart }: { onStart: () => void }) {
  return (
    <Screen footer={<Button onClick={onStart}>Составить маршрут</Button>}>
      <Illustration scene="welcome" />
      <div className="intro">
        <span className="badge">Маршрут</span>
        <h1>Переехали на учёбу? Мы рядом</h1>
        <p className="intro__subtitle">
          Разберёмся спокойно и по порядку: регистрация, поликлиника, проезд и поддержка
          студентов — только то, что нужно именно вам.
        </p>
      </div>
      <div className="soft-list">
        <div className="soft-card soft-card--static">
          <span className="soft-card__title">Около минуты</span>
          <span className="soft-card__meta">несколько коротких вопросов о вашей ситуации</span>
        </div>
        <div className="soft-card soft-card--static">
          <span className="soft-card__title">Шаг за шагом</span>
          <span className="soft-card__meta">что сделать, какие документы взять и куда идти</span>
        </div>
        <div className="soft-card soft-card--static">
          <span className="soft-card__title">Бот напомнит</span>
          <span className="soft-card__meta">о следующем шаге и рекомендуемом сроке</span>
        </div>
      </div>
      <p className="disclaimer">
        «Маршрут» — не государственный сервис и не принимает юридически значимых решений. У
        каждого шага указан официальный источник и дата его проверки.
      </p>
    </Screen>
  );
}
