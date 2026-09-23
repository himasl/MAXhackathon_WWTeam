import { SOURCE_LABELS } from "../shared/labels";
import { Screen, Section } from "../shared/ui";

export function SupportPage() {
  return (
    <Screen>
      <h1>Поддержка</h1>
      <Section title="Что такое «Маршрут»">
        <p>
          Сервис помогает студенту, который переехал в другой регион на учёбу, понять, что
          нужно сделать, в каком порядке и куда обращаться.
        </p>
      </Section>
      <Section title="Важно">
        <ul className="list">
          <li>Сервис не является государственным.</li>
          <li>Сервис не принимает юридически значимых решений и не гарантирует право на льготу.</li>
          <li>Окончательные условия всегда указаны в официальном источнике шага.</li>
          <li>Мы не запрашиваем паспортные данные и медицинские сведения.</li>
        </ul>
      </Section>
      <Section title="Откуда данные">
        <ul className="list">
          <li>
            <strong>{SOURCE_LABELS.OFFICIAL}</strong> — ссылка на сайт госоргана или
            официальный портал с датой проверки.
          </li>
          <li>
            <strong>{SOURCE_LABELS.MOCK}</strong> — демонстрационная памятка, официальный
            источник ещё не внесён.
          </li>
          <li>
            <strong>Рекомендуемый срок</strong> рассчитан сервисом и не является требованием
            закона.
          </li>
        </ul>
      </Section>
      <Section title="Бот">
        <p>
          В чате с ботом: <code>/next</code> — следующий шаг, <code>/start</code> — открыть
          маршрут. Бот напомнит, когда приблизится рекомендуемый срок.
        </p>
      </Section>
    </Screen>
  );
}
