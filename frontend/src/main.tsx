import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles.css";

function App() {
  return (
    <main>
      <section>
        <span>Маршрут</span>
        <h1>Поможем разобраться после переезда</h1>
        <p>Сервис готовится к запуску. Персональный маршрут появится на следующих этапах.</p>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

