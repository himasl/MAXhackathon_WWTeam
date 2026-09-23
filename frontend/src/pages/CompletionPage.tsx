import type { ReactNode } from "react";

import type { Route } from "../shared/api/types";
import { Button, Screen } from "../shared/ui";

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
      <div className="hero hero--center">
        <div className="hero__emoji" aria-hidden>
          🎉
        </div>
        <h1>Маршрут завершён</h1>
        <p className="lead">Все необходимые действия из вашего маршрута выполнены.</p>
        <p className="counter">
          {route.progress.completed} / {route.progress.total}
        </p>
        <p className="muted">Помогите одногруппнику: у него те же дела после переезда.</p>
        <div className="actions">{invite}</div>
      </div>
    </Screen>
  );
}
