/**
 * Date formatting, shared by the engine and the screens.
 *
 * It lives here rather than in `ui/` because the engine writes dates into the
 * reasons it gives a person — and a reason that says "2026-08-15" inside an
 * itinerary where every other date reads "Saturday, 15 August" looks like a
 * different system talking.
 */
export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const WEEKDAYS = [
  "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
];

export function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

/** "8 June" — for places where the year is already in context. */
export function formatDayMonth(iso: string): string {
  const [, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTHS[month - 1]}`;
}

export function formatWeekday(iso: string): string {
  return WEEKDAYS[new Date(`${iso}T00:00:00Z`).getUTCDay()];
}
