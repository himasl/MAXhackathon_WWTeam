import { useCallback, useEffect, useState } from "react";

import { NearbyPlace } from "../features/NearbyPlace";
import { api, errorMessage } from "../shared/api/client";
import type { Route, StepDetail } from "../shared/api/types";
import { CATEGORY_LABELS, SOURCE_LABELS, formatDate } from "../shared/labels";
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
              К маршруту
            </Button>
          }
        />
      </Screen>
    );
  }
  if (!step) {
    return (
      <Screen>
        <Loading text="Загружаем шаг…" />
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
            {done ? "Вернуть в работу" : "Отметить выполненным"}
          </Button>
        )
      }
    >
      <button type="button" className="back-link" onClick={onBack}>
        ‹ Маршрут
      </button>
      <div className="step-header">
        <span className="tag">{CATEGORY_LABELS[step.category]}</span>
        {done ? <span className="tag tag--done">Выполнено</span> : null}
        {!step.is_required ? <span className="tag">По желанию</span> : null}
      </div>
      <h1>{step.title}</h1>
      <p className="lead">{step.short_description}</p>

      {actionError ? <Notice tone="error">{actionError}</Notice> : null}

      <Section title="Почему этот шаг появился?">
        <p>{step.reason}</p>
      </Section>

      <Section title="Что сделать">
        <ol className="list">
          {actions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
        {step.estimated_duration ? (
          <p className="muted">Займёт примерно {step.estimated_duration} мин.</p>
        ) : null}
      </Section>

      {step.documents.length > 0 ? (
        <Section title="Документы">
          <ul className="documents">
            {step.documents.map((document) => (
              <li key={document.code}>
                <span className="documents__title">
                  {document.title}
                  {!document.required ? <span className="muted"> — если есть</span> : null}
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
        <Section title="Куда обратиться">
          <p>{step.location}</p>
          <NearbyPlace location={step.location} regionTitle={regionTitle} />
        </Section>
      ) : null}

      {deadline && !done ? (
        <Section title="Рекомендуемый срок">
          <p>До {deadline}</p>
          <p className="muted">
            Срок рассчитан сервисом как рекомендация и не является юридическим требованием.
          </p>
          <Button variant="secondary" onClick={addToCalendar}>
            Добавить в календарь
          </Button>
          {calendarError ? <Notice tone="error">{calendarError}</Notice> : null}
        </Section>
      ) : null}

      <Section title="Источник">
        {step.sources.map((source) => (
          <div key={source.id} className={`source source--${source.source_type.toLowerCase()}`}>
            <span className="source__type">{SOURCE_LABELS[source.source_type]}</span>
            <strong>{source.title}</strong>
            <span className="muted">{source.organization}</span>
            {source.checked_at ? (
              <span className="muted">Проверено: {formatDate(source.checked_at, true)}</span>
            ) : null}
            {source.source_type === "MOCK" ? (
              <span className="muted">
                Демонстрационные данные: официальный источник для этого шага ещё не внесён.
              </span>
            ) : (
              <Button variant="secondary" onClick={() => maxBridge.openLink(source.url)}>
                Открыть официальный источник
              </Button>
            )}
          </div>
        ))}
      </Section>
    </Screen>
  );
}
