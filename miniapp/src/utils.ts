export function createId(): string {
  // Record identifiers provide retry deduplication; authentication tokens are
  // generated with a cryptographic RNG on the server.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
    /[xy]/g,
    (character) => {
      const random = Math.floor(Math.random() * 16);
      return (character === "x" ? random : (random & 3) | 8).toString(16);
    },
  );
}

export function dateKey(date: Date): string {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}-${String(date.getUTCDate()).padStart(2, "0")}`;
}

export function addDays(value: string, amount: number): string {
  const [year, month, day] = value.split("-").map(Number);
  return dateKey(new Date(Date.UTC(year, month - 1, day + amount)));
}

export function fallbackToday(): string {
  return dateKey(new Date(Date.now() + 8 * 3600 * 1000));
}

export function monday(value: string): string {
  const day = new Date(`${value}T12:00:00Z`).getUTCDay();
  return addDays(value, -(day === 0 ? 6 : day - 1));
}

export function dateLabel(value: string): string {
  return `${Number(value.slice(5, 7))}月${Number(value.slice(8, 10))}日`;
}

export function formatMinutes(value: number): string {
  return value < 60
    ? `${value} 分钟`
    : `${Math.floor(value / 60)} 小时${value % 60 ? ` ${value % 60} 分钟` : ""}`;
}

export function percentage(correct: number, questions: number): number | null {
  return questions > 0 ? Math.round((correct / questions) * 100) : null;
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

export const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "操作未完成，请稍后重试";

export function confirmAction(
  title: string,
  content: string,
): Promise<boolean> {
  return new Promise((resolve) =>
    uni.showModal({
      title,
      content,
      confirmColor: "#45634c",
      success: (result) => resolve(result.confirm),
      fail: () => resolve(false),
    }),
  );
}

export function toast(title: string) {
  uni.showToast({ title, icon: "none", duration: 2200 });
}

export function openEditor(kind: string, query = "") {
  uni.navigateTo({
    url: `/pages/editor/index?kind=${kind}${query ? `&${query}` : ""}`,
  });
}
