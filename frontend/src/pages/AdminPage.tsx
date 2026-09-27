import { useCallback, useEffect, useState } from "react";

import { api, errorMessage } from "../shared/api/client";
import type {
  AdminCount,
  AdminOverview,
  AdminReport,
  AdminSource,
  AdminSourceKind,
  Region,
} from "../shared/api/types";
import { maxBridge } from "../shared/max/maxBridge";
import { Button, ErrorState, Loading, Notice, Screen, Section } from "../shared/ui";

/** The team panel: business metrics, official regional links and users' reports.
 *  Visible only to SUPPORT_MAX_USER_IDS; the text is Russian, the team's language. */

type Tab = "stats" | "sources" | "reports";

const percent = (value: number) => `${Math.round(value * 100)}%`;
const shortDate = (value: string) =>
  new Date(value).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });

const KIND_LABELS: Record<AdminSourceKind, string> = {
  mfc: "МФЦ",
  tfoms: "Фонд ОМС",
  transport: "Проезд",
  regional: "Региональный",
  federal: "Федеральный",
};
const REPORT_LABELS: Record<AdminReport["kind"], string> = {
  OUTDATED: "Устарело",
  NOT_APPLICABLE: "Не подходит",
  OTHER: "Другое",
};

export function AdminPage({ regions }: { regions: Region[] }) {
  const [tab, setTab] = useState<Tab>("stats");
  return (
    <Screen>
      <h1>Панель команды</h1>
      <div className="segmented segmented--3" role="group" aria-label="Разделы панели">
        {(
          [
            ["stats", "Статистика"],
            ["sources", "Источники"],
            ["reports", "Отзывы"],
          ] as const
        ).map(([value, label]) => (
          <button key={value} type="button" aria-pressed={tab === value} onClick={() => setTab(value)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "stats" ? <StatsTab onOpen={setTab} /> : null}
      {tab === "sources" ? <SourcesTab regions={regions} /> : null}
      {tab === "reports" ? <ReportsTab regions={regions} /> : null}
    </Screen>
  );
}

function useLoad<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    setError(null);
    try {
      setData(await load());
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }, [load]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, error, reload, setData };
}

/* ---------- statistics ---------- */

function StatsTab({ onOpen }: { onOpen: (tab: Tab) => void }) {
  const { data, error, reload } = useLoad(api.admin.overview);
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const { users, activity, engagement } = data;
  return (
    <>
      <div className="kpis">
        <Kpi value={users.total} label="пользователей" hint={`+${users.new_7d} за неделю`} />
        <Kpi value={activity.mau} label="активны за 30 дней" hint={`сегодня ${activity.dau}, за неделю ${activity.wau}`} />
        <Kpi value={percent(engagement.completion_rate)} label="прошли маршрут" hint="из активных маршрутов" />
        <Kpi value={percent(activity.returning_share)} label="возвращаются" hint="заходили больше одного дня" />
      </div>

      <Section title="Активность по дням">
        <ActivityChart daily={activity.daily} />
        <p className="muted admin-note">
          Бот используют {percent(activity.bot_share)} активных · DAU/MAU {percent(activity.stickiness)}
        </p>
      </Section>

      <Section title="Воронка">
        <Funnel stages={data.funnel} />
      </Section>

      <Section title="Как пользуются">
        <dl className="admin-facts">
          <Fact label="Дел выполнено" value={engagement.steps_done} />
          <Fact label="Из них кнопкой в чате" value={percent(engagement.done_from_chat_share)} />
          <Fact label="Напоминаний отправлено" value={engagement.reminders_sent} />
          <Fact label="Выполнено после напоминания" value={percent(engagement.reminder_conversion)} />
          <Fact label="Пропущено «не нужно»" value={engagement.steps_skipped} />
          <Fact label="Дел в маршруте в среднем" value={engagement.avg_steps_per_route} />
          <Fact label="Медиана до регистрации" value={days(engagement.registration_median_days)} />
          <Fact label="Медиана прохождения маршрута" value={days(engagement.route_median_days)} />
        </dl>
      </Section>

      <Section title="Где застревают">
        {data.problem_steps.length ? (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Дело</th>
                <th>Выполнили</th>
                <th>Отзывы</th>
              </tr>
            </thead>
            <tbody>
              {data.problem_steps.map((step) => (
                <tr key={step.code}>
                  <td>{step.title}</td>
                  <td>
                    {percent(step.completion_rate)} <span className="muted">из {step.in_routes}</span>
                  </td>
                  <td>{step.reports || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Пока нет маршрутов.</p>
        )}
      </Section>

      <CountTable title="Регионы" rows={data.by_region} />
      <CountTable title="Вузы" rows={data.by_university} />
      <CountTable title="Сценарии" rows={data.by_scenario} unit="маршрутов" />
      <CountTable title="Жильё" rows={data.by_housing} />
      <CountTable title="Язык" rows={data.by_language} completed={false} />

      <Section title="Качество данных">
        <dl className="admin-facts">
          <Fact label="Региональных источников" value={data.data.regional_sources} />
          <Fact label="Не проверялись 90+ дней" value={data.data.stale_sources} />
          <Fact label="Исправлено в панели" value={data.data.edited_sources} />
          <Fact label="Неразобранных отзывов" value={data.data.open_reports} />
        </dl>
        <div className="admin-actions">
          <Button variant="secondary" onClick={() => onOpen("sources")}>
            Проверить источники
          </Button>
          <Button variant="secondary" onClick={() => onOpen("reports")}>
            Разобрать отзывы
          </Button>
        </div>
      </Section>
      <p className="muted admin-note">
        Только агрегаты, без личных данных. Команда и тестовые учётки проверяющих не учитываются.
        Обновлено {new Date(data.generated_at).toLocaleString("ru-RU")}.
      </p>
    </>
  );
}

const days = (value: number | null) => (value === null ? "—" : `${value} дн.`);

function Kpi({ value, label, hint }: { value: number | string; label: string; hint: string }) {
  return (
    <div className="kpi">
      <p className="kpi__value">{value}</p>
      <p className="kpi__label">{label}</p>
      <p className="kpi__hint">{hint}</p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="admin-facts__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function ActivityChart({ daily }: { daily: AdminOverview["activity"]["daily"] }) {
  const [selected, setSelected] = useState(daily.length - 1);
  const max = Math.max(1, ...daily.map((day) => day.total));
  const current = daily[selected];
  return (
    <div className="activity">
      <p className="activity__readout" aria-live="polite">
        <b>{shortDate(current.day)}</b>: {current.total} активных · в приложении {current.app}, в боте{" "}
        {current.bot}
      </p>
      <div className="activity__bars" role="list" aria-label="Активные пользователи за 30 дней">
        {daily.map((day, index) => (
          <button
            key={day.day}
            type="button"
            role="listitem"
            className={`activity__bar ${index === selected ? "activity__bar--selected" : ""}`}
            onMouseEnter={() => setSelected(index)}
            onFocus={() => setSelected(index)}
            onClick={() => setSelected(index)}
            aria-label={`${shortDate(day.day)}: ${day.total}`}
          >
            <span style={{ height: `${Math.max(day.total ? 6 : 2, (day.total / max) * 100)}%` }} />
          </button>
        ))}
      </div>
      <div className="activity__axis" aria-hidden>
        <span>{shortDate(daily[0].day)}</span>
        <span>макс. {max}</span>
        <span>{shortDate(daily[daily.length - 1].day)}</span>
      </div>
    </div>
  );
}

function Funnel({ stages }: { stages: AdminOverview["funnel"] }) {
  const top = Math.max(1, stages[0]?.users ?? 0);
  return (
    <ol className="funnel">
      {stages.map((stage, index) => {
        const previous = index ? stages[index - 1].users : stage.users;
        return (
          <li key={stage.code} className="funnel__row">
            <div className="funnel__head">
              <span>{stage.title}</span>
              <b>
                {stage.users}
                {index ? <span className="muted"> · {percent(previous ? stage.users / previous : 0)}</span> : null}
              </b>
            </div>
            <div className="funnel__track">
              <span style={{ width: `${(stage.users / top) * 100}%` }} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function CountTable({
  title,
  rows,
  unit = "чел.",
  completed = true,
}: {
  title: string;
  rows: AdminCount[];
  unit?: string;
  completed?: boolean;
}) {
  if (!rows.length) return null;
  return (
    <Section title={title}>
      <table className="admin-table">
        <thead>
          <tr>
            <th />
            <th>{unit}</th>
            {completed ? <th>прошли</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.code}>
              <td>{row.title}</td>
              <td>{row.users}</td>
              {completed ? <td>{row.completed}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

/* ---------- sources ---------- */

function SourcesTab({ regions }: { regions: Region[] }) {
  const [region, setRegion] = useState("");
  const [kind, setKind] = useState<AdminSourceKind | "">("");
  const [stale, setStale] = useState(false);
  const load = useCallback(
    () => api.admin.sources({ region_code: region || undefined, kind: kind || undefined, stale }),
    [region, kind, stale],
  );
  const { data, error, reload, setData } = useLoad(load);

  const replace = (updated: AdminSource) =>
    setData((items) => items?.map((item) => (item.id === updated.id ? updated : item)) ?? null);

  return (
    <>
      <div className="admin-filters">
        <select className="input" value={region} onChange={(event) => setRegion(event.target.value)} aria-label="Регион">
          <option value="">Все регионы</option>
          {regions.map((item) => (
            <option key={item.code} value={item.code}>
              {item.title}
            </option>
          ))}
        </select>
        <select
          className="input"
          value={kind}
          onChange={(event) => setKind(event.target.value as AdminSourceKind | "")}
          aria-label="Тип источника"
        >
          <option value="">Все типы</option>
          {(Object.keys(KIND_LABELS) as AdminSourceKind[]).map((item) => (
            <option key={item} value={item}>
              {KIND_LABELS[item]}
            </option>
          ))}
        </select>
        <label className="admin-check">
          <input type="checkbox" checked={stale} onChange={(event) => setStale(event.target.checked)} />
          Только не проверенные 90+ дней
        </label>
      </div>
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {!error && !data ? <Loading /> : null}
      {data && !data.length ? <p className="muted">Ничего не найдено.</p> : null}
      {data ? (
        <>
          <p className="muted admin-note">Найдено: {data.length}. Исправление сразу видно студентам и не перезаписывается при деплое.</p>
          <ul className="soft-list">
            {data.map((source) => (
              <SourceCard key={source.id} source={source} onSaved={replace} />
            ))}
          </ul>
        </>
      ) : null}
    </>
  );
}

function SourceCard({ source, onSaved }: { source: AdminSource; onSaved: (source: AdminSource) => void }) {
  const [editing, setEditing] = useState(false);
  const [url, setUrl] = useState(source.url);
  const [organization, setOrganization] = useState(source.organization);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = async (change: Parameters<typeof api.admin.updateSource>[1]) => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.admin.updateSource(source.id, change);
      onSaved(updated);
      setEditing(false);
      setSaved(true);
      maxBridge.notify("success");
    } catch (reason) {
      setError(errorMessage(reason));
      maxBridge.notify("error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="soft-card soft-card--static admin-source">
      <p className="soft-card__eyebrow">
        {KIND_LABELS[source.kind]} · {source.region_title ?? "вся Россия"}
      </p>
      {source.stale || source.edited_at ? (
        <p className="admin-tags">
          {source.stale ? <span className="tag admin-tag--stale">не проверялся 90+ дней</span> : null}
          {source.edited_at ? <span className="tag">исправлен в панели</span> : null}
        </p>
      ) : null}
      <p className="soft-card__title">{source.organization}</p>
      <button type="button" className="link-button admin-source__url" onClick={() => maxBridge.openLink(source.url)}>
        {source.url} ↗
      </button>
      <p className="soft-card__meta">
        Проверен: {source.checked_at ? new Date(source.checked_at).toLocaleDateString("ru-RU") : "—"} · в шагах: {source.steps}
      </p>
      {editing ? (
        <div className="admin-form">
          <label>
            Ссылка
            <input className="input" type="url" value={url} onChange={(event) => setUrl(event.target.value)} />
          </label>
          <label>
            Организация
            <input className="input" value={organization} onChange={(event) => setOrganization(event.target.value)} />
          </label>
          <div className="admin-actions">
            <Button
              loading={busy}
              onClick={() => {
                setSaved(false);
                if (!/^https?:\/\/[^\s/]+\.[^\s]+$/i.test(url.trim())) {
                  setError("Проверьте ссылку: она должна начинаться с https:// и вести на сайт.");
                  return;
                }
                if (organization.trim().length < 2) {
                  setError("Укажите организацию.");
                  return;
                }
                void save({ url: url.trim(), organization: organization.trim(), mark_checked: true });
              }}
            >
              Сохранить
            </Button>
            <Button variant="ghost" onClick={() => setEditing(false)} disabled={busy}>
              Отмена
            </Button>
          </div>
        </div>
      ) : (
        <div className="admin-actions">
          <Button variant="secondary" loading={busy} onClick={() => save({ mark_checked: true })}>
            Проверено сегодня
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setSaved(false);
              setError(null);
              setEditing(true);
            }}
          >
            Изменить
          </Button>
        </div>
      )}
      {error ? <Notice tone="error">{error}</Notice> : null}
      {saved ? <Notice tone="success">Сохранено</Notice> : null}
    </li>
  );
}

/* ---------- reports ---------- */

function ReportsTab({ regions }: { regions: Region[] }) {
  const regionTitle = (code: string) => regions.find((item) => item.code === code)?.title ?? `регион ${code}`;
  const [resolved, setResolved] = useState(false);
  const load = useCallback(() => api.admin.reports(resolved), [resolved]);
  const { data, error, reload, setData } = useLoad(load);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const toggle = async (report: AdminReport) => {
    setBusy(report.id);
    setActionError(null);
    try {
      await api.admin.setResolved(report.id, !resolved);
      setData((items) => items?.filter((item) => item.id !== report.id) ?? null);
      maxBridge.notify("success");
    } catch (reason) {
      setActionError(errorMessage(reason));
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <div className="segmented" role="group" aria-label="Статус отзывов">
        <button type="button" aria-pressed={!resolved} onClick={() => setResolved(false)}>
          Новые
        </button>
        <button type="button" aria-pressed={resolved} onClick={() => setResolved(true)}>
          Разобранные
        </button>
      </div>
      {actionError ? <Notice tone="error">{actionError}</Notice> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {!error && !data ? <Loading /> : null}
      {data && !data.length ? (
        <p className="muted">{resolved ? "Разобранных отзывов пока нет." : "Новых отзывов нет — всё разобрано."}</p>
      ) : null}
      <ul className="soft-list">
        {data?.map((report) => (
          <li key={report.id} className="soft-card soft-card--static">
            <p className="soft-card__eyebrow">
              {REPORT_LABELS[report.kind]} · {new Date(report.created_at).toLocaleDateString("ru-RU")}
              {report.region_code ? ` · ${regionTitle(report.region_code)}` : ""}
            </p>
            <p className="soft-card__title">{report.step_title}</p>
            {report.comment ? <p>«{report.comment}»</p> : null}
            {report.summary ? <p className="soft-card__meta admin-summary">{report.summary}</p> : null}
            <Button variant="secondary" loading={busy === report.id} onClick={() => toggle(report)}>
              {resolved ? "Вернуть в новые" : "Разобрано"}
            </Button>
          </li>
        ))}
      </ul>
    </>
  );
}
