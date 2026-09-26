export type Citizenship = "RU" | "FOREIGN";
export type EducationType = "FULL_TIME" | "PART_TIME";
export type HousingType = "DORMITORY" | "RENT" | "RELATIVES" | "OTHER";
export type RouteStatus = "ACTIVE" | "COMPLETED" | "ARCHIVED";
export type StepStatus = "TODO" | "IN_PROGRESS" | "DONE" | "SKIPPED";
export type StepCategory =
  | "REGISTRATION"
  | "HEALTHCARE"
  | "EDUCATION"
  | "TRANSPORT"
  | "SOCIAL_SUPPORT"
  | "OTHER";
export type SourceType = "OFFICIAL" | "MOCK" | "OTHER";

export interface Profile {
  age: number;
  region_code: string;
  education_type: EducationType;
  housing_type: HousingType;
  has_registration: boolean;
  has_clinic_attachment: boolean;
  citizenship: Citizenship;
  university_code: string | null;
}

export type RegionalService = "mfc" | "tfoms" | "student_transport";

export interface Region {
  code: string;
  title: string;
  popular: boolean;
  /** Official regional data the route uses for this region. */
  services: RegionalService[];
}

export interface University {
  code: string;
  title: string;
  short_title: string;
  region_code: string;
  kind: "university" | "college";
  partner: boolean;
  popular: boolean;
}

export interface AppConfig {
  bot_username: string | null;
  bot_url: string | null;
}

export interface RouteStepSummary {
  id: string;
  code: string;
  title: string;
  short_description: string;
  category: StepCategory;
  position: number;
  status: StepStatus;
  is_required: boolean;
  estimated_duration: number | null;
  deadline: string | null;
}

export interface Route {
  id: string;
  status: RouteStatus;
  scenario_code: string;
  scenario_version: number;
  created_at: string;
  completed_at: string | null;
  progress: { completed: number; total: number; percent: number };
  next_step_id: string | null;
  steps: RouteStepSummary[];
}

export interface Source {
  id: string;
  title: string;
  url: string;
  organization: string;
  source_type: SourceType;
  region_code: string | null;
  published_at: string | null;
  checked_at: string | null;
}

export interface StepDetail {
  id: string;
  route_id: string;
  code: string;
  title: string;
  short_description: string;
  full_description: string;
  reason: string;
  location: string;
  category: StepCategory;
  estimated_duration: number | null;
  is_required: boolean;
  position: number;
  status: StepStatus;
  deadline: string | null;
  deadline_origin: string | null;
  completed_at: string | null;
  documents: { code: string; title: string; description: string; required: boolean }[];
  sources: Source[];
  next_step_id: string | null;
}

export interface AuthResponse {
  access_token: string;
  start_param: string | null;
}

export interface ChecklistDocument {
  code: string;
  title: string;
  description: string;
  required: boolean;
}

export interface ChecklistGroup {
  place: string;
  steps: string[];
  documents: ChecklistDocument[];
}

export interface Checklist {
  groups: ChecklistGroup[];
}

export interface SharedProgress {
  status: RouteStatus;
  progress: { completed: number; total: number; percent: number };
  created_at: string;
  completed_at: string | null;
  steps: { title: string; category: StepCategory; status: StepStatus; completed_at: string | null }[];
}

export interface HelpTopic {
  code: string;
  title: string;
  summary: string;
  actions: string[];
  phones: { label: string; number: string }[];
  sources: { title: string; url: string; organization: string }[];
}
