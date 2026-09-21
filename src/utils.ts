import type { TimerState } from "./types";

export function dateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function studyToday(timeZone = "Asia/Shanghai"): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) =>
    parts.find((item) => item.type === type)!.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function addDays(value: string, amount: number): string {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + amount);
  return dateKey(date);
}

export function monday(value: string): string {
  const day = new Date(`${value}T12:00:00`).getDay();
  return addDays(value, -(day === 0 ? 6 : day - 1));
}

export function dateLabel(
  value: string,
  options: Intl.DateTimeFormatOptions = { month: "long", day: "numeric" },
): string {
  return new Intl.DateTimeFormat("zh-CN", options).format(
    new Date(`${value}T12:00:00`),
  );
}

export function formatMinutes(value: number): string {
  if (value < 60) return `${value} 分钟`;
  const remainder = value % 60;
  return `${Math.floor(value / 60)} 小时${remainder ? ` ${remainder} 分钟` : ""}`;
}

export function percentage(correct: number, questions: number): number | null {
  return questions > 0 ? Math.round((correct / questions) * 100) : null;
}

export function elapsedSeconds(
  timer: TimerState | null,
  timestamp: number,
): number {
  if (!timer) return 0;
  const running =
    timer.started_at === null
      ? 0
      : Math.max(0, (timestamp - timer.started_at) / 1000);
  return Math.min(86400, Math.floor(timer.elapsed + running));
}

export function clockText(seconds: number): string {
  return [
    Math.floor(seconds / 3600),
    Math.floor((seconds % 3600) / 60),
    seconds % 60,
  ]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}
