import { useCallback, useEffect, useState } from "react";

import { NearbyPlace } from "../features/NearbyPlace";
import { api, errorMessage } from "../shared/api/client";
import type { Route, StepDetail } from "../shared/api/types";
import { t } from "../shared/i18n";
import { CATEGORY_LABELS, SOURCE_LABELS, STATUS_LABELS, formatDate } from "../shared/labels";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, ErrorState, Loading, Notice, Screen, Section } from "../shared/ui";

interface Props {
  routeId: string;
  stepId: string;
  routeIsArchived: boolean;
  regionTitle: string | null;
  onRouteChanged: (route: Route, completedStepId: string | null) => void;
  onBack: () => void;
}

export function StepPage({ routeId, stepId, routeIsArchived, regionTitle, onRouteChanged, onBack }: Props) {
  const [step, setStep] = useState<StepDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [calendarError, setCalendarError] = useState<string | null>(null);

  const addToCalendar = async () => {
    setCalendarError(null);
    try {
      const { url } = await api.calendarLink(routeId, stepId);
      maxBridge.openLink(url);
    } catch (error) {
      setCalendarError(errorMessage(error));
    }
  };

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      setStep(await api.getStep(routeId, stepId));
    } catch (error) {
      setLoadError(errorMessage(error));
    }
  }, [routeId, stepId]);

  useEffect(() => {
    setStep(null);
    void load();
  }, [load]);

  const toggle = async () => {
    if (!step) return;
    setSaving(true);
    setActionError(null);
    try {
      const done = step.status === "DONE";
      const route = done
        ? await api.reopenStep(routeId, stepId)
        : await api.completeStep(routeId, stepId);
      maxBridge.notify("success");
      onRouteChanged(route, done ? null : stepId);
      if (done) await load();
    } catch (error) {
      maxBridge.notify("error");
      setActionError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  if (loadError) {
    return (
      <Screen>
        <ErrorState
          message={loadError}
          onRetry={load}
          action={
            <Button variant="ghost" onClick={onBack}>
              {t("К маршруту", "Back to route")}
            </Button>
          }
        />
      </Screen>
    );
  }
  if (!step) {
    return (
      <Screen>
        <Loading text={t("Загружаем шаг…", "Loading the step…")} />
      </Screen>
    );
  }

  const done = step.status === "DONE";
  const deadline = formatDate(step.deadline, true);
  const actions = step.full_description.split("\n").filter(Boolean);

  return (
    <Screen
      footer={
        routeIsArchived ? null : (
          <Button variant={done ? "secondary" : "primary"} onClick={toggle} loading={saving}>
            {done ? t("Вернуть в работу", "Mark as not done") : t("Отметить выполненным", "Mark as done")}
          </Button>
        )
      }
    >
      <button type="button" className="back-link" onClick={onBack}>
        ‹ {t("Маршрут", "Route")}
      </button>
      <div className="step-header">
        <span className="tag">{CATEGORY_LABELS[step.category]}</span>
        {done ? <span className="tag tag--done">{STATUS_LABELS.DONE}</span> : null}
        {step.status === "IN_PROGRESS" ? <span className="tag">{STATUS_LABELS.IN_PROGRESS}</span> : null}
        {!step.is_required ? <span className="tag">{t("По желанию", "Optional")}</span> : null}
      </div>
      <h1>{step.title}</h1>
      <p className="lead">{step.short_description}</p>

      {actionError ? <Notice tone="error">{actionError}</Notice> : null}

      <Section title={t("Почему этот шаг появился?", "Why is this step here?")}>
        <p>{step.reason}</p>
      </Section>

      <Section title={t("Что сделать", "What to do")}>
        <ol className="list">
          {actions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
        {step.estimated_duration ? (
          <p className="muted">
            {t(`Займёт примерно ${step.estimated_duration} мин.`, `Takes about ${step.estimated_duration} min.`)}
          </p>
        ) : null}
      </Section>

      {step.documents.length > 0 ? (
        <Section title={t("Документы", "Documents")}>
          <ul className="documents">
            {step.documents.map((document) => (
              <li key={document.code}>
                <span className="documents__title">
                  {document.title}
                  {!document.required ? (
                    <span className="muted"> — {t("если есть", "if you have it")}</span>
                  ) : null}
                </span>
                {document.description ? (
                  <span className="muted documents__description">{document.description}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {step.location ? (
        <Section title={t("Куда обратиться", "Where to go")}>
          <p>{step.location}</p>
          <NearbyPlace location={step.location} regionTitle={regionTitle} />
        </Section>
      ) : null}

      {deadline && !done ? (
        <Section title={t("Рекомендуемый срок", "Recommended date")}>
          <p>{t(`До ${deadline}`, `By ${deadline}`)}</p>
          <p className="muted">
            {t(
              "Срок рассчитан сервисом как рекомендация и не является юридическим требованием.",
              "The date is a recommendation calculated by the service, not a legal requirement.",
            )}
          </p>
          <Button variant="secondary" onClick={addToCalendar}>
            {t("Добавить в календарь", "Add to calendar")}
          </Button>
          {calendarError ? <Notice tone="error">{calendarError}</Notice> : null}
        </Section>
      ) : null}

      <Section title={t("Источник", "Source")}>
        {step.sources.map((source) => (
          <div key={source.id} className={`source source--${source.source_type.toLowerCase()}`}>
            <span className="source__type">{SOURCE_LABELS[source.source_type]}</span>
            <strong>{source.title}</strong>
            <span className="muted">{source.organization}</span>
            {source.checked_at ? (
              <span className="muted">
                {t("Проверено:", "Checked:")} {formatDate(source.checked_at, true)}
              </span>
            ) : null}
            {source.source_type === "MOCK" ? (
              <span className="muted">
                {t(
                  "Демонстрационные данные: официальный источник для этого шага ещё не внесён.",
                  "Demo data: an official source for this step has not been added yet.",
                )}
              </span>
            ) : (
              <Button variant="secondary" onClick={() => maxBridge.openLink(source.url)}>
                {t("Открыть официальный источник", "Open the official source")}
              </Button>
            )}
          </div>
        ))}
      </Section>
    </Screen>
  );
}
