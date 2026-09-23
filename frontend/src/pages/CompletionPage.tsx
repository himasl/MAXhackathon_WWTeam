import type { ReactNode } from "react";

import type { Route } from "../shared/api/types";
import { Button, Screen } from "../shared/ui";
import { Illustration } from "../shared/ui/Illustration";

export function CompletionPage({
  route,
  onShowRoute,
  invite,
}: {
  route: Route;
  onShowRoute: () => void;
  invite?: ReactNode;
}) {
  return (
    <Screen footer={<Button onClick={onShowRoute}>Посмотреть маршрут</Button>}>
      <Illustration scene="done" />
      <div className="intro intro--center">
        <span className="badge badge--success">
          {route.progress.completed} / {route.progress.total}
        </span>
        <h1>Маршрут завершён 🎉</h1>
        <p className="intro__subtitle">
          Все необходимые действия выполнены. Теперь можно выдохнуть и заняться учёбой.
        </p>
      </div>
      <div className="soft-card soft-card--static">
        <span className="soft-card__title">Помогите одногруппнику</span>
        <span className="soft-card__meta">у него после переезда те же дела</span>
      </div>
      <div className="actions">{invite}</div>
    </Screen>
  );
}
