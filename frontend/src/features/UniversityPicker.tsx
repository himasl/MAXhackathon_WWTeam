import { useMemo, useState } from "react";

import type { University } from "../shared/api/types";

const normalize = (text: string) => text.toLowerCase().replace(/ё/g, "е").trim();
export const NO_UNIVERSITY = "__none__";

interface Props {
  universities: University[];
  value: string | null | undefined;
  onChange: (code: string | null) => void;
}

function matches(item: University, query: string): boolean {
  return normalize(item.title).includes(query) || normalize(item.short_title).includes(query);
}

/** Universities and colleges of the selected region: popular first, the rest via search. */
export function UniversityPicker({ universities, value, onChange }: Props) {
  const [query, setQuery] = useState("");
  const selected = universities.find((item) => item.code === value);
  const large = universities.length > 12;

  const options = useMemo(() => {
    const q = normalize(query);
    if (q) return universities.filter((item) => matches(item, q)).slice(0, 40);
    if (!large) return universities;
    const popular = universities.filter((item) => item.popular || item.partner);
    return selected && !popular.includes(selected) ? [selected, ...popular] : popular;
  }, [universities, query, selected, large]);

  return (
    <div className="region-picker">
      {large ? (
        <input
          className="input input--search"
          type="search"
          placeholder="Найти вуз или колледж: МГУ, «финансовый»…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Поиск вуза или колледжа"
        />
      ) : null}
      {large && !query ? <p className="muted region-picker__hint">Часто выбирают</p> : null}
      <div className="choices" role="radiogroup">
        {options.map((item) => (
          <button
            key={item.code}
            type="button"
            role="radio"
            aria-checked={value === item.code}
            className={`choice choice--institution ${value === item.code ? "choice--selected" : ""}`}
            onClick={() => onChange(item.code)}
          >
            <span className="choice__title">{item.short_title}</span>
            <span className="choice__subtitle">{item.title}</span>
            {item.partner ? <span className="choice__tag">Официальные памятки вуза</span> : null}
            {item.kind === "college" ? <span className="choice__tag choice__tag--muted">Колледж</span> : null}
          </button>
        ))}
        {query && options.length === 0 ? (
          <p className="muted">Не нашли — выберите «Другой вуз или колледж» ниже.</p>
        ) : null}
        <button
          type="button"
          role="radio"
          aria-checked={value === null}
          className={`choice ${value === null ? "choice--selected" : ""}`}
          onClick={() => onChange(null)}
        >
          Другой вуз или колледж
        </button>
      </div>
      {large && !query ? (
        <p className="muted region-picker__hint">
          В регионе {universities.length} учебных заведений — остальные найдутся через поиск.
        </p>
      ) : null}
    </div>
  );
}
