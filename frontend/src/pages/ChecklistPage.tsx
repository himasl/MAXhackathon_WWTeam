import { useCallback, useEffect, useState } from "react";

import { NearbyPlace } from "../features/NearbyPlace";
import { api, errorMessage } from "../shared/api/client";
import type { Checklist } from "../shared/api/types";
import { t } from "../shared/i18n";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, ErrorState, Loading, Notice, Screen } from "../shared/ui";

interface Props {
  routeId: string;
  regionTitle: string | null;
  onBack: () => void;
}

const storageKey = (routeId: string) => `marshrut.packed.${routeId}`;

function readPacked(routeId: string): Set<string> {
  try {
    return new Set(JSON.parse(window.localStorage.getItem(storageKey(routeId)) ?? "[]"));
  } catch {
    return new Set();
  }
}

/** «Что взять с собой»: documents of the open steps, grouped by where you go with them. */
export function ChecklistPage({ routeId, regionTitle, onBack }: Props) {
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [packed, setPacked] = useState<Set<string>>(() => readPacked(routeId));
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setChecklist(await api.getChecklist(routeId));
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }, [routeId]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = (key: string) => {
    const next = new Set(packed);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setPacked(next);
    try {
      window.localStorage.setItem(storageKey(routeId), JSON.stringify([...next]));
    } catch {
      // Ticks are a convenience; they simply are not remembered.
    }
  };

  const send = async () => {
    setSending(true);
    setSent(null);
    try {
      const result = await api.sendChecklist(routeId);
      setSent(
        result.sent
          ? { tone: "success", text: t("Список отправлен в чат с ботом.", "The list was sent to the bot chat.") }
          : {
              tone: "error",
              text: t(
                "Не получилось отправить. Напишите боту /start и попробуйте снова.",
                "Could not send. Write /start to the bot and try again.",
              ),
            },
      );
      maxBridge.notify(result.sent ? "success" : "warning");
    } catch (failure) {
      setSent({ tone: "error", text: errorMessage(failure) });
    } finally {
      setSending(false);
    }
  };

  const back = (
    <button type="button" className="back-link" onClick={onBack}>
      ‹ {t("Маршрут", "Route")}
    </button>
  );

  if (error) {
    return (
      <Screen>
        {back}
        <ErrorState message={error} onRetry={load} />
      </Screen>
    );
  }
  if (!checklist) {
    return (
      <Screen>
        <Loading text={t("Собираем список…", "Putting the list together…")} />
      </Screen>
    );
  }

  return (
    <Screen
      footer={
        checklist.groups.length ? (
          <Button onClick={send} loading={sending}>
            {t("Прислать список в чат MAX", "Send the list to the MAX chat")}
          </Button>
        ) : null
      }
    >
      {back}
      <h1>🎒 {t("Что взять с собой", "What to take with you")}</h1>
      <p className="lead">
        {t(
          "Документы для незакрытых шагов, собранные по местам. Отмечайте, что уже положили в папку.",
          "Documents for your open steps, grouped by place. Tick what's already in your folder.",
        )}
      </p>
      {sent ? <Notice tone={sent.tone}>{sent.text}</Notice> : null}
      {checklist.groups.length === 0 ? (
        <Notice tone="info">
          {t("Для оставшихся шагов документы не нужны.", "No documents are needed for the remaining steps.")}
        </Notice>
      ) : null}
      {checklist.groups.map((group) => (
        <section key={group.place} className="section checklist-group" aria-label={group.place}>
          <h2 className="section__title">📍 {group.place}</h2>
          <p className="muted checklist-group__steps">{group.steps.join(" · ")}</p>
          <ul className="checklist">
            {group.documents.map((document) => {
              const key = `${group.place}:${document.code}`;
              return (
                <li key={key}>
                  <label className="checklist__item">
                    <input type="checkbox" checked={packed.has(key)} onChange={() => toggle(key)} />
                    <span>
                      <span className="checklist__title">{document.title}</span>
                      {!document.required ? (
                        <span className="muted"> — {t("если есть", "if you have it")}</span>
                      ) : null}
                      {document.description ? (
                        <span className="muted checklist__description">{document.description}</span>
                      ) : null}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          <NearbyPlace location={group.place} regionTitle={regionTitle} />
        </section>
      ))}
    </Screen>
  );
}
