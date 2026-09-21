export interface Profile {
  id: number;
  name: string;
  exam_name: string;
  exam_date: string | null;
  daily_goal_minutes: number;
}

export interface Subject {
  id: string;
  name: string;
  kind: "practice" | "essay";
  color: string;
  position: number;
}

export interface Plan {
  id: string;
  title: string;
  subject_id: string;
  scheduled_date: string;
  minutes: number;
  note: string;
  completed: boolean;
  created_at: string;
}

export interface StudyLog {
  id: string;
  title: string;
  subject_id: string;
  study_date: string;
  duration_minutes: number;
  question_count: number;
  correct_count: number;
  note: string;
  plan_id: string | null;
  created_at: string;
}

export type Rating = "again" | "hard" | "good" | "easy";
export interface ReviewItem {
  id: string;
  title: string;
  subject_id: string;
  note: string;
  source: string;
  due_date: string;
  interval_days: number;
  review_count: number;
  last_rating: Rating | null;
  archived: boolean;
  version: number;
  interval_options: Record<Rating, number>;
  created_at: string;
}

export interface ReviewAttempt {
  id: string;
  rating: Rating;
  next_interval_days: number;
  reviewed_at: string;
}

export interface Totals {
  minutes: number;
  sessions: number;
  questions: number;
  correct: number;
}
export interface Daily extends Totals {
  date: string;
}
export interface Overview {
  date: string;
  timezone: string;
  profile: Profile;
  today: Totals & { reviews: number };
  total_minutes: number;
  total_days: number;
  streak: number;
  days_until_exam: number | null;
  daily: Daily[];
  subject_totals: (Totals & { subject_id: string })[];
  review_due: number;
}

export type Page =
  "today" | "plan" | "review" | "records" | "insights" | "settings";
export type EditorMode = "log" | "plan" | "review" | "profile" | "subject";
export interface TimerState {
  id: string;
  title: string;
  subject_id: string;
  plan_id: string | null;
  study_date: string;
  elapsed: number;
  started_at: number | null;
}

export interface AuthStatus {
  account: { id: string; username: string | null } | null;
  local_mode: boolean;
  csrf_token: string | null;
  can_register: boolean;
  first_account: boolean;
  requires_bootstrap: boolean;
  registration_open: boolean;
}

export interface Workspace {
  auth: AuthStatus;
  overview: Overview;
  subjects: Subject[];
  plans: Plan[];
  logs: StudyLog[];
  reviews: ReviewItem[];
}

export type BackupCollection =
  "subjects" | "plans" | "logs" | "reviews" | "review_history";
export interface ImportPreview {
  id: string;
  mode: "merge" | "replace";
  expires_at: string;
  profile_changed: boolean;
  profile: Profile;
  counts: Record<
    BackupCollection,
    {
      current: number;
      incoming: number;
      new: number;
      duplicate: number;
      conflict: number;
    }
  >;
}
export interface BackupSnapshot {
  id: string;
  purpose: "before-restore" | "before-upgrade";
  size_bytes: number;
  created_at: string;
}
