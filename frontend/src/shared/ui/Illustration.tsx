/**
 * Calm landscape used across the app: sun, soft hills, a house and a path.
 * Pure SVG (no external assets) so it renders the same in MAX and in the browser.
 * Colours come from CSS variables, so it follows the light and dark themes.
 */

type Scene = "welcome" | "route" | "done";

export function Illustration({ scene, progress = 0 }: { scene: Scene; progress?: number }) {
  // The walker moves along the path as the route progresses.
  const t = Math.max(0, Math.min(1, progress / 100));
  const walkerX = 70 + t * 170;
  const walkerY = 150 - t * 52;

  return (
    <div className={`art art--${scene}`} aria-hidden>
      <svg viewBox="0 0 320 170" preserveAspectRatio="xMidYMid slice" role="presentation">
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0.4" y2="1">
            <stop offset="0" stopColor="var(--art-sky-top)" />
            <stop offset="1" stopColor="var(--art-sky-bottom)" />
          </linearGradient>
        </defs>
        <rect width="320" height="170" fill="url(#sky)" />
        <circle cx="258" cy="46" r={scene === "done" ? 30 : 24} fill="var(--art-sun)" />
        {scene === "done" ? (
          <g stroke="var(--art-sun)" strokeWidth="4" strokeLinecap="round" opacity="0.7">
            <line x1="258" y1="4" x2="258" y2="12" />
            <line x1="300" y1="46" x2="292" y2="46" />
            <line x1="288" y1="16" x2="282" y2="22" />
            <line x1="228" y1="16" x2="234" y2="22" />
          </g>
        ) : null}
        <ellipse cx="60" cy="200" rx="170" ry="95" fill="var(--art-hill-back)" />
        <ellipse cx="290" cy="215" rx="190" ry="100" fill="var(--art-hill-front)" />

        {/* Path from the bottom-left towards the house. */}
        <path
          d="M40 172 C 90 150, 120 150, 170 128 S 230 104, 246 98"
          fill="none"
          stroke="var(--art-path)"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={scene === "welcome" ? "2 14" : undefined}
        />

        {/* House. */}
        <g transform="translate(236 64)">
          <rect x="0" y="16" width="34" height="26" rx="3" fill="var(--art-house)" />
          <path d="M-4 18 L17 0 L38 18 Z" fill="var(--art-roof)" />
          <rect x="13" y="28" width="9" height="14" rx="2" fill="var(--art-door)" />
          <rect x="4" y="22" width="7" height="6" rx="1" fill="var(--art-window)" />
          {scene === "done" ? (
            <g>
              <line x1="30" y1="2" x2="30" y2="-18" stroke="var(--art-roof)" strokeWidth="2" />
              <path d="M30 -18 L44 -13 L30 -8 Z" fill="var(--art-flag)" />
            </g>
          ) : null}
        </g>

        {scene === "route" ? (
          <g transform={`translate(${walkerX} ${walkerY})`}>
            <circle r="9" fill="var(--art-walker)" />
            <circle r="3.5" cy="-2" fill="var(--art-house)" />
          </g>
        ) : null}

        {/* Birds. */}
        <g fill="none" stroke="var(--art-bird)" strokeWidth="2" strokeLinecap="round">
          <path d="M60 40 q6 -6 12 0 q6 -6 12 0" />
          <path d="M104 60 q4 -4 8 0 q4 -4 8 0" />
        </g>
      </svg>
    </div>
  );
}
