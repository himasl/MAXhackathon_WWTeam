import { useEffect, useState } from "react";

import { LanguageSwitch } from "../features/LanguageSwitch";
import { api } from "../shared/api/client";
import type { HelpTopic } from "../shared/api/types";
import { t } from "../shared/i18n";
import { SOURCE_LABELS } from "../shared/labels";
import { maxBridge } from "../shared/max/maxBridge";
import { Loading, Screen, Section } from "../shared/ui";

function HelpCard({ topic }: { topic: HelpTopic }) {
  return (
    <details className="help-card">
      <summary className="help-card__summary">
        <span className="help-card__title">{topic.title}</span>
      </summary>
      <div className="help-card__body">
        <p>{topic.summary}</p>
        <ol className="list">
          {topic.actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ol>
        {topic.phones.length ? (
          <div className="help-card__phones">
            {topic.phones.map((phone) => (
              <a key={phone.number} className="phone-link" href={`tel:${phone.number.replace(/[^\d+]/g, "")}`}>
                <span className="phone-link__number">{phone.number}</span>
                <span className="phone-link__label">{phone.label}</span>
              </a>
            ))}
          </div>
        ) : null}
        {topic.sources.map((source) => (
          <button
            key={source.url}
            type="button"
            className="link-button"
            onClick={() => maxBridge.openLink(source.url)}
          >
            {source.title} — {source.organization} ↗
          </button>
        ))}
      </div>
    </details>
  );
}

export function SupportPage() {
  const [topics, setTopics] = useState<HelpTopic[] | null>(null);

  useEffect(() => {
    api.getHelp().then(setTopics, () => setTopics([]));
  }, []);

  return (
    <Screen>
      <div className="topbar">
        <LanguageSwitch />
      </div>
      <h1>{t("Помощь", "Help")}</h1>

      <Section id="sos" title={t("Если что-то пошло не так", "If something went wrong")}>
        <p className="muted">
          {t(
            "Короткие инструкции на случай, когда нужно действовать быстро.",
            "Short instructions for when you need to act fast.",
          )}
        </p>
        {topics === null ? <Loading /> : topics.map((topic) => <HelpCard key={topic.code} topic={topic} />)}
      </Section>

      <Section title={t("Что такое «Маршрут»", "What is Marshrut")}>
        <p>
          {t(
            "Сервис помогает студенту, который переехал в другой регион на учёбу, понять, что нужно сделать, в каком порядке и куда обращаться.",
            "It helps students who moved to another region to study understand what to do, in what order and where to go.",
          )}
        </p>
      </Section>
      <Section title={t("Важно", "Important")}>
        <ul className="list">
          <li>{t("Сервис не является государственным.", "This is not a government service.")}</li>
          <li>
            {t(
              "Сервис не принимает юридически значимых решений и не гарантирует право на льготу.",
              "It makes no legal decisions and does not guarantee any benefit.",
            )}
          </li>
          <li>
            {t(
              "Окончательные условия всегда указаны в официальном источнике шага.",
              "The final conditions are always in the step's official source.",
            )}
          </li>
          <li>
            {t(
              "Мы не запрашиваем паспортные данные и медицинские сведения.",
              "We never ask for passport or medical data.",
            )}
          </li>
        </ul>
      </Section>
      <Section title={t("Откуда данные", "Where the data comes from")}>
        <ul className="list">
          <li>
            <strong>{SOURCE_LABELS.OFFICIAL}</strong> —{" "}
            {t(
              "ссылка на сайт госоргана или официальный портал с датой проверки.",
              "a link to a government or official website with the date it was checked.",
            )}
          </li>
          <li>
            <strong>{SOURCE_LABELS.MOCK}</strong> —{" "}
            {t(
              "демонстрационная памятка, официальный источник ещё не внесён.",
              "a demo guide; an official source has not been added yet.",
            )}
          </li>
          <li>
            <strong>{t("Рекомендуемый срок", "Recommended date")}</strong>{" "}
            {t(
              "рассчитан сервисом и не является требованием закона.",
              "is calculated by the service and is not a legal requirement.",
            )}
          </li>
        </ul>
      </Section>
      <Section title={t("Бот", "Bot")}>
        <p>
          {t("В чате с ботом:", "In the bot chat:")} <code>/next</code> —{" "}
          {t("следующий шаг", "next step")}, <code>/start</code> — {t("открыть маршрут", "open the route")}.{" "}
          {t(
            "Под напоминанием: «✅ Выполнено» отмечает шаг, «⏰ Напомнить завтра» переносит напоминание, «🚶 Уже в процессе» — отмечает, что дело начато.",
            "Buttons under a reminder: “✅ Выполнено” (done), “⏰ Напомнить завтра” (remind tomorrow), “🚶 Уже в процессе” (already on it).",
          )}
        </p>
      </Section>
    </Screen>
  );
}
