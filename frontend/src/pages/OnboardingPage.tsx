import { type ReactElement, useState } from "react";

import type { EducationType, HousingType, Profile } from "../shared/api/types";
import { REGIONS } from "../shared/labels";
import { Button, Notice, Screen } from "../shared/ui";

type Draft = Partial<Profile>;

interface Option<T> {
  value: T;
  label: string;
}

interface Question {
  title: string;
  hint?: string;
  isAnswered: (draft: Draft) => boolean;
  render: (draft: Draft, set: (patch: Draft) => void) => ReactElement;
}

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

const QUESTIONS: Question[] = [
  {
    title: "Куда вы переехали?",
    isAnswered: (d) => Boolean(d.region_code),
    render: (d, set) => (
      <Choices
        options={REGIONS.map((region) => ({ value: region.code, label: region.title }))}
        value={d.region_code}
        onChange={(region_code) => set({ region_code })}
      />
    ),
  },
  {
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
    title: "Есть ли у вас регистрация в новом регионе?",
    hint: "Временная регистрация по месту пребывания или постоянная.",
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

interface Props {
  initial: Profile | null;
  onSubmit: (profile: Profile) => Promise<void>;
  onCancel?: () => void;
  error: string | null;
}

export function OnboardingPage({ initial, onSubmit, onCancel, error }: Props) {
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState<Draft>(initial ?? {});
  const [submitting, setSubmitting] = useState(false);

  const question = QUESTIONS[index];
  const isLast = index === QUESTIONS.length - 1;
  const answered = question.isAnswered(draft);

  const next = async () => {
    if (!answered) return;
    if (!isLast) {
      setIndex(index + 1);
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(draft as Profile);
    } finally {
      setSubmitting(false);
    }
  };

  const back = () => (index === 0 ? onCancel?.() : setIndex(index - 1));

  return (
    <Screen
      footer={
        <div className="footer-row">
          {index > 0 || onCancel ? (
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
            {index + 1} / {QUESTIONS.length}
          </span>
          <div className="wizard__dots" aria-hidden>
            {QUESTIONS.map((_, i) => (
              <span key={i} className={i <= index ? "dot dot--active" : "dot"} />
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
