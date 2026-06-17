# UI Specification — Observatory Design

RepoLens uses the **Observatory** design concept. Think of looking at code the way an astronomer
looks at the sky: a dark environment that makes the signal stand out, precision instruments for
exploration, and data that is presented with rigour. The UI must feel professional and distinctive
— not a ChatGPT clone, not a generic dashboard, not a plain white SaaS app.

---

## Design Principles

1. **Dark by default.** The background is near-black. Text is light. Code is the star.
2. **Data density with breathing room.** Show a lot of information without feeling cluttered.
   Use whitespace deliberately, not abundantly.
3. **Animate with purpose.** Every animation communicates state (indexing progress, answer
   streaming, grounding score revealing). No decorative animations.
4. **Colour as signal.** The colour palette has exactly one accent (the purple-to-blue gradient).
   All other colours carry semantic meaning (success, warning, danger, language type).
5. **Typography hierarchy is clear.** One font family. Four size steps. Two weights. No exceptions.

---

## Colour Palette

Define these as CSS variables in `frontend/src/styles/globals.css` and in `tailwind.config.ts`.

```css
:root {
  /* Backgrounds */
  --bg-void:      #070B0F;  /* True space — page background */
  --bg-base:      #0D1117;  /* Primary surface */
  --bg-elevated:  #161B22;  /* Cards, panels */
  --bg-muted:     #1C2128;  /* Input backgrounds, subtle surfaces */
  --bg-glass:     rgba(22, 27, 34, 0.7); /* Glass morphism panels */

  /* Borders */
  --border-subtle:  #21262D;  /* Separators */
  --border-default: #30363D;  /* Card borders, input borders */
  --border-strong:  #3D444D;  /* Hover states */

  /* Text */
  --text-primary:   #E6EDF3;
  --text-secondary: #8B949E;
  --text-muted:     #484F58;
  --text-inverse:   #0D1117;  /* Text on light/gradient backgrounds */

  /* Accent — the Observatory signature */
  --accent-purple:  #8B5CF6;
  --accent-blue:    #3B82F6;
  --accent-grad: linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%);

  /* Semantic */
  --color-success: #3FB950;
  --color-warning: #D29922;
  --color-danger:  #F85149;
  --color-info:    #58A6FF;

  /* Language colours — used in CitationCard and file tree */
  --lang-py:   #60A5FA;  /* Python blue */
  --lang-ts:   #34D399;  /* TypeScript teal */
  --lang-go:   #67E8F9;  /* Go cyan */
  --lang-rs:   #FB923C;  /* Rust orange */
  --lang-js:   #FBBF24;  /* JavaScript amber */
  --lang-c:    #A78BFA;  /* C/C++ purple */
  --lang-java: #F472B6;  /* Java pink */
  --lang-md:   #94A3B8;  /* Markdown grey */
}
```

### Tailwind config extension (`tailwind.config.ts`)
```typescript
import type { Config } from 'tailwindcss'

export default {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#070B0F',
        base: '#0D1117',
        elevated: '#161B22',
        muted: '#1C2128',
        'border-subtle': '#21262D',
        'border-default': '#30363D',
        'border-strong': '#3D444D',
        'text-primary': '#E6EDF3',
        'text-secondary': '#8B949E',
        'text-muted': '#484F58',
        'accent-purple': '#8B5CF6',
        'accent-blue': '#3B82F6',
        success: '#3FB950',
        warning: '#D29922',
        danger: '#F85149',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      backgroundImage: {
        'accent-grad': 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)',
        'card-grad': 'linear-gradient(180deg, #161B22 0%, #0D1117 100%)',
      },
      backdropBlur: {
        glass: '12px',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'stream-cursor': 'blink 1s step-end infinite',
        'ring-fill': 'ringFill 0.8s ease-out forwards',
      },
      keyframes: {
        blink: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0' } },
        ringFill: { from: { 'stroke-dashoffset': '100' }, to: {} },
      },
    },
  },
  plugins: [],
} satisfies Config
```

---

## Typography

**Font imports** in `index.html`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

| Use | Family | Size | Weight | Class |
|---|---|---|---|---|
| Page headings | Inter | 20px | 500 | `text-xl font-medium` |
| Section headings | Inter | 16px | 500 | `text-base font-medium` |
| Body text | Inter | 14px | 400 | `text-sm` |
| Caption / muted | Inter | 12px | 400 | `text-xs text-text-secondary` |
| Code blocks | JetBrains Mono | 13px | 400 | `font-mono text-[13px]` |
| Inline code | JetBrains Mono | 12px | 400 | `font-mono text-xs` |

---

## Layout

```
┌────────────────────────────────────────────────────┐
│ Sidebar (240px fixed)    │ Main content (flex-1)   │
│                          │                          │
│ Logo (gradient text)     │ [Page-specific content]  │
│                          │                          │
│ ─── Navigation ───       │                          │
│ ◈ Repositories           │                          │
│ ◈ [repo name]            │                          │
│   └ Chat                 │                          │
│   └ Drift Report         │                          │
│                          │                          │
│ ─── Bottom ───           │                          │
│ Settings                 │                          │
└────────────────────────────────────────────────────┘
```

- `Layout.tsx` wraps all pages. Sidebar is always visible.
- The sidebar uses `border-r border-border-subtle` and `bg-base` background.
- Active nav item: `bg-muted rounded-lg` + left border: `border-l-2 border-accent-purple`
- Logo: "RepoLens" in gradient text: `bg-accent-grad bg-clip-text text-transparent`

---

## Component Specifications

### RepoCard
A card for each indexed repository on the Repo Manager page.

```
┌──────────────────────────────┐
│  [◉ orb]  repo-name          │
│           github.com/org/repo │
│                               │
│  ████████████░░  68%         │
│  847 chunks · 3 langs · 2h   │
└──────────────────────────────┘
```

- Background: `bg-elevated border border-border-default rounded-xl`
- The "orb" is a 40×40 circle with a gradient background. The gradient is deterministic from the
  repo name (use a simple hash to pick a start hue, rotate 60° for end hue). CSS:
  `background: conic-gradient(from 180deg, hsl(${hue}deg 70% 60%), hsl(${hue+60}deg 60% 50%))`
- Status dot: 8×8 circle, `bg-success animate-pulse-slow` when indexing, `bg-success` when done,
  `bg-text-muted` when not indexed
- Progress bar: `bg-muted rounded-full` track, `bg-accent-grad rounded-full` fill
- On hover: `border-border-strong scale-[1.01]` with `transition-all duration-200`
- Click → navigate to Chat for that repo

### ChatMessage

**User message:**
```
                       [avatar] You asked
                       ──────────────────────────────
                       how does request routing work?
```
Aligned right, `bg-muted rounded-2xl rounded-tr-sm px-4 py-3 max-w-[70%] ml-auto`

**System answer:**
```
[lens icon] RepoLens
───────────────────────────────────────────────────
The router matches incoming requests by pattern...
[code block: router.go:42-67]
...and dispatches to registered handlers [router.go:72-89].

[citation cards expand here]

[grounding ring] 94% grounded
```

- Container: `bg-elevated border border-border-subtle rounded-2xl rounded-tl-sm p-4 max-w-full`
- Streaming cursor: a `|` span with `animate-stream-cursor` shown while tokens are arriving
- Inline citation chips: `[router.go:42-67]` styled as `font-mono text-xs bg-muted text-lang-go
  border border-border-default rounded px-1.5 py-0.5 cursor-pointer hover:border-accent-purple`
- Click on chip → expand the CitationCard below

### CitationCard

```
┌─ pkg/router.go  •  handleRoute  •  Go  •  lines 42–67 ──────┐
│                                                                │
│  func handleRoute(w http.ResponseWriter, r *http.Request) {   │
│      pattern := r.URL.Path                                     │
│      ...                                                       │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘
```

- Container: `bg-muted border-l-2 border-lang-go rounded-lg overflow-hidden mt-2`
- Header: `flex items-center gap-2 px-3 py-2 border-b border-border-subtle text-xs`
  - File path: `text-text-secondary font-mono`
  - Symbol name: `text-text-primary font-medium`
  - Language badge: `text-[10px] px-1.5 py-0.5 rounded bg-base` coloured by `--lang-{language}`
  - Line range: `text-text-muted`
- Code area: uses `react-syntax-highlighter` with a custom dark theme matching Observatory colours.
  The relevant lines are highlighted with a subtle `bg-accent-purple/10` background.
- Animate in: `animate-in fade-in slide-in-from-top-1 duration-200` (use Tailwind animate plugin
  or simple CSS transition)

### GroundingBadge

A circular SVG progress ring that animates from 0% to the actual score on mount.

```
    ╭──╮
   ╱ 94 ╲
   ╲  % ╱
    ╰──╯
```

- SVG: 52×52px. Two concentric circles: track (muted) and fill (coloured).
- Colour by verdict:
  - `high` (≥0.8): `#3FB950` (success green)
  - `medium` (≥0.6): `#D29922` (warning amber)
  - `low` (≥0.4): `#F85149` (danger red)
  - `none`: `#484F58` (muted)
- The fill circle uses `stroke-dasharray` + `stroke-dashoffset` animated with CSS.
- Label inside: score as integer percent, `font-mono text-xs font-medium`
- Below the ring: `"N% grounded"` in `text-xs text-text-secondary`

### IndexProgress

While a repo is being indexed:

```
[████████████████████████░░░░░░░░░] 847 / 1203 files
Parsing  src/repolens/ingestion/parser.py ...
```

- Fixed top bar: `fixed top-0 left-0 right-0 h-0.5 bg-border-subtle z-50`
  - Inner fill: `bg-accent-grad transition-all duration-300` (width = progress %)
- Detail panel (below header in main content, when indexing is active):
  `bg-muted/50 backdrop-blur-glass border border-border-subtle rounded-lg p-4`
  - File counter: large, `text-2xl font-medium text-text-primary`
  - Current file: `font-mono text-xs text-text-secondary truncate`

### DriftFinding

```
┌─────────────────────────────────────────────────────────────┐
│ ● CONTRADICTED                                               │
│                                                              │
│ LEFT: README.md line 42          RIGHT: pkg/config.go:17    │
│ ─────────────────                ──────────────────────────  │
│ "the default timeout             const defaultTimeout =      │
│  is 30 seconds"                  10 * time.Second           │
└─────────────────────────────────────────────────────────────┘
```

- Status badge (top-left):
  - CONTRADICTED: `bg-danger/10 text-danger border border-danger/30`
  - NOT_FOUND: `bg-warning/10 text-warning border border-warning/30`
  - SUPPORTED: `bg-success/10 text-success border border-success/30`
- Two-column layout inside: `grid grid-cols-2 gap-4`
- Left (doc claim): amber-tinted background `bg-warning/5 border-l-2 border-warning`
- Right (code): blue-tinted background `bg-info/5 border-l-2 border-info`
- Both show: location header (path:line) + content (italic for doc claim, monospace for code)

---

## Interaction States

| State | Visual |
|---|---|
| Default | `border-border-default` |
| Hover | `border-border-strong` + `scale-[1.01]` |
| Active / selected | `border-accent-purple` + `bg-muted` |
| Loading | Skeleton shimmer: `animate-pulse bg-muted rounded` |
| Error | `border-danger` + red error message below |
| Success | `border-success` momentarily, then returns to default |

---

## Page-Level Background

The app background (`bg-void`, `#070B0F`) uses a subtle radial gradient to suggest depth:
```css
body {
  background: radial-gradient(ellipse 80% 60% at 50% -10%, #12082A 0%, #070B0F 60%);
}
```

This creates a very faint purple glow at the top of the screen — the "observatory dome" effect.
It's subtle enough to not distract but gives the UI a distinctive atmosphere.

---

## Glassmorphism Panels

Modals, dropdowns, and overlaid panels use glass morphism:
```css
.glass {
  background: rgba(22, 27, 34, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(48, 54, 61, 0.6);
}
```

Use sparingly — only for elements that float above the content layer (modals, tooltips,
command palette if added).

---

## Icons

Use `lucide-react` throughout. Key icons used:
- Repo: `BookOpen`
- Chat: `MessageSquare`
- Drift: `GitCompare`
- Add: `Plus`
- Delete: `Trash2`
- Indexing: `RefreshCw` (spinning)
- Done: `CheckCircle`
- Error: `AlertCircle`
- Citation: `Link2`
- Settings: `Settings`
- Logo accent: `Telescope`

All icons at 16px for inline, 20px for nav items, 24px for headings/empty states.
Stroke width: 1.5 (default lucide). Colour: `text-text-secondary`, active: `text-text-primary`.

---

## Empty States

Each page needs a designed empty state (not just "No data").

**Repo Manager (no repos):**
- Large `Telescope` icon (48px, gradient fill using SVG linearGradient)
- Heading: "No repositories indexed yet"
- Body: "Add a GitHub repository or local path to start asking questions"
- CTA button: gradient background `bg-accent-grad text-white rounded-lg px-4 py-2`

**Chat (no messages):**
- `MessageSquare` icon (40px)
- Heading: "Ask anything about [repo name]"
- Three suggested questions as clickable chips (hardcoded to: "How does authentication work?",
  "What is the entry point?", "How are errors handled?")

**Drift Report (never run):**
- `GitCompare` icon (40px)
- Heading: "No drift report yet"
- Body: "Run a drift check to find where documentation disagrees with the code"
- CTA: "Run Drift Check"

---

## Accessibility

- All interactive elements must have `focus-visible:outline` with `outline-accent-purple`
- `aria-label` on all icon-only buttons
- Colour is never the only indicator of status — always pair with text or icon
- Motion: respect `prefers-reduced-motion` — disable animations when set
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: 0.01ms !important; }
  }
  ```
