import { useState } from "react";

import { t } from "../shared/i18n";
import { maxBridge } from "../shared/max/maxBridge";
import { Button } from "../shared/ui";

/**
 * "Find nearby" for steps done in person (МФЦ, поликлиника, …).
 * Most МФЦ services are available in any office, so the nearest one is where the student
 * lives now, not where they are registered. Coordinates stay on the device: they only go
 * into the Yandex Maps link and are never sent to our backend.
 */

interface Place {
  pattern: RegExp;
  query: string;
  label: string;
  note?: string;
}

const PLACES: Place[] = [
  {
    pattern: /МФЦ|\bMFC\b/i,
    query: "МФЦ",
    label: t("Найти МФЦ рядом", "Find an MFC nearby"),
    note: t(
      "Большинство услуг МФЦ оказывает в любом офисе, а не только по прописке — удобнее идти в ближайший к дому.",
      "Most MFC services are available in any office, not only where you are registered — go to the nearest one.",
    ),
  },
  {
    pattern: /поликлиник|\bclinic\b/i,
    query: "поликлиника",
    label: t("Найти поликлинику рядом", "Find a clinic nearby"),
  },
  {
    pattern: /страхов\S* (медицинск|компан)|insurance company/i,
    query: "страховая медицинская организация",
    label: t("Найти офис страховой рядом", "Find an insurance office nearby"),
  },
  {
    pattern: /транспортных карт/i,
    query: "пункт обслуживания транспортных карт",
    label: t("Найти пункт рядом", "Find a service point nearby"),
  },
];

export function placeFor(location: string): Place | null {
  return PLACES.find((place) => place.pattern.test(location)) ?? null;
}

function mapsUrl(query: string, coords: GeolocationCoordinates | null, regionTitle: string | null) {
  const params = new URLSearchParams();
  if (coords) {
    // Yandex expects "longitude,latitude".
    params.set("ll", `${coords.longitude.toFixed(5)},${coords.latitude.toFixed(5)}`);
    params.set("z", "14");
    params.set("text", query);
  } else {
    params.set("text", regionTitle ? `${query} ${regionTitle}` : query);
  }
  return `https://yandex.ru/maps/?${params.toString()}`;
}

function currentPosition(): Promise<GeolocationCoordinates | null> {
  if (typeof navigator === "undefined" || !navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    // The API timeout does not count time spent on the permission prompt,
    // so a prompt left unanswered would hang forever without our own timer.
    const timer = window.setTimeout(() => resolve(null), 12000);
    const finish = (coords: GeolocationCoordinates | null) => {
      window.clearTimeout(timer);
      resolve(coords);
    };
    navigator.geolocation.getCurrentPosition(
      (position) => finish(position.coords),
      () => finish(null),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 10 * 60 * 1000 },
    );
  });
}

export function NearbyPlace({
  location,
  regionTitle,
}: {
  location: string;
  regionTitle: string | null;
}) {
  const [searching, setSearching] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const place = placeFor(location);
  if (!place) return null;

  const find = async () => {
    setSearching(true);
    setHint(null);
    // Outside MAX a window opened after an await is blocked as a pop-up,
    // so reserve the tab now and point it at the map once we know the position.
    const tab = maxBridge.isInsideMax() ? null : window.open("", "_blank");
    const coords = await currentPosition();
    const url = mapsUrl(place.query, coords, regionTitle);
    if (!coords) {
      setHint(
        regionTitle
          ? t(
              `Геолокация недоступна — показываем ${place.query} в регионе «${regionTitle}».`,
              `Location is unavailable — showing results in ${regionTitle}.`,
            )
          : t("Геолокация недоступна — показываем поиск на карте.", "Location is unavailable — showing a map search."),
      );
    }
    if (tab) {
      tab.opener = null;
      tab.location.href = url;
    } else {
      maxBridge.openLink(url);
    }
    setSearching(false);
  };

  return (
    <div className="nearby">
      <Button variant="secondary" onClick={find} loading={searching}>
        📍 {place.label}
      </Button>
      <p className="muted nearby__note">
        {hint ??
          `${place.note ? `${place.note} ` : ""}${t(
            "Местоположение нужно только для карты и не сохраняется.",
            "Your location is used only for the map and is not stored.",
          )}`}
      </p>
    </div>
  );
}
