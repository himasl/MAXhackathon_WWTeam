import type { CSSProperties, ReactNode } from "react";

import type { Route } from "../shared/api/types";
import { Button, Screen } from "../shared/ui";
import { Illustration } from "../shared/ui/Illustration";

/** Staggered appearance: each block rises softly a moment after the previous one. */
const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

interface Props {
  route: Route;
  onShowRoute: () => void;
  onNewRoute: () => void;
  invite?: ReactNode;
}

export function CompletionPage({ route, onShowRoute, onNewRoute, invite }: Props) {
  return (
    <Screen
      footer={
        <div className="footer-stack reveal" style={delay(900)}>
          <Button onClick={onNewRoute}>Построить новый маршрут</Button>
          <Button variant="ghost" onClick={onShowRoute}>
            Посмотреть пройденный маршрут
          </Button>
        </div>
      }
    >
      <div className="completion">
        <div className="reveal" style={delay(0)}>
          <Illustration scene="done" />
        </div>
        <div className="intro intro--center">
          <span className="badge badge--success pop" style={delay(350)}>
            {route.progress.completed} / {route.progress.total}
          </span>
          <h1 className="reveal" style={delay(450)}>
            Маршрут завершён 🎉
          </h1>
          <p className="intro__subtitle reveal" style={delay(550)}>
            Все необходимые действия выполнены. Теперь можно выдохнуть и заняться учёбой.
          </p>
        </div>
        <div className="reveal" style={delay(700)}>
          <div className="soft-card soft-card--static">
            <span className="soft-card__title">Помогите одногруппнику</span>
            <span className="soft-card__meta">у него после переезда те же дела</span>
          </div>
          <div className="actions">{invite}</div>
        </div>
      </div>
    </Screen>
  );
}
