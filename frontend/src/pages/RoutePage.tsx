import { type ReactNode, useState } from "react";

import { ShareProgress } from "../features/ShareProgress";
import { api, errorMessage } from "../shared/api/client";
import type { Route, RouteStepSummary } from "../shared/api/types";
import { plural, t } from "../shared/i18n";
import { CATEGORY_LABELS, STATUS_LABELS, formatDate, formatWeekday, greeting } from "../shared/labels";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, Notice, ProgressBar, Screen } from "../shared/ui";
import { Illustration } from "../shared/ui/Illustration";

type Mode = "list" | "days";
const MODE_KEY = "marshrut.routeMode";

function tasksText(count: number): string {
  return `${count} ${plural(count, ["дело", "дела", "дел"], ["task", "tasks"])}`;
}

/** Encouraging headline that changes with progress. */
function headline(route: Route): { title: string; subtitle: string } {
  const { completed, total, percent } = route.progress;
  const left = total - completed;
  const tasks = tasksText(left);
  if (left === 0) {
    return {
      title: t("Маршрут пройден", "Route completed"),
      subtitle: t(
        "Все дела выполнены. Если ситуация изменилась — постройте новый маршрут.",
        "Everything is done. If your situation changes, build a new route.",
      ),
    };
  }
  if (completed === 0) {
    return {
      title: t("Начнём с главного", "Let's start with the main thing"),
      subtitle: t(
        `В маршруте ${tasks}. Идите по одному шагу — так проще.`,
        `Your route has ${tasks}. Take one step at a time.`,
      ),
    };
  }
  if (percent >= 50) {
    return {
      title: t("Вы уже почти освоились", "You're almost settled in"),
      subtitle: t(`Осталось ${tasks} — начните с самого важного.`, `${tasks} left — start with the most important.`),
    };
  }
  return {
    title: t("Хорошее начало", "Good start"),
    subtitle: t(`Осталось ${tasks}. Следующий шаг уже ждёт.`, `${tasks} left. The next step is waiting.`),
  };
}

function meta(step: RouteStepSummary): string {
  const parts: string[] = [];
  if (step.status === "IN_PROGRESS") parts.push(STATUS_LABELS.IN_PROGRESS.toLowerCase());
  if (step.estimated_duration) {
    parts.push(t(`займёт около ${step.estimated_duration} мин`, `about ${step.estimated_duration} min`));
  }
  const deadline = formatDate(step.deadline);
  if (deadline) parts.push(t(`до ${deadline}`, `by ${deadline}`));
  if (!parts.length) parts.push(step.is_required ? CATEGORY_LABELS[step.category] : t("по желанию", "optional"));
  return parts.join(" · ");
}

const DAY = 24 * 3600 * 1000;

function startOfDay(value: Date): number {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
}

/** Open steps grouped into a plan by days: overdue, today, tomorrow, the week ahead, later. */
export function planByDays(
  steps: RouteStepSummary[],
  now = new Date(),
): { key: string; title: string; steps: RouteStepSummary[] }[] {
  const today = startOfDay(now);
  const groups = new Map<string, { key: string; title: string; order: number; steps: RouteStepSummary[] }>();
  const put = (key: string, title: string, order: number, step: RouteStepSummary) => {
    const group = groups.get(key) ?? { key, title, order, steps: [] };
    group.steps.push(step);
    groups.set(key, group);
  };
  for (const step of steps) {
    if (!step.deadline) {
      put("anytime", t("Когда будет время", "Whenever you have time"), 1e9, step);
      continue;
    }
    const date = new Date(step.deadline);
    const diff = Math.round((startOfDay(date) - today) / DAY);
    if (diff < 0) put("overdue", t("Срок уже прошёл", "Past the recommended date"), -1, step);
    else if (diff === 0) put("d0", t("Сегодня", "Today"), 0, step);
    else if (diff === 1) put("d1", t("Завтра", "Tomorrow"), 1, step);
    else if (diff <= 7) put(`d${diff}`, formatWeekday(date), diff, step);
    else put("later", t("Позже", "Later"), 100, step);
  }
  return [...groups.values()].sort((a, b) => a.order - b.order);
}

function readMode(): Mode {
  try {
    return window.localStorage.getItem(MODE_KEY) === "days" ? "days" : "list";
  } catch {
    return "list";
  }
}

interface Props {
  route: Route;
  onOpenStep: (stepId: string) => void;
  onEditProfile: () => void;
  onOpenChecklist: () => void;
  invite?: ReactNode;
}

export function RoutePage({ route, onOpenStep, onEditProfile, onOpenChecklist, invite }: Props) {
  const [reminder, setReminder] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [mode, setModeState] = useState<Mode>(readMode);
  const { completed, total, percent } = route.progress;
  const next = route.steps.find((step) => step.id === route.next_step_id) ?? null;
  const open = route.steps.filter((step) => step.status !== "DONE" && step.status !== "SKIPPED");
  const later = open.filter((step) => step.id !== next?.id);
  const done = route.steps.filter((step) => step.status === "DONE");
  const { title, subtitle } = headline(route);

  const setMode = (value: Mode) => {
    setModeState(value);
    try {
      window.localStorage.setItem(MODE_KEY, value);
    } catch {
      // Only a convenience.
    }
  };

  const remind = async () => {
    setSending(true);
    setReminder(null);
    try {
      const result = await api.remind(route.id);
      setReminder(
        result.sent
          ? { tone: "success", text: t("Напоминание отправлено в чат с ботом.", "Reminder sent to the bot chat.") }
          : {
              tone: "error",
              text: t(
                "Не получилось отправить сообщение. Напишите боту /start и попробуйте снова.",
                "Could not send the message. Write /start to the bot and try again.",
              ),
            },
      );
      maxBridge.notify(result.sent ? "success" : "warning");
    } catch (error) {
      setReminder({ tone: "error", text: errorMessage(error) });
    } finally {
      setSending(false);
    }
  };

  const card = (step: RouteStepSummary, main = false) => (
    <button
      type="button"
      key={step.id}
      className={`soft-card ${main ? "soft-card--main" : ""}`}
      onClick={() => onOpenStep(step.id)}
    >
      {main ? <span className="soft-card__eyebrow">{t("Следующий шаг", "Next step")}</span> : null}
      <span className="soft-card__title">{step.title}</span>
      <span className="soft-card__meta">{meta(step)}</span>
      {main ? <span className="soft-card__hint">{step.short_description}</span> : null}
    </button>
  );

  return (
    <Screen>
      <Illustration scene="route" progress={percent} />

      <div className="intro">
        <p className="muted">{greeting()} 👋</p>
        <h1>{total === 0 ? t("Всё уже в порядке", "All set") : title}</h1>
        <p className="intro__subtitle">
          {total === 0
            ? t(
                "По вашим ответам обязательных шагов не нашлось. Если что-то изменится — обновите ответы.",
                "Based on your answers there are no required steps. Update your answers if something changes.",
              )
            : subtitle}
        </p>
        {total > 0 ? (
          <div className="progress-line">
            <ProgressBar percent={percent} />
            <span>
              {completed} {t("из", "of")} {total}
            </span>
          </div>
        ) : null}
      </div>

      {open.length > 1 ? (
        <div className="segmented" role="group" aria-label={t("Вид маршрута", "Route view")}>
          <button type="button" aria-pressed={mode === "list"} onClick={() => setMode("list")}>
            {t("По порядку", "In order")}
          </button>
          <button type="button" aria-pressed={mode === "days"} onClick={() => setMode("days")}>
            {t("План по дням", "Plan by days")}
          </button>
        </div>
      ) : null}

      {mode === "days" && open.length > 1 ? (
        <div className="day-plan">
          {planByDays(open).map((group) => (
            <section key={group.key} className="day-plan__group" aria-label={group.title}>
              <h2 className="day-plan__title">{group.title}</h2>
              <div className="soft-list">{group.steps.map((step) => card(step))}</div>
            </section>
          ))}
        </div>
      ) : (
        <>
          {next ? card(next, true) : null}
          {later.length ? <div className="soft-list">{later.map((step) => card(step))}</div> : null}
        </>
      )}

      {done.length ? (
        <div className="done-chips" aria-label={t("Выполненные шаги", "Completed steps")}>
          {done.map((step) => (
            <button type="button" key={step.id} className="chip" onClick={() => onOpenStep(step.id)}>
              <span aria-hidden>✓ </span>
              {step.title}
            </button>
          ))}
        </div>
      ) : null}

      <div className="actions">
        {route.status === "COMPLETED" ? (
          <Button onClick={onEditProfile}>{t("Построить новый маршрут", "Build a new route")}</Button>
        ) : null}
        {open.length ? (
          <Button variant="secondary" onClick={onOpenChecklist}>
            🎒 {t("Что взять с собой", "What to take with you")}
          </Button>
        ) : null}
        {route.next_step_id ? (
          <Button variant="secondary" onClick={remind} loading={sending}>
            {t("Напомнить о следующем шаге в MAX", "Remind me about the next step in MAX")}
          </Button>
        ) : null}
        {reminder ? <Notice tone={reminder.tone}>{reminder.text}</Notice> : null}
        <ShareProgress />
        {invite}
        {route.status !== "COMPLETED" ? (
          <Button variant="ghost" onClick={onEditProfile}>
            {t("Изменить ответы и пересобрать маршрут", "Change answers and rebuild the route")}
          </Button>
        ) : null}
      </div>
    </Screen>
  );
}
