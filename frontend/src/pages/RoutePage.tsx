import { type ReactNode, useState } from "react";

import { api, errorMessage } from "../shared/api/client";
import type { Route, RouteStepSummary } from "../shared/api/types";
import { CATEGORY_LABELS, formatDate, greeting } from "../shared/labels";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, Notice, ProgressBar, Screen } from "../shared/ui";
import { Illustration } from "../shared/ui/Illustration";

function plural(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

/** Encouraging headline that changes with progress. */
function headline(route: Route): { title: string; subtitle: string } {
  const { completed, total, percent } = route.progress;
  const left = total - completed;
  const tasks = `${left} ${plural(left, "дело", "дела", "дел")}`;
  if (completed === 0) {
    return { title: "Начнём с главного", subtitle: `В маршруте ${tasks}. Идите по одному шагу — так проще.` };
  }
  if (percent >= 50) {
    return { title: "Вы уже почти освоились", subtitle: `Осталось ${tasks} — начните с самого важного.` };
  }
  return { title: "Хорошее начало", subtitle: `Осталось ${tasks}. Следующий шаг уже ждёт.` };
}

function meta(step: RouteStepSummary): string {
  const parts: string[] = [];
  if (step.estimated_duration) parts.push(`займёт около ${step.estimated_duration} мин`);
  const deadline = formatDate(step.deadline);
  if (deadline) parts.push(`до ${deadline}`);
  if (!parts.length) parts.push(step.is_required ? CATEGORY_LABELS[step.category] : "по желанию");
  return parts.join(" · ");
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
  const next = route.steps.find((step) => step.id === route.next_step_id) ?? null;
  const later = route.steps.filter((step) => step.status !== "DONE" && step.id !== next?.id);
  const done = route.steps.filter((step) => step.status === "DONE");
  const { title, subtitle } = headline(route);

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
      <Illustration scene="route" progress={percent} />

      <div className="intro">
        <p className="muted">{greeting()} 👋</p>
        <h1>{total === 0 ? "Всё уже в порядке" : title}</h1>
        <p className="intro__subtitle">
          {total === 0
            ? "По вашим ответам обязательных шагов не нашлось. Если что-то изменится — обновите ответы."
            : subtitle}
        </p>
        {total > 0 ? (
          <div className="progress-line">
            <ProgressBar percent={percent} />
            <span>
              {completed} из {total}
            </span>
          </div>
        ) : null}
      </div>

      {next ? (
        <button type="button" className="soft-card soft-card--main" onClick={() => onOpenStep(next.id)}>
          <span className="soft-card__eyebrow">Следующий шаг</span>
          <span className="soft-card__title">{next.title}</span>
          <span className="soft-card__meta">{meta(next)}</span>
          <span className="soft-card__hint">{next.short_description}</span>
        </button>
      ) : null}

      {later.length ? (
        <div className="soft-list">
          {later.map((step) => (
            <button
              type="button"
              key={step.id}
              className="soft-card"
              onClick={() => onOpenStep(step.id)}
            >
              <span className="soft-card__title">{step.title}</span>
              <span className="soft-card__meta">{meta(step)}</span>
            </button>
          ))}
        </div>
      ) : null}

      {done.length ? (
        <div className="done-chips" aria-label="Выполненные шаги">
          {done.map((step) => (
            <button type="button" key={step.id} className="chip" onClick={() => onOpenStep(step.id)}>
              ✓ {step.title}
            </button>
          ))}
        </div>
      ) : null}

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
