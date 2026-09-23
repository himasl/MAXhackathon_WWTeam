import { type ReactNode, useState } from "react";

import { api, errorMessage } from "../shared/api/client";
import type { Route, RouteStepSummary } from "../shared/api/types";
import { CATEGORY_LABELS, formatDate, greeting } from "../shared/labels";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, Notice, ProgressBar, Screen } from "../shared/ui";

function StepIcon({ step, isNext }: { step: RouteStepSummary; isNext: boolean }) {
  if (step.status === "DONE") return <span className="step-icon step-icon--done">✓</span>;
  if (isNext) return <span className="step-icon step-icon--next">●</span>;
  return <span className="step-icon">○</span>;
}

interface Props {
  route: Route;
  onOpenStep: (stepId: string) => void;
  onEditProfile: () => void;
  invite?: ReactNode;
}

export function RoutePage({ route, onOpenStep, onEditProfile, invite }: Props) {
  const [reminder, setReminder] = useState<{ tone: "success" | "error"; text: string } | null>(
    null,
  );
  const [sending, setSending] = useState(false);
  const { completed, total, percent } = route.progress;

  const remind = async () => {
    setSending(true);
    setReminder(null);
    try {
      const result = await api.remind(route.id);
      setReminder(
        result.sent
          ? { tone: "success", text: "Напоминание отправлено в чат с ботом." }
          : {
              tone: "error",
              text: "Не получилось отправить сообщение. Напишите боту /start и попробуйте снова.",
            },
      );
      maxBridge.notify(result.sent ? "success" : "warning");
    } catch (error) {
      setReminder({ tone: "error", text: errorMessage(error) });
    } finally {
      setSending(false);
    }
  };

  return (
    <Screen>
      <p className="muted">{greeting()} 👋</p>
      <h1>Ваш маршрут</h1>

      <div className="card progress-card">
        <div className="progress-card__row">
          <strong>
            {completed} из {total} выполнено
          </strong>
          <span>{percent}%</span>
        </div>
        <ProgressBar percent={percent} />
      </div>

      {total === 0 ? (
        <div className="card">
          <p>По вашим ответам обязательных шагов не нашлось. Если что-то изменилось, обновите ответы.</p>
        </div>
      ) : (
        <ol className="steps">
          {route.steps.map((step) => {
            const isNext = step.id === route.next_step_id;
            const deadline = formatDate(step.deadline);
            return (
              <li key={step.id}>
                <button
                  type="button"
                  className={`step ${isNext ? "step--next" : ""} ${step.status === "DONE" ? "step--done" : ""}`}
                  onClick={() => onOpenStep(step.id)}
                >
                  <StepIcon step={step} isNext={isNext} />
                  <span className="step__body">
                    <span className="step__title">{step.title}</span>
                    <span className="step__meta">
                      {step.status === "DONE"
                        ? "Выполнено"
                        : isNext
                          ? "Следующий шаг"
                          : CATEGORY_LABELS[step.category]}
                      {step.status !== "DONE" && deadline ? ` · желательно до ${deadline}` : ""}
                      {!step.is_required ? " · по желанию" : ""}
                    </span>
                    {isNext ? <span className="step__hint">{step.short_description}</span> : null}
                  </span>
                  <span className="step__chevron" aria-hidden>
                    ›
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}

      <div className="actions">
        {route.next_step_id ? (
          <Button variant="secondary" onClick={remind} loading={sending}>
            Напомнить о следующем шаге в MAX
          </Button>
        ) : null}
        {reminder ? <Notice tone={reminder.tone}>{reminder.text}</Notice> : null}
        {invite}
        <Button variant="ghost" onClick={onEditProfile}>
          Изменить ответы и пересобрать маршрут
        </Button>
      </div>
    </Screen>
  );
}
