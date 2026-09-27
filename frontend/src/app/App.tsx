import { useCallback, useEffect, useState } from "react";

import { OfflineBanner } from "../features/OfflineBanner";

import { AdminPage } from "../pages/AdminPage";
import { ChecklistPage } from "../pages/ChecklistPage";
import { CompletionPage } from "../pages/CompletionPage";
import { OnboardingPage } from "../pages/OnboardingPage";
import { RoutePage } from "../pages/RoutePage";
import { SharedProgressPage } from "../pages/SharedProgressPage";
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
import type { AppConfig, Profile, Region, Route, University } from "../shared/api/types";
import { t } from "../shared/i18n";
import { maxBridge } from "../shared/max/maxBridge";
import { ErrorState, Loading, Screen } from "../shared/ui";
import { InviteButton } from "../features/InviteButton";
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

/** A parent opened the student's progress link: a public page, no sign-in. */
function sharedToken(): string | null {
  return new URLSearchParams(window.location.search).get("share");
}

export function App() {
  const share = sharedToken();
  return share ? <SharedProgressPage token={share} /> : <StudentApp />;
}

function StudentApp() {
  const [boot, setBoot] = useState<Boot>({ state: "loading" });
  const [route, setRoute] = useState<Route | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [config, setConfig] = useState<AppConfig>({ bot_username: null, bot_url: null });
  const [inviteUniversity, setInviteUniversity] = useState<string | null>(null);
  // The project team (SUPPORT_MAX_USER_IDS) also gets the team panel tab.
  const [isAdmin, setIsAdmin] = useState(false);
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
      const [currentRoute, currentProfile, regionList, catalog, appConfig, me] = await Promise.all([
        orNull(api.getCurrentRoute()),
        orNull(api.getProfile()),
        api.getRegions(),
        // The catalog and config are optional: onboarding works without them.
        api.getUniversities().catch(() => [] as University[]),
        api.getConfig().catch(() => ({ bot_username: null, bot_url: null })),
        api.getMe().catch(() => null),
      ]);
      const admin = me?.is_admin ?? false;
      setIsAdmin(admin);
      setRoute(currentRoute);
      setProfile(currentProfile);
      setRegions(regionList);
      setUniversities(catalog);
      setConfig(appConfig);
      if (startParam?.startsWith("uni_")) setInviteUniversity(startParam.slice(4));

      const deepLinkStep = startParam?.startsWith("step_") ? startParam.slice(5) : null;
      if (admin && (startParam === "admin" || window.location.hash === "#/admin")) {
        // The bot's /admin button opens the team panel.
        navigate({ name: "admin" }, true);
      } else if (!currentRoute) {
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
    if (
      view.name === "step" ||
      view.name === "support" ||
      view.name === "checklist" ||
      (view.name === "onboarding" && route)
    ) {
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
        <Loading text={t("Открываем маршрут…", "Opening your route…")} />
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

  const invited = universities.find((item) => item.code === inviteUniversity);
  const onboarding = (
    <OnboardingPage
      initial={
        profile ??
        (invited
          ? { citizenship: "RU", region_code: invited.region_code, university_code: invited.code }
          : null)
      }
      regions={regions}
      universities={universities}
      error={submitError}
      onSubmit={submitProfile}
      onCancel={route ? goBack : () => navigate({ name: "welcome" })}
    />
  );
  const welcome = <WelcomePage onStart={() => navigate({ name: "onboarding" })} />;

  const regionTitle = regions.find((region) => region.code === profile?.region_code)?.title ?? null;
  let content;
  if (view.name === "admin" && isAdmin) {
    content = <AdminPage regions={regions} />;
  } else if (!route) {
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
        regionTitle={regionTitle}
        onRouteChanged={onRouteChanged}
        onBack={goBack}
        onOpenStep={(id) => navigate({ name: "step", stepId: id })}
      />
    );
  } else if (view.name === "done") {
    content = (
      <CompletionPage
        route={route}
        regionTitle={regionTitle}
        botUrl={config.bot_url}
        onShowRoute={goBack}
        onNewRoute={() => navigate({ name: "onboarding" })}
        invite={<InviteButton botUrl={config.bot_url} universityCode={profile?.university_code ?? null} />}
      />
    );
  } else if (view.name === "support") {
    content = <SupportPage />;
  } else if (view.name === "checklist") {
    content = <ChecklistPage routeId={route.id} regionTitle={regionTitle} onBack={goBack} />;
  } else {
    content = (
      <RoutePage
        route={route}
        onOpenStep={(stepId) => navigate({ name: "step", stepId })}
        onEditProfile={() => navigate({ name: "onboarding" })}
        onOpenChecklist={() => navigate({ name: "checklist" })}
        invite={<InviteButton botUrl={config.bot_url} universityCode={profile?.university_code ?? null} />}
      />
    );
  }

  const showTabs =
    (route || isAdmin) &&
    (view.name === "route" || view.name === "support" || (view.name === "admin" && isAdmin));
  return (
    <div className={`app ${showTabs ? "app--tabs" : ""}`}>
      <OfflineBanner />
      {content}
      {showTabs ? (
        <nav className="tabs" aria-label={t("Разделы", "Sections")}>
          <button
            type="button"
            className={view.name === "route" ? "tab tab--active" : "tab"}
            onClick={() => navigate({ name: "route" })}
            aria-current={view.name === "route" ? "page" : undefined}
          >
            {t("Маршрут", "Route")}
          </button>
          <button
            type="button"
            className={view.name === "support" ? "tab tab--active" : "tab"}
            onClick={() => navigate({ name: "support" })}
            aria-current={view.name === "support" ? "page" : undefined}
          >
            {t("Помощь", "Help")}
          </button>
          {isAdmin ? (
            <button
              type="button"
              className={view.name === "admin" ? "tab tab--active" : "tab"}
              onClick={() => navigate({ name: "admin" })}
              aria-current={view.name === "admin" ? "page" : undefined}
            >
              {t("Команда", "Team")}
            </button>
          ) : null}
        </nav>
      ) : null}
    </div>
  );
}
