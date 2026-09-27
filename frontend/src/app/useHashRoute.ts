import { useCallback, useEffect, useState } from "react";

export type View =
  | { name: "route" }
  | { name: "welcome" }
  | { name: "onboarding" }
  | { name: "support" }
  | { name: "done" }
  | { name: "checklist" }
  | { name: "admin" }
  | { name: "step"; stepId: string };

export function parseHash(hash: string): View {
  const path = hash.replace(/^#\/?/, "");
  const [head, param] = path.split("/");
  if (head === "step" && param) return { name: "step", stepId: decodeURIComponent(param) };
  if (
    head === "welcome" ||
    head === "onboarding" ||
    head === "support" ||
    head === "done" ||
    head === "checklist" ||
    head === "admin"
  ) {
    return { name: head };
  }
  return { name: "route" };
}

export function toHash(view: View): string {
  return view.name === "step" ? `#/step/${encodeURIComponent(view.stepId)}` : `#/${view.name}`;
}

export function useHashRoute(): [View, (view: View, replace?: boolean) => void] {
  const [view, setView] = useState<View>(() => parseHash(window.location.hash));

  useEffect(() => {
    const onChange = () => setView(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = useCallback((next: View, replace = false) => {
    const hash = toHash(next);
    if (replace) {
      window.history.replaceState(null, "", hash);
    } else if (window.location.hash !== hash) {
      window.history.pushState(null, "", hash);
    }
    setView(next);
    window.scrollTo(0, 0);
  }, []);

  return [view, navigate];
}
