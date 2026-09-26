import { useState, type CSSProperties, type ReactNode } from "react";

import type { Route } from "../shared/api/types";
import { plural, t } from "../shared/i18n";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, Notice, Screen } from "../shared/ui";
import { Illustration } from "../shared/ui/Illustration";

/** Staggered appearance: each block rises softly a moment after the previous one. */
const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

const DAY = 24 * 3600 * 1000;

export function daysToFinish(route: Route): number {
  const end = route.completed_at ? new Date(route.completed_at) : new Date();
  return Math.max(1, Math.ceil((end.getTime() - new Date(route.created_at).getTime()) / DAY));
}

interface Props {
  route: Route;
  regionTitle: string | null;
  botUrl: string | null;
  onShowRoute: () => void;
  onNewRoute: () => void;
  invite?: ReactNode;
}

export function CompletionPage({ route, regionTitle, botUrl, onShowRoute, onNewRoute, invite }: Props) {
  const [shared, setShared] = useState<"shared" | "copied" | "failed" | null>(null);
  const days = daysToFinish(route);
  const daysText = `${days} ${plural(days, ["день", "дня", "дней"], ["day", "days"])}`;
  const where = regionTitle ? t(`Регион: ${regionTitle}`, `Region: ${regionTitle}`) : null;

  const shareAchievement = async () => {
    const text = t(
      `Я закрыл все дела после переезда на учёбу за ${daysText}: ${route.progress.total} шагов в «Маршруте» ✅`,
      `I sorted out everything after moving for my studies in ${daysText}: ${route.progress.total} steps in Marshrut ✅`,
    );
    setShared(await maxBridge.share(text, botUrl ?? window.location.origin));
  };

  return (
    <Screen
      footer={
        <div className="footer-stack reveal" style={delay(900)}>
          <Button onClick={onNewRoute}>{t("Построить новый маршрут", "Build a new route")}</Button>
          <Button variant="ghost" onClick={onShowRoute}>
            {t("Посмотреть пройденный маршрут", "See the completed route")}
          </Button>
        </div>
      }
    >
      <div className="completion">
        <div className="reveal" style={delay(0)}>
          <Illustration scene="done" />
        </div>
        <div className="intro intro--center">
          <span className="badge badge--success pop" style={delay(350)}>
            {route.progress.completed} / {route.progress.total}
          </span>
          <h1 className="reveal" style={delay(450)}>
            {t("Маршрут завершён 🎉", "Route completed 🎉")}
          </h1>
          <p className="intro__subtitle reveal" style={delay(550)}>
            {t(
              "Все необходимые действия выполнены. Теперь можно выдохнуть и заняться учёбой.",
              "Everything is done. Time to breathe out and focus on your studies.",
            )}
          </p>
        </div>

        <figure className="achievement pop" style={delay(650)} aria-label={t("Достижение", "Achievement")}>
          <span className="achievement__icon" aria-hidden>
            🏅
          </span>
          <figcaption>
            <strong className="achievement__title">{t("Освоился на новом месте", "Settled in")}</strong>
            <span className="achievement__meta">
              {t(`за ${daysText}`, `in ${daysText}`)} · {route.progress.total}{" "}
              {plural(route.progress.total, ["шаг", "шага", "шагов"], ["step", "steps"])}
            </span>
            {where ? <span className="achievement__meta">{where}</span> : null}
          </figcaption>
        </figure>

        <div className="reveal actions" style={delay(750)}>
          <Button variant="secondary" onClick={shareAchievement}>
            {t("Поделиться достижением", "Share the achievement")}
          </Button>
          {shared === "copied" ? (
            <Notice tone="success">{t("Текст скопирован.", "Text copied.")}</Notice>
          ) : null}
          <div className="soft-card soft-card--static">
            <span className="soft-card__title">{t("Помогите одногруппнику", "Help a groupmate")}</span>
            <span className="soft-card__meta">
              {t("у него после переезда те же дела", "they have the same to-dos after moving")}
            </span>
          </div>
          {invite}
        </div>
      </div>
    </Screen>
  );
}
