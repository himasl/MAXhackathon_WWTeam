import { useState } from "react";

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
    pattern: /МФЦ/i,
    query: "МФЦ",
    label: "Найти МФЦ рядом",
    note: "Большинство услуг МФЦ оказывает в любом офисе, а не только по прописке — удобнее идти в ближайший к дому.",
  },
  { pattern: /поликлиник/i, query: "поликлиника", label: "Найти поликлинику рядом" },
  {
    pattern: /страхов\S* медицинск/i,
    query: "страховая медицинская организация ОМС",
    label: "Найти офис страховой рядом",
  },
  {
    pattern: /транспортных карт/i,
    query: "пункт обслуживания транспортных карт",
    label: "Найти пункт рядом",
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
          ? `Геолокация недоступна — показываем ${place.query} в регионе «${regionTitle}».`
          : "Геолокация недоступна — показываем поиск на карте.",
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
        {hint ?? `${place.note ? `${place.note} ` : ""}Местоположение нужно только для карты и не сохраняется.`}
      </p>
    </div>
  );
}
