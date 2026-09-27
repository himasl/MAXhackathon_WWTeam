import { useState } from "react";

import { api, errorMessage } from "../shared/api/client";
import type { AskAnswer } from "../shared/api/types";
import { t } from "../shared/i18n";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, Notice } from "../shared/ui";

/**
 * «Задать вопрос по шагу»: the question goes to POST /api/v1/ask with the step. The backend
 * asks the RAG service (RAG_URL) or, without it, finds the answer in the student's route.
 */
export function AskQuestion({
  stepId,
  onOpenStep,
}: {
  stepId: string;
  onOpenStep: (stepId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        {t("Задать вопрос по шагу", "Ask about this step")}
      </Button>
    );
  }

  const send = async () => {
    if (question.trim().length < 3) {
      setError(t("Напишите вопрос чуть подробнее.", "Please write a bit more."));
      return;
    }
    setSending(true);
    setError(null);
    try {
      setAnswer(await api.ask(question.trim(), stepId));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="ask">
      <form
        className="ask__form"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <label className="ask__label" htmlFor="ask-question">
          {t("Ваш вопрос", "Your question")}
        </label>
        <textarea
          id="ask-question"
          className="input"
          rows={2}
          maxLength={500}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={t("Например: что взять с собой?", "For example: what should I bring?")}
        />
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Button type="submit" loading={sending}>
          {t("Спросить", "Ask")}
        </Button>
      </form>
      {answer ? (
        <div className="ask__answer" aria-live="polite">
          <p className="ask__text">{answer.answer}</p>
          {answer.sources.map((source) => (
            <button
              key={source.url}
              type="button"
              className="link-button"
              onClick={() => maxBridge.openLink(source.url)}
            >
              {source.title} ↗
            </button>
          ))}
          {answer.step_id && answer.step_id !== stepId ? (
            <Button variant="ghost" onClick={() => onOpenStep(answer.step_id as string)}>
              {t("Открыть этот шаг", "Open this step")}
            </Button>
          ) : null}
          <p className="muted ask__note">
            {t(
              "Ответ может быть неточным — проверяйте по официальному источнику.",
              "The answer may be inaccurate — check the official source.",
            )}
          </p>
        </div>
      ) : null}
    </div>
  );
}
