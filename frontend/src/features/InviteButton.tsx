import { useState } from "react";

import { t } from "../shared/i18n";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, Notice } from "../shared/ui";

interface Props {
  botUrl: string | null;
  universityCode: string | null;
}

/** Invite a groupmate: the bot link carries the university code for the pilot. */
export function InviteButton({ botUrl, universityCode }: Props) {
  const [result, setResult] = useState<"shared" | "copied" | "failed" | null>(null);
  if (!botUrl) return null;

  const link = universityCode ? `${botUrl}?start=${encodeURIComponent(universityCode)}` : botUrl;
  const share = async () => {
    setResult(
      await maxBridge.share(
        t(
          "Разбираюсь с делами после переезда на учёбу в «Маршруте» — регистрация, поликлиника, проезд. Попробуй:",
          "I'm sorting out my move for studies with Marshrut — registration, clinic, transport. Try it:",
        ),
        link,
      ),
    );
  };

  return (
    <>
      <Button variant="secondary" onClick={share}>
        {t("Пригласить одногруппника", "Invite a groupmate")}
      </Button>
      {result === "copied" ? (
        <Notice tone="success">
          {t("Ссылка скопирована — отправьте её в чат группы.", "Link copied — send it to your group chat.")}
        </Notice>
      ) : null}
      {result === "failed" ? (
        <Notice tone="info">
          {t("Отправьте одногруппнику ссылку:", "Send this link to your groupmate:")} <strong>{link}</strong>
        </Notice>
      ) : null}
    </>
  );
}
