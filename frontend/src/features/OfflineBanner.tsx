import { useEffect, useState } from "react";

import { isOffline, onOfflineChange } from "../shared/api/client";
import { t } from "../shared/i18n";

/** A thin line on top when the route is shown from the saved offline copy. */
export function OfflineBanner() {
  const [offline, setOffline] = useState(isOffline);
  useEffect(() => onOfflineChange(setOffline), []);
  if (!offline) return null;
  return (
    <div className="offline-banner" role="status">
      {t(
        "Нет связи — показываем сохранённую версию маршрута. Отметки заработают, когда связь вернётся.",
        "No connection — showing the saved route. Marking steps works again once you're online.",
      )}
    </div>
  );
}
