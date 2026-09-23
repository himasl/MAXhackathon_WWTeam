import { useMemo, useState } from "react";

import type { Region } from "../shared/api/types";

const normalize = (text: string) => text.toLowerCase().replace(/ё/g, "е").trim();

interface Props {
  regions: Region[];
  value: string | undefined;
  onChange: (code: string) => void;
}

/** All 89 regions: popular ones first, the rest are found by typing a name. */
export function RegionPicker({ regions, value, onChange }: Props) {
  const [query, setQuery] = useState("");
  const selected = regions.find((region) => region.code === value);

  const options = useMemo(() => {
    const q = normalize(query);
    if (q) {
      return regions
        .filter((region) => normalize(region.title).includes(q) || region.code === q)
        .sort((a, b) => {
          // Matches at the start of a word first: «моск» → Москва, Московская область.
          const rank = (r: Region) => (normalize(r.title).startsWith(q) ? 0 : 1);
          return rank(a) - rank(b) || a.title.localeCompare(b.title, "ru");
        })
        .slice(0, 30);
    }
    const popular = regions.filter((region) => region.popular);
    return selected && !selected.popular ? [selected, ...popular] : popular;
  }, [regions, query, selected]);

  return (
    <div className="region-picker">
      <input
        className="input input--search"
        type="search"
        placeholder="Найти регион по названию"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Поиск региона"
      />
      {!query ? <p className="muted region-picker__hint">Часто выбирают</p> : null}
      <div className="choices" role="radiogroup">
        {options.map((region) => (
          <button
            key={region.code}
            type="button"
            role="radio"
            aria-checked={value === region.code}
            className={`choice ${value === region.code ? "choice--selected" : ""}`}
            onClick={() => onChange(region.code)}
          >
            {region.title}
          </button>
        ))}
        {query && options.length === 0 ? (
          <p className="muted">Ничего не нашлось. Попробуйте другое написание.</p>
        ) : null}
      </div>
      {!query ? (
        <p className="muted region-picker__hint">
          Всего {regions.length} регионов — остальные найдутся через поиск.
        </p>
      ) : null}
    </div>
  );
}
