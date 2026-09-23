import type { AppConfig, AuthResponse, Profile, Route, StepDetail, University } from "./types";

const BASE_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }

  get isNotFound() {
    return this.status === 404;
  }
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
  if (init.body) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Нет соединения с сервером");
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `Ошибка ${response.status}`,
    );
  }
  return body as T;
}

export const api = {
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
  reopenStep: (routeId: string, stepId: string) =>
    request<Route>(`/api/v1/routes/${routeId}/steps/${stepId}/reopen`, { method: "POST" }),
  getConfig: () => request<AppConfig>("/api/v1/config"),
  getUniversities: () => request<University[]>("/api/v1/universities"),
  calendarLink: (routeId: string, stepId: string) =>
    request<{ url: string }>(`/api/v1/routes/${routeId}/steps/${stepId}/calendar-link`, {
      method: "POST",
    }),
  remind: (routeId: string) =>
    request<{ sent: boolean; step_id: string | null }>(`/api/v1/routes/${routeId}/remind`, {
      method: "POST",
    }),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return "Нет соединения с сервером. Проверьте интернет.";
    if (error.status === 401)
      return "Не удалось подтвердить вход. Откройте маршрут по кнопке из чата с ботом в MAX (команда /start).";
    if (error.status >= 500) return "Сервис временно недоступен. Попробуйте ещё раз.";
    return error.message;
  }
  return "Что-то пошло не так. Попробуйте ещё раз.";
}
