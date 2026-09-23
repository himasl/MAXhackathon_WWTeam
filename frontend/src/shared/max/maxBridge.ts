/**
 * The only place that touches `window.WebApp` (MAX Bridge).
 * Outside MAX (plain browser, local dev) every method degrades gracefully.
 */

interface MaxWebApp {
  initData?: string;
  initDataUnsafe?: { start_param?: string };
  platform?: string;
  ready?: () => void;
  openLink?: (url: string) => void;
  BackButton?: {
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
  };
  shareMaxContent?: (params: { text?: string; link?: string }) => void;
  shareContent?: (params: { text?: string; link?: string }) => void;
  HapticFeedback?: {
    notificationOccurred: (type: "error" | "success" | "warning") => void;
  };
}

declare global {
  interface Window {
    WebApp?: MaxWebApp;
  }
}

export interface MaxBridge {
  getInitData(): string | null;
  getPlatform(): string;
  getStartParam(): string | null;
  isInsideMax(): boolean;
  ready(): void;
  openLink(url: string): void;
  showBackButton(callback: () => void): () => void;
  notify(type: "error" | "success" | "warning"): void;
  share(text: string, link: string): Promise<"shared" | "copied" | "failed">;
}

function webApp(): MaxWebApp | undefined {
  return typeof window === "undefined" ? undefined : window.WebApp;
}

function startParamFromUrl(): string | null {
  // Link buttons from the bot: https://app/?t=<token>&start=<param>
  const fromQuery = new URLSearchParams(window.location.search).get("start");
  if (fromQuery) return fromQuery;
  const match = window.location.hash.match(/^#\/start\/([^/?]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export const maxBridge: MaxBridge = {
  getInitData() {
    const data = webApp()?.initData;
    return data && data.length > 0 ? data : null;
  },
  getPlatform() {
    return webApp()?.platform ?? "browser";
  },
  getStartParam() {
    return webApp()?.initDataUnsafe?.start_param || startParamFromUrl();
  },
  isInsideMax() {
    return this.getInitData() !== null;
  },
  ready() {
    try {
      webApp()?.ready?.();
    } catch {
      // Not inside MAX.
    }
  },
  openLink(url: string) {
    const app = webApp();
    if (app?.openLink && this.isInsideMax()) {
      app.openLink(url);
    } else {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  },
  showBackButton(callback: () => void) {
    const button = webApp()?.BackButton;
    if (!button || !this.isInsideMax()) {
      return () => undefined;
    }
    button.onClick(callback);
    button.show();
    return () => {
      button.offClick(callback);
      button.hide();
    };
  },
  async share(text: string, link: string) {
    const app = webApp();
    try {
      // Inside MAX: share to a chat in MAX (falls back to the native share sheet).
      if (this.isInsideMax() && app?.shareMaxContent) {
        app.shareMaxContent({ text, link });
        return "shared";
      }
      if (this.isInsideMax() && app?.shareContent) {
        app.shareContent({ text, link });
        return "shared";
      }
      if (navigator.share) {
        await navigator.share({ text, url: link });
        return "shared";
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return "failed";
    }
    try {
      await navigator.clipboard.writeText(`${text} ${link}`);
      return "copied";
    } catch {
      return "failed";
    }
  },
  notify(type) {
    try {
      webApp()?.HapticFeedback?.notificationOccurred(type);
    } catch {
      // Haptics are optional.
    }
  },
};
