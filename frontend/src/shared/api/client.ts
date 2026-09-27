import { lang, t } from "../i18n";
import type {
  AdminOverview,
  AdminReport,
  AdminSource,
  AdminSourceKind,
  AppConfig,
  AuthResponse,
  Checklist,
  HelpTopic,
  Me,
  Profile,
  Region,
  ReportKind,
  Route,
  SharedProgress,
  StepDetail,
  University,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId: string | null = null,
  ) {
    super(message);
  }

  get isNotFound() {
    return this.status === 404;
  }
}

/** True when the last answer came from the offline copy (service worker). */
let offline = false;
const offlineListeners = new Set<(value: boolean) => void>();

export function isOffline(): boolean {
  return offline;
}

export function onOfflineChange(listener: (value: boolean) => void): () => void {
  offlineListeners.add(listener);
  return () => offlineListeners.delete(listener);
}

function setOffline(value: boolean) {
  if (value === offline) return;
  offline = value;
  offlineListeners.forEach((listener) => listener(value));
}

const TOKEN_KEY = "marshrut.token";
let accessToken: string | null = null;

export function setAccessToken(token: string | null, remember = false) {
  accessToken = token;
  if (!remember && token) return;
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage can be unavailable (private mode); the token then lives for this session.
  }
}

export function restoreAccessToken(): string | null {
  try {
    accessToken = window.localStorage.getItem(TOKEN_KEY);
  } catch {
    accessToken = null;
  }
  return accessToken;
}

/** Take the signed login token from a bot link (?t=...) and clean the address bar. */
export function consumeLinkToken(): string | null {
  const url = new URL(window.location.href);
  const token = url.searchParams.get("t");
  if (!token) return null;
  url.searchParams.delete("t");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  return token;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("Accept-Language", lang());
  if (init.body) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", t("Нет соединения с сервером", "No connection to the server"));
  }

  if ((init.method ?? "GET") === "GET") setOffline(response.headers.get("X-Offline") === "1");
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `${t("Ошибка", "Error")} ${response.status}`,
      response.headers.get("X-Request-ID"),
    );
  }
  return body as T;
}

export const api = {
  getMe: () => request<Me>("/api/v1/me"),
  loginWithMax: (initData: string) =>
    request<AuthResponse>("/api/v1/auth/max", {
      method: "POST",
      body: JSON.stringify({ init_data: initData }),
    }),
  getProfile: () => request<Profile>("/api/v1/profile"),
  saveProfile: (profile: Profile) =>
    request<Profile>("/api/v1/profile", { method: "PUT", body: JSON.stringify(profile) }),
  createRoute: () => request<Route>("/api/v1/routes", { method: "POST" }),
  getCurrentRoute: () => request<Route>("/api/v1/routes/current"),
  getStep: (routeId: string, stepId: string) =>
    request<StepDetail>(`/api/v1/routes/${routeId}/steps/${stepId}`),
  completeStep: (routeId: string, stepId: string) =>
    request<Route>(`/api/v1/routes/${routeId}/steps/${stepId}/complete`, { method: "POST" }),
  skipStep: (routeId: string, stepId: string) =>
    request<Route>(`/api/v1/routes/${routeId}/steps/${stepId}/skip`, { method: "POST" }),
  setLanguage: (value: "ru" | "en") =>
    request<null>("/api/v1/me/language", { method: "PUT", body: JSON.stringify({ lang: value }) }),
  reopenStep: (routeId: string, stepId: string) =>
    request<Route>(`/api/v1/routes/${routeId}/steps/${stepId}/reopen`, { method: "POST" }),
  getConfig: () => request<AppConfig>("/api/v1/config"),
  getRegions: () => request<Region[]>("/api/v1/regions"),
  getUniversities: () => request<University[]>("/api/v1/universities"),
  calendarLink: (routeId: string, stepId: string) =>
    request<{ url: string }>(`/api/v1/routes/${routeId}/steps/${stepId}/calendar-link`, {
      method: "POST",
    }),
  getChecklist: (routeId: string) => request<Checklist>(`/api/v1/routes/${routeId}/checklist`),
  sendChecklist: (routeId: string) =>
    request<{ sent: boolean }>(`/api/v1/routes/${routeId}/checklist/send`, { method: "POST" }),
  createShareLink: () =>
    request<{ url: string; expires_in: number }>("/api/v1/routes/share", { method: "POST" }),
  revokeShareLinks: () => request<null>("/api/v1/routes/share", { method: "DELETE" }),
  getShared: (token: string) =>
    request<SharedProgress>(`/api/v1/shared/${encodeURIComponent(token)}`),
  getHelp: () => request<HelpTopic[]>("/api/v1/help"),
  reportStep: (routeId: string, stepId: string, kind: ReportKind, comment: string) =>
    request<{ id: string }>(`/api/v1/routes/${routeId}/steps/${stepId}/report`, {
      method: "POST",
      body: JSON.stringify({ kind, comment }),
    }),
  admin: {
    overview: () => request<AdminOverview>("/api/v1/admin/overview"),
    sources: (filter: { region_code?: string; kind?: AdminSourceKind; stale?: boolean }) => {
      const query = new URLSearchParams();
      if (filter.region_code) query.set("region_code", filter.region_code);
      if (filter.kind) query.set("kind", filter.kind);
      if (filter.stale) query.set("stale", "true");
      return request<AdminSource[]>(`/api/v1/admin/sources?${query}`);
    },
    updateSource: (
      id: string,
      change: { url?: string; organization?: string; title?: string; mark_checked?: boolean },
    ) =>
      request<AdminSource>(`/api/v1/admin/sources/${id}`, {
        method: "PATCH",
        body: JSON.stringify(change),
      }),
    reports: (resolved: boolean) =>
      request<AdminReport[]>(`/api/v1/admin/reports?resolved=${resolved}`),
    setResolved: (id: string, resolved: boolean) =>
      request<null>(`/api/v1/admin/reports/${id}/${resolved ? "resolve" : "reopen"}`, {
        method: "POST",
      }),
  },
  remind: (routeId: string) =>
    request<{ sent: boolean; step_id: string | null }>(`/api/v1/routes/${routeId}/remind`, {
      method: "POST",
    }),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0)
      return t("Нет соединения с сервером. Проверьте интернет.", "No connection. Check the internet.");
    if (error.status === 401)
      return t(
        "Не удалось подтвердить вход. Откройте маршрут по кнопке из чата с ботом в MAX (команда /start).",
        "We could not sign you in. Open the route with the button in the bot chat in MAX (/start).",
      );
    if (error.status >= 500) {
      // The code helps support find this exact failure in the server logs.
      const code = error.requestId ? ` ${t("Код для поддержки", "Support code")}: ${error.requestId}.` : "";
      return t("Сервис временно недоступен. Попробуйте ещё раз.", "The service is unavailable. Try again.") + code;
    }
    return error.message;
  }
  return t("Что-то пошло не так. Попробуйте ещё раз.", "Something went wrong. Try again.");
}
