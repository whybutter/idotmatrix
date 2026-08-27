// Simple line-style SVG icons matching the app's outline aesthetic.
import type { JSX } from "react";

type P = { size?: number };
const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export const IconColor = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.5-1 1-1.8-.5-.8-.2-1.7.8-1.7H16a5 5 0 0 0 5-5c0-5-4-9.5-9-9.5Z" />
    <circle cx="7.5" cy="10.5" r="1" fill="currentColor" />
    <circle cx="12" cy="7.5" r="1" fill="currentColor" />
    <circle cx="16.5" cy="10.5" r="1" fill="currentColor" />
  </svg>
);

export const IconText = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M8 9h8M12 9v6" />
    <path d="M3 4l1.5 1.5M21 4l-1.5 1.5M3 20l1.5-1.5M21 20l-1.5-1.5" />
  </svg>
);

export const IconImage = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="8.5" cy="9" r="1.5" />
    <path d="M21 16l-5-5-7 7" />
  </svg>
);

export const IconClock = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

export const IconEffect = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" />
    <circle cx="12" cy="12" r="3.2" />
  </svg>
);

export const IconGif = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M9 9.5A2.5 2.5 0 1 0 9 14.5M13 9v6M17 9h-2v6M15 12h1.5" />
  </svg>
);

export const IconScore = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <path d="M12 6v12M7 10v4M17 10v4" />
  </svg>
);

export const IconTimer = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <path d="M6 3l12 18H6L18 3" />
    <path d="M8 3h8M8 21h8" />
  </svg>
);

export const IconAlbum = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <rect x="7" y="8" width="10" height="8" rx="1" />
    <path d="M6 4v16" />
  </svg>
);

export const IconMic = ({ size = 30 }: P): JSX.Element => (
  <svg {...base(size)}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M6 11a6 6 0 0 0 12 0M12 17v4M9 21h6" />
  </svg>
);

export const IconBrightness = ({ size = 18 }: P): JSX.Element => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4" />
  </svg>
);

export const IconPower = ({ size = 22 }: P): JSX.Element => (
  <svg {...base(size)}>
    <path d="M12 4v8" />
    <path d="M7.5 7a7 7 0 1 0 9 0" />
  </svg>
);

export const IconSpinner = ({ size = 16 }: P): JSX.Element => (
  <svg width={size} height={size} viewBox="0 0 24 24" className="idot-spin" aria-hidden>
    <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth={2.4} opacity={0.25} />
    <path
      d="M21 12a9 9 0 0 0-9-9"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.4}
      strokeLinecap="round"
    />
  </svg>
);

export const IconCheck = ({ size = 16 }: P): JSX.Element => (
  <svg {...base(size)} strokeWidth={2.4}>
    <path d="M5 12.5l4.5 4.5L19 6.5" />
  </svg>
);

export const IconAlert = ({ size = 16 }: P): JSX.Element => (
  <svg {...base(size)} strokeWidth={2.2}>
    <path d="M12 8v5M12 16.5v.01" />
    <circle cx="12" cy="12" r="9" />
  </svg>
);

export const IconDevice = ({ size = 24 }: P): JSX.Element => (
  <svg {...base(size)}>
    <rect x="2.5" y="5" width="13" height="10" rx="1.5" />
    <rect x="17" y="8" width="4.5" height="9" rx="1" />
  </svg>
);
