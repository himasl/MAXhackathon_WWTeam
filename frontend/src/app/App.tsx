import { useCallback, useEffect, useState } from "react";

import { CompletionPage } from "../pages/CompletionPage";
import { OnboardingPage } from "../pages/OnboardingPage";
import { RoutePage } from "../pages/RoutePage";
import { StepPage } from "../pages/StepPage";
import { SupportPage } from "../pages/SupportPage";
import { WelcomePage } from "../pages/WelcomePage";
import {
  ApiError,
  api,
  consumeLinkToken,
  errorMessage,
  restoreAccessToken,
  setAccessToken,
} from "../shared/api/client";
import type { Profile, Route } from "../shared/api/types";
import { maxBridge } from "../shared/max/maxBridge";
import { ErrorState, Loading, Screen } from "../shared/ui";
import { useHashRoute } from "./useHashRoute";

type Boot = { state: "loading" } | { state: "error"; message: string } | { state: "ready" };

async function orNull<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch (error) {
    if (error instanceof ApiError && error.isNotFound) return null;
    throw error;
  }
}

export function App() {
  const [boot, setBoot] = useState<Boot>({ state: "loading" });
  const [route, setRoute] = useState<Route | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [view, navigate] = useHashRoute();

  const start = useCallback(async () => {
    setBoot({ state: "loading" });
    try {
      let startParam = maxBridge.getStartParam();
      const initData = maxBridge.getInitData();
      const linkToken = consumeLinkToken();
      if (initData) {
        const auth = await api.loginWithMax(initData);
        setAccessToken(auth.access_token);
        startParam = auth.start_param ?? startParam;
      } else if (linkToken) {
        // Opened from a bot button: remember the signed login for later visits.
        setAccessToken(linkToken, true);
      } else {
        restoreAccessToken();
      }
      const [currentRoute, currentProfile] = await Promise.all([
        orNull(api.getCurrentRoute()),
        orNull(api.getProfile()),
      ]);
      setRoute(currentRoute);
      setProfile(currentProfile);

      const deepLinkStep = startParam?.startsWith("step_") ? startParam.slice(5) : null;
      if (!currentRoute) {
        navigate({ name: "welcome" }, true);
      } else if (deepLinkStep && currentRoute.steps.some((step) => step.id === deepLinkStep)) {
        navigate({ name: "route" }, true);
        navigate({ name: "step", stepId: deepLinkStep });
      } else if (["welcome", "done"].includes(window.location.hash.replace("#/", ""))) {
        navigate({ name: "route" }, true);
      }
      setBoot({ state: "ready" });
    } catch (error) {
      setBoot({ state: "error", message: errorMessage(error) });
    } finally {
      maxBridge.ready();
    }
  }, [navigate]);

  useEffect(() => {
    void start();
  }, [start]);

  const goBack = useCallback(() => navigate({ name: "route" }), [navigate]);

  useEffect(() => {
    if (view.name === "step" || view.name === "support" || (view.name === "onboarding" && route)) {
      return maxBridge.showBackButton(goBack);
    }
    return undefined;
  }, [view, route, goBack]);

  const submitProfile = async (draft: Profile) => {
    setSubmitError(null);
    try {
      setProfile(await api.saveProfile(draft));
      const created = await api.createRoute();
      setRoute(created);
      maxBridge.notify("success");
      navigate({ name: "route" }, true);
    } catch (error) {
      // The previous route stays untouched on failure.
      setSubmitError(errorMessage(error));
    }
  };

  const onRouteChanged = (updated: Route, completedStepId: string | null) => {
    setRoute(updated);
    if (!completedStepId) return;
    if (updated.status === "COMPLETED") {
      navigate({ name: "done" }, true);
    } else if (updated.next_step_id) {
      navigate({ name: "step", stepId: updated.next_step_id }, true);
    } else {
      navigate({ name: "route" }, true);
    }
  };

  if (boot.state === "loading") {
    return (
      <Screen>
        <Loading text="Открываем маршрут…" />
      </Screen>
    );
  }
  if (boot.state === "error") {
    return (
      <Screen>
        <ErrorState message={boot.message} onRetry={start} />
      </Screen>
    );
  }

  const onboarding = (
    <OnboardingPage
      initial={profile}
      error={submitError}
      onSubmit={submitProfile}
      onCancel={route ? goBack : () => navigate({ name: "welcome" })}
    />
  );
  const welcome = <WelcomePage onStart={() => navigate({ name: "onboarding" })} />;

  let content;
  if (!route) {
    content = view.name === "onboarding" ? onboarding : welcome;
  } else if (view.name === "onboarding") {
    content = onboarding;
  } else if (view.name === "step") {
    content = (
      <StepPage
        key={view.stepId}
        routeId={route.id}
        stepId={view.stepId}
        routeIsArchived={route.status === "ARCHIVED"}
        onRouteChanged={onRouteChanged}
        onBack={goBack}
      />
    );
  } else if (view.name === "done") {
    content = <CompletionPage route={route} onShowRoute={goBack} />;
  } else if (view.name === "support") {
    content = <SupportPage />;
  } else {
    content = (
      <RoutePage
        route={route}
        onOpenStep={(stepId) => navigate({ name: "step", stepId })}
        onEditProfile={() => navigate({ name: "onboarding" })}
      />
    );
  }

  const showTabs = route && (view.name === "route" || view.name === "support");
  return (
    <div className={`app ${showTabs ? "app--tabs" : ""}`}>
      {content}
      {showTabs ? (
        <nav className="tabs" aria-label="Разделы">
          <button
            type="button"
            className={view.name === "route" ? "tab tab--active" : "tab"}
            onClick={() => navigate({ name: "route" })}
          >
            Маршрут
          </button>
          <button
            type="button"
            className={view.name === "support" ? "tab tab--active" : "tab"}
            onClick={() => navigate({ name: "support" })}
          >
            Поддержка
          </button>
        </nav>
      ) : null}
    </div>
  );
}
