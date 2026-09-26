import { t } from "../shared/i18n";
import { useMemo, useState } from "react";

import type { Region, RegionalService } from "../shared/api/types";

const normalize = (text: string) => text.toLowerCase().replace(/ё/g, "е").trim();

interface Props {
  regions: Region[];
  value: string | undefined;
  onChange: (code: string) => void;
}

const SERVICE_LABELS: Record<RegionalService, string> = {
  mfc: t("МФЦ", "MFC (public services centre)"),
  tfoms: t("фонд ОМС", "health insurance fund"),
  student_transport: t("студенческий проезд", "student transport"),
};

/** Tells what official regional data the route will use for the chosen region. */
function coverageNote(region: Region): string {
  const services = region.services ?? [];
  if (services.length === 0) {
    return t(
      "Для региона возьмём федеральные правила и Госуслуги; региональные подсказки помечены как демонстрационные.",
      "For this region we use federal rules and Gosuslugi; regional tips are marked as demo data.",
    );
  }
  const list = services.map((kind) => SERVICE_LABELS[kind]).join(", ");
  return t(`Для региона есть официальные данные: ${list}.`, `Official data for this region: ${list}.`);
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
        placeholder={t("Найти регион по названию", "Find a region by name (in Russian)")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label={t("Поиск региона", "Region search")}
      />
      {!query ? <p className="muted region-picker__hint">{t("Часто выбирают", "Popular")}</p> : null}
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
          <p className="muted">{t("Ничего не нашлось. Попробуйте другое написание.", "Nothing found. Try another spelling.")}</p>
        ) : null}
      </div>
      {selected ? <p className="region-picker__coverage">{coverageNote(selected)}</p> : null}
      {!query ? (
        <p className="muted region-picker__hint">
          {t(
            `Всего ${regions.length} регионов — остальные найдутся через поиск.`,
            `${regions.length} regions in total — search to find the rest.`,
          )}
        </p>
      ) : null}
    </div>
  );
}
