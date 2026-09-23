import { type ReactElement, useMemo, useState } from "react";

import type {
  Citizenship,
  EducationType,
  HousingType,
  Profile,
  Region,
  University,
} from "../shared/api/types";
import { RegionPicker } from "../features/RegionPicker";
import { Button, Notice, Screen } from "../shared/ui";

type Draft = Partial<Profile>;

interface Option<T> {
  value: T;
  label: string;
}

interface Question {
  id: string;
  title: string;
  hint?: string;
  isAnswered: (draft: Draft) => boolean;
  render: (draft: Draft, set: (patch: Draft) => void) => ReactElement;
}

const NO_UNIVERSITY = "__none__";

function Choices<T extends string | boolean>({
  options,
  value,
  onChange,
}: {
  options: Option<T>[];
  value: T | undefined;
  onChange: (value: T) => void;
}) {
  return (
    <div className="choices" role="radiogroup">
      {options.map((option) => (
        <button
          key={String(option.value)}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          className={`choice ${value === option.value ? "choice--selected" : ""}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

const YES_NO: Option<boolean>[] = [
  { value: true, label: "Да" },
  { value: false, label: "Нет" },
];

function buildQuestions(regions: Region[], universities: University[]): Question[] {
  const inRegion = (draft: Draft) =>
    universities.filter((item) => item.region_code === draft.region_code);

  const questions: Question[] = [
    {
      id: "citizenship",
      title: "Вы гражданин России?",
      hint: "Для иностранных студентов маршрут другой: миграционный учёт, страховка.",
      isAnswered: (d) => Boolean(d.citizenship),
      render: (d, set) => (
        <Choices<Citizenship>
          options={[
            { value: "RU", label: "Да, гражданин РФ" },
            { value: "FOREIGN", label: "Нет, я иностранный студент" },
          ]}
          value={d.citizenship}
          onChange={(citizenship) => set({ citizenship })}
        />
      ),
    },
    {
      id: "region",
      title: "Куда вы переехали?",
      hint: "Регион, где вы учитесь и живёте сейчас.",
      isAnswered: (d) => regions.some((region) => region.code === d.region_code),
      render: (d, set) => (
        <RegionPicker
          regions={regions}
          value={d.region_code}
          onChange={(region_code) =>
            // A university belongs to a region: reset it when the region changes.
            set({
              region_code,
              university_code: region_code === d.region_code ? d.university_code : undefined,
            })
          }
        />
      ),
    },
    {
      id: "university",
      title: "Где вы учитесь?",
      hint: "Для вузов-партнёров добавим их официальные памятки: общежитие, стипендии.",
      isAnswered: (d) => d.university_code !== undefined,
      render: (d, set) => (
        <Choices
          options={[
            ...inRegion(d).map((item) => ({ value: item.code, label: item.title })),
            { value: NO_UNIVERSITY, label: "Другой вуз" },
          ]}
          value={d.university_code === null ? NO_UNIVERSITY : d.university_code}
          onChange={(code) => set({ university_code: code === NO_UNIVERSITY ? null : code })}
        />
      ),
    },
    {
      id: "age",
      title: "Сколько вам лет?",
      hint: "Возраст влияет на доступные программы, например «Пушкинскую карту».",
      isAnswered: (d) => typeof d.age === "number" && d.age >= 14 && d.age <= 100,
      render: (d, set) => (
        <input
          className="input"
          type="number"
          inputMode="numeric"
          min={14}
          max={100}
          placeholder="Например, 18"
          value={d.age ?? ""}
          onChange={(event) => {
            const value = event.target.value;
            set({ age: value === "" ? undefined : Number(value) });
          }}
          aria-label="Возраст"
        />
      ),
    },
    {
      id: "education",
      title: "Форма обучения",
      isAnswered: (d) => Boolean(d.education_type),
      render: (d, set) => (
        <Choices<EducationType>
          options={[
            { value: "FULL_TIME", label: "Очная" },
            { value: "PART_TIME", label: "Очно-заочная или заочная" },
          ]}
          value={d.education_type}
          onChange={(education_type) => set({ education_type })}
        />
      ),
    },
    {
      id: "housing",
      title: "Где вы живёте?",
      isAnswered: (d) => Boolean(d.housing_type),
      render: (d, set) => (
        <Choices<HousingType>
          options={[
            { value: "DORMITORY", label: "В общежитии" },
            { value: "RENT", label: "Снимаю квартиру или комнату" },
            { value: "RELATIVES", label: "У родственников" },
            { value: "OTHER", label: "Другое" },
          ]}
          value={d.housing_type}
          onChange={(housing_type) => set({ housing_type })}
        />
      ),
    },
    {
      id: "registration",
      title: "Есть ли у вас регистрация по новому адресу?",
      hint: "Временная регистрация по месту пребывания. Для иностранных студентов — миграционный учёт.",
      isAnswered: (d) => typeof d.has_registration === "boolean",
      render: (d, set) => (
        <Choices
          options={YES_NO}
          value={d.has_registration}
          onChange={(has_registration) => set({ has_registration })}
        />
      ),
    },
    {
      id: "clinic",
      title: "Вы прикреплены к поликлинике в новом городе?",
      isAnswered: (d) => typeof d.has_clinic_attachment === "boolean",
      render: (d, set) => (
        <Choices
          options={YES_NO}
          value={d.has_clinic_attachment}
          onChange={(has_clinic_attachment) => set({ has_clinic_attachment })}
        />
      ),
    },
  ];
  return questions;
}

interface Props {
  initial: Draft | null;
  regions: Region[];
  universities: University[];
  onSubmit: (profile: Profile) => Promise<void>;
  onCancel?: () => void;
  error: string | null;
}

export function OnboardingPage({
  initial,
  regions,
  universities,
  onSubmit,
  onCancel,
  error,
}: Props) {
  const [draft, setDraft] = useState<Draft>(initial ?? {});
  const [index, setIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const all = useMemo(() => buildQuestions(regions, universities), [regions, universities]);
  // The university question is shown only when the region has partner universities.
  const questions = all.filter(
    (question) =>
      question.id !== "university" ||
      universities.some((item) => item.region_code === draft.region_code),
  );
  const current = Math.min(index, questions.length - 1);
  const question = questions[current];
  const isLast = current === questions.length - 1;
  const answered = question.isAnswered(draft);

  const next = async () => {
    if (!answered) return;
    if (!isLast) {
      setIndex(current + 1);
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({ ...draft, university_code: draft.university_code ?? null } as Profile);
    } finally {
      setSubmitting(false);
    }
  };

  const back = () => (current === 0 ? onCancel?.() : setIndex(current - 1));

  return (
    <Screen
      footer={
        <div className="footer-row">
          {current > 0 || onCancel ? (
            <Button variant="ghost" onClick={back} disabled={submitting}>
              Назад
            </Button>
          ) : null}
          <Button onClick={next} disabled={!answered} loading={submitting}>
            {isLast ? "Составить маршрут" : "Далее"}
          </Button>
        </div>
      }
    >
      <div className="wizard">
        <div className="wizard__meta">
          <span>
            {current + 1} / {questions.length}
          </span>
          <div className="wizard__dots" aria-hidden>
            {questions.map((item, i) => (
              <span key={item.id} className={i <= current ? "dot dot--active" : "dot"} />
            ))}
          </div>
        </div>
        <h1>{question.title}</h1>
        {question.hint ? <p className="muted">{question.hint}</p> : null}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void next();
          }}
        >
          {question.render(draft, (patch) => setDraft({ ...draft, ...patch }))}
        </form>
        {error ? <Notice tone="error">{error}</Notice> : null}
      </div>
    </Screen>
  );
}
