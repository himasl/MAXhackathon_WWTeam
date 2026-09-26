import { useEffect, useState } from "react";

import { api, errorMessage } from "../shared/api/client";
import type { SharedProgress } from "../shared/api/types";
import { t } from "../shared/i18n";
import { CATEGORY_LABELS, STATUS_LABELS, formatDate } from "../shared/labels";
import { ErrorState, Loading, ProgressBar, Screen } from "../shared/ui";
import { Illustration } from "../shared/ui/Illustration";

/** Public read-only page opened by a parent from the student's link (?share=...). */
export function SharedProgressPage({ token }: { token: string }) {
  const [data, setData] = useState<SharedProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getShared(token).then(setData, (failure) =>
      setError(
        failure?.status === 404
          ? t("Ссылка больше не действует. Попросите новую.", "This link no longer works. Ask for a new one.")
          : errorMessage(failure),
      ),
    );
  }, [token]);

  if (error) {
    return (
      <Screen>
        <ErrorState message={error} />
      </Screen>
    );
  }
  if (!data) {
    return (
      <Screen>
        <Loading />
      </Screen>
    );
  }

  const { completed, total, percent } = data.progress;
  const finished = data.status === "COMPLETED";
  return (
    <Screen>
      <Illustration scene={finished ? "done" : "route"} progress={percent} />
      <div className="intro">
        <span className="badge">{t("Прогресс переезда", "Moving progress")}</span>
        <h1>
          {finished
            ? t("Все дела после переезда сделаны 🎉", "Everything after the move is done 🎉")
            : t("Как идут дела после переезда", "How the move is going")}
        </h1>
        <div className="progress-line">
          <ProgressBar percent={percent} />
          <span>
            {completed} {t("из", "of")} {total}
          </span>
        </div>
      </div>
      <ul className="shared-steps">
        {data.steps.map((step) => (
          <li key={step.title} className={`shared-step shared-step--${step.status.toLowerCase()}`}>
            <span className="shared-step__mark" aria-hidden>
              {step.status === "DONE" ? "✓" : step.status === "IN_PROGRESS" ? "…" : "○"}
            </span>
            <span className="shared-step__body">
              <span className="shared-step__title">{step.title}</span>
              <span className="muted">
                {CATEGORY_LABELS[step.category]} · {STATUS_LABELS[step.status].toLowerCase()}
                {step.completed_at ? ` ${formatDate(step.completed_at)}` : ""}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <p className="disclaimer">
        {t(
          "Страница показывает только названия шагов и отметки о выполнении. Студент может отключить ссылку в любой момент.",
          "This page shows only step names and completion marks. The student can turn the link off at any time.",
        )}
      </p>
    </Screen>
  );
}
