import { Button, Screen } from "../shared/ui";

export function WelcomePage({ onStart }: { onStart: () => void }) {
  return (
    <Screen footer={<Button onClick={onStart}>Составить маршрут</Button>}>
      <div className="hero">
        <div className="hero__badge">Маршрут</div>
        <h1>Добро пожаловать 👋</h1>
        <p className="lead">Разберёмся, что нужно сделать после переезда на учёбу.</p>
        <p>
          Ответьте на несколько вопросов, и мы составим персональный маршрут действий:
          регистрация, поликлиника, проезд и меры поддержки.
        </p>
        <p className="muted">Это займёт около минуты.</p>
      </div>
      <div className="disclaimer">
        «Маршрут» — не государственный сервис и не принимает юридически значимых решений.
        У каждого шага указан официальный источник и дата его проверки.
      </div>
    </Screen>
  );
}
