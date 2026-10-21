import type { ReactElement } from "react";

/**
 * Inline stroke SVG on a 24px grid, 1.8–2px stroke (handoff §7).
 * No emoji, no icon font.
 */
type Name =
  | "price" | "quotes" | "admin" | "question" | "quote" | "check"
  | "arrowRight" | "close" | "again" | "file" | "reset" | "download"
  | "transfer" | "experience" | "hotel" | "free";

const PATHS: Record<Name, ReactElement> = {
  price: <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M4 21h16" /></>,
  quotes: <><path d="M4 5h16" /><path d="M4 12h16" /><path d="M4 19h10" /></>,
  admin: <><path d="M4 7h10" /><path d="M18 7h2" /><path d="M4 17h4" /><path d="M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></>,
  question: <><circle cx="12" cy="12" r="9" /><path d="M9.6 9.4a2.5 2.5 0 1 1 3.3 2.4c-.6.2-.9.6-.9 1.2v.4" /><path d="M12 16.6h.01" /></>,
  quote: <path d="M4 4h16v12H7l-3 3z" />,
  check: <path d="m5 13 4 4L19 7" />,
  arrowRight: <><path d="M5 12h13" /><path d="m12 5 7 7-7 7" /></>,
  close: <><path d="M6 6l12 12" /><path d="M18 6 6 18" /></>,
  again: <><path d="M21 12a9 9 0 1 1-3.2-6.9" /><path d="M21 4v5h-5" /></>,
  file: <><path d="M14 3v5h5" /><path d="M14 3H6v18h12V8z" /></>,
  reset: <><path d="M3 12a9 9 0 1 0 3.2-6.9" /><path d="M3 4v5h5" /></>,
  download: <><path d="M12 4v11" /><path d="m7 11 5 5 5-5" /><path d="M5 20h14" /></>,
  transfer: <><path d="M5 17h14" /><path d="M6 17v-4l2-4h8l2 4v4" /><circle cx="8.5" cy="17" r="1.5" /><circle cx="15.5" cy="17" r="1.5" /></>,
  experience: <><path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11z" /><circle cx="12" cy="10" r="2.5" /></>,
  hotel: <><path d="M3 19v-7h18v7" /><path d="M3 12V6" /><path d="M21 19v2" /><path d="M3 19v2" /><path d="M7 12V9h6v3" /></>,
  free: <><circle cx="12" cy="12" r="9" /><path d="M12 7.5V12l3 1.8" /></>,
};

export function Icon({
  name,
  size = 18,
  color = "currentColor",
  strokeWidth = 1.8,
}: {
  name: Name;
  size?: number;
  color?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      {PATHS[name]}
    </svg>
  );
}
