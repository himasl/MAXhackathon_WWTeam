import { useState } from "react";

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
    setResult(await maxBridge.share(
      "Разбираюсь с делами после переезда на учёбу в «Маршруте» — регистрация, поликлиника, проезд. Попробуй:",
      link,
    ));
  };

  return (
    <>
      <Button variant="secondary" onClick={share}>
        Пригласить одногруппника
      </Button>
      {result === "copied" ? <Notice tone="success">Ссылка скопирована — отправьте её в чат группы.</Notice> : null}
      {result === "failed" ? (
        <Notice tone="info">
          Отправьте одногруппнику ссылку: <strong>{link}</strong>
        </Notice>
      ) : null}
    </>
  );
}
