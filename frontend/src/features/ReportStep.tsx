import { useState } from "react";

import { api, errorMessage } from "../shared/api/client";
import type { ReportKind } from "../shared/api/types";
import { t } from "../shared/i18n";
import { Button, Notice } from "../shared/ui";

const KINDS: { value: ReportKind; label: string }[] = [
  { value: "OUTDATED", label: t("Информация устарела", "The information is outdated") },
  { value: "NOT_APPLICABLE", label: t("Шаг мне не подходит", "This step doesn't apply to me") },
  { value: "OTHER", label: t("Другое", "Something else") },
];

/**
 * A quiet link under the step: «Сообщить о неточности». The note reaches the team's MAX
 * chat with the step, scenario version, region and sources, so data is fixed quickly.
 */
export function ReportStep({ routeId, stepId }: { routeId: string; stepId: string }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<ReportKind>("OUTDATED");
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  if (state === "sent") {
    return (
      <Notice tone="success">
        {t("Спасибо! Команда проверит шаг и обновит данные.", "Thank you! The team will check the step and update it.")}
      </Notice>
    );
  }
  if (!open) {
    return (
      <button type="button" className="link-button report-link" onClick={() => setOpen(true)}>
        {t("Сообщить о неточности", "Report a problem")}
      </button>
    );
  }

  const send = async () => {
    setState("sending");
    setError(null);
    try {
      await api.reportStep(routeId, stepId, kind, comment);
      setState("sent");
    } catch (failure) {
      setError(errorMessage(failure));
      setState("idle");
    }
  };

  return (
    <form
      className="report-form"
      onSubmit={(event) => {
        event.preventDefault();
        void send();
      }}
    >
      <fieldset className="report-form__kinds">
        <legend>{t("Что не так с шагом?", "What is wrong with this step?")}</legend>
        {KINDS.map((option) => (
          <label key={option.value} className="report-form__kind">
            <input
              type="radio"
              name="report-kind"
              value={option.value}
              checked={kind === option.value}
              onChange={() => setKind(option.value)}
            />
            {option.label}
          </label>
        ))}
      </fieldset>
      <label className="report-form__comment">
        <span className="muted">{t("Комментарий, если хотите", "Comment (optional)")}</span>
        <textarea
          className="input"
          rows={3}
          maxLength={500}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder={t("Например: сменился адрес или цена", "For example: the address or price changed")}
        />
      </label>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <Button type="submit" variant="secondary" loading={state === "sending"}>
        {t("Отправить", "Send")}
      </Button>
      <button type="button" className="link-button" onClick={() => setOpen(false)}>
        {t("Отмена", "Cancel")}
      </button>
    </form>
  );
}
