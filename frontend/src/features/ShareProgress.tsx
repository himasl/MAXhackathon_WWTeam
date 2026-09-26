import { useState } from "react";

import { api, errorMessage } from "../shared/api/client";
import { t } from "../shared/i18n";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, Notice } from "../shared/ui";

/**
 * A read-only progress link for parents: they see which steps are done, and nothing else —
 * no answers, region, university or contacts. The student can switch all links off.
 */
export function ShareProgress() {
  const [link, setLink] = useState<string | null>(null);
  const [state, setState] = useState<"idle" | "busy" | "revoked">("idle");
  const [error, setError] = useState<string | null>(null);

  const share = async () => {
    setState("busy");
    setError(null);
    try {
      const { url } = await api.createShareLink();
      setLink(url);
      await maxBridge.share(
        t(
          "Как у меня дела с переездом на учёбу — здесь видно, что уже сделано:",
          "How my move for studies is going — see what's already done:",
        ),
        url,
      );
      setState("idle");
    } catch (failure) {
      setError(errorMessage(failure));
      setState("idle");
    }
  };

  const revoke = async () => {
    setState("busy");
    setError(null);
    try {
      await api.revokeShareLinks();
      setLink(null);
      setState("revoked");
    } catch (failure) {
      setError(errorMessage(failure));
      setState("idle");
    }
  };

  return (
    <div className="share-progress">
      <Button variant="secondary" onClick={share} loading={state === "busy" && !link}>
        👪 {t("Показать прогресс родителям", "Show progress to parents")}
      </Button>
      {link ? (
        <Notice tone="success">
          <span>
            {t(
              "Ссылка готова. По ней видно только, какие шаги выполнены — без ваших ответов и контактов.",
              "The link is ready. It shows only which steps are done — no answers or contacts.",
            )}
          </span>
          <span className="share-progress__link">{link}</span>
          <button type="button" className="link-button" onClick={revoke}>
            {t("Отключить все ссылки", "Turn off all links")}
          </button>
        </Notice>
      ) : null}
      {state === "revoked" ? (
        <Notice tone="info">{t("Ссылки больше не работают.", "The links no longer work.")}</Notice>
      ) : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
    </div>
  );
}
