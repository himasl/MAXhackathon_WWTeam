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
}

function webApp(): MaxWebApp | undefined {
  return typeof window === "undefined" ? undefined : window.WebApp;
}

function startParamFromHash(): string | null {
  // Browser fallback for deep links: https://app/#/start/<param>
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
    return webApp()?.initDataUnsafe?.start_param || startParamFromHash();
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
  notify(type) {
    try {
      webApp()?.HapticFeedback?.notificationOccurred(type);
    } catch {
      // Haptics are optional.
    }
  },
};
