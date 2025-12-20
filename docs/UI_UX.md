# UI/UX Design Specification

## FreightLens Terminal Interface

**Version:** 1.0  
**Last Updated:** 2024-12-19

---

## Design Philosophy

FreightLens embodies the **"Bloomberg Terminal of Trucking"** vision: a power-user interface optimized for **information density**, **keyboard efficiency**, and **rapid decision-making**. The UI prioritizes function over form, delivering maximum signal with minimum friction.

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Density** | Show more data, not less; truckers need to compare dozens of loads quickly |
| **Keyboard-First** | Every action reachable via hotkey; mouse optional |
| **Zero Latency Feel** | Optimistic updates, instant filtering, no loading spinners |
| **Glanceability** | Critical metrics (RPM, score, deadhead) visible without interaction |
| **Dark Mode Native** | Designed for dark first; reduces eye strain during night driving |

---

## Visual Language

### Color System

```
┌─────────────────────────────────────────────────────────────┐
│  BACKGROUND HIERARCHY                                        │
├─────────────────────────────────────────────────────────────┤
│  bg-primary:    #0d1117  (main background)                  │
│  bg-secondary:  #161b22  (panels, cards)                    │
│  bg-tertiary:   #21262d  (hover states, inputs)             │
│  bg-elevated:   #30363d  (modals, dropdowns)                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  SEMANTIC COLORS                                            │
├─────────────────────────────────────────────────────────────┤
│  green-light:   #3fb950  (GreenLight positive, high scores) │
│  yellow-caution:#d29922  (medium scores, warnings)          │
│  red-stop:      #f85149  (low scores, errors, hazmat)       │
│  blue-info:     #58a6ff  (links, selections, info)          │
│  purple-accent: #a371f7  (premium features, alerts)         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  TEXT HIERARCHY                                             │
├─────────────────────────────────────────────────────────────┤
│  text-primary:   #f0f6fc  (headings, important values)      │
│  text-secondary: #8b949e  (labels, descriptions)            │
│  text-muted:     #6e7681  (disabled, placeholders)          │
│  text-link:      #58a6ff  (interactive text)                │
└─────────────────────────────────────────────────────────────┘
```

### Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| Monospace Data | `JetBrains Mono`, `Fira Code` | 13px | 400 |
| Headers | `Inter`, system-ui | 14-18px | 600 |
| Body Text | `Inter`, system-ui | 13px | 400 |
| Ticker | `JetBrains Mono` | 12px | 400 |

### Iconography

Minimal icons, text-first. When used:
- Lucide icons (MIT licensed, consistent stroke width)
- 16px default, 20px for primary actions
- Paired with text labels (no icon-only buttons except toolbar)

---

## Layout Architecture

### Primary Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│ ◉ FreightLens                    [🔍 Search...] [⚙] [👤]    ░░ 15:32 CST │
├────────────────────────────────────────────────────────────────────────┤
│ ▸ BREAKING: Spot rates up 3% │ DAT: $2.45 avg │ Diesel: $3.89 ▸▸▸     │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ FILTERS                                                          │  │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │  │
│  │ │Equipment▾│ │Origin    │ │Dest      │ │RPM ≥ 2.50│ │+Filter  │ │  │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘ │  │
│  │ [Clear All]  [Save Filter]  [Load: "My Filters" ▾]              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ LOADS (247 results)                          Sort: GreenLight ▾ │  │
│  ├─────────────────────────────────────────────────────────────────┤  │
│  │ ▌SCORE│ O→D              │PICKUP     │EQUIP    │  RATE  │  RPM │  │
│  ├─────────────────────────────────────────────────────────────────┤  │
│  │ ▐ 92 ▌│ ATL,GA → CHI,IL  │12/20 08:00│Dry Van  │ $1,850 │$2.58 │◀│
│  │ │ 87  │ DAL,TX → DEN,CO  │12/20 14:00│Reefer   │ $2,100 │$2.72 │ │
│  │ │ 84  │ MIA,FL → ATL,GA  │12/21 06:00│Flatbed  │ $1,200 │$2.45 │ │
│  │ │ 79  │ LAX,CA → PHX,AZ  │12/20 10:00│Dry Van  │   $890 │$2.38 │ │
│  │ │ 75  │ SEA,WA → PDX,OR  │12/20 16:00│Reefer   │   $450 │$2.65 │ │
│  │ │ 71  │ CHI,IL → DET,MI  │12/21 08:00│Dry Van  │   $680 │$2.28 │ │
│  │ └─────┴──────────────────┴───────────┴─────────┴────────┴──────┘ │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ DETAIL PANEL (ATL,GA → CHI,IL)                         [×] [⭐] │  │
│  ├─────────────────────────────────────────────────────────────────┤  │
│  │ GreenLight Score: ████████████░░░░ 92/100                       │  │
│  │                                                                  │  │
│  │ WHY THIS SCORE:                                                 │  │
│  │  ✓ +22% RPM above market     ✓ Broker 4.2★ (156 reviews)       │  │
│  │  ✓ Lane history: 12 runs     ⚠ Pickup in 18 hours              │  │
│  │  ✓ Low deadhead: 45 mi                                          │  │
│  │                                                                  │  │
│  │ ROUTE: 716 mi │ WEIGHT: 42,000 lbs │ COMMODITY: General Freight │  │
│  │                                                                  │  │
│  │ BROKER: Acme Logistics (MC-123456)                              │  │
│  │ Days to Pay: 32 avg │ Dispute Rate: 2% │ [View Full Profile →]  │  │
│  │                                                                  │  │
│  │ [📞 Call Broker]  [📋 Copy Details]  [➕ Add to Watchlist]      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ [F1] Help  [/] Search  [W] Watchlists  [A] Alerts  [P] Portfolio      │
└────────────────────────────────────────────────────────────────────────┘
```

### Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Desktop XL | ≥1440px | 3-column: filters + list + detail |
| Desktop | ≥1024px | 2-column: list + detail (filters collapsed) |
| Tablet | ≥768px | Single column with slide-over detail |
| Mobile | <768px | Stack: filters → list → detail (sheets) |

---

## Core Workflows

### 1. Load Search & Discovery

#### Quick Search (Omnisearch)

Activated via `/` or clicking the search bar. Supports natural language and structured queries.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 🔍 atlanta to chicago dry van next week                                 │
├─────────────────────────────────────────────────────────────────────────┤
│ INTERPRETED AS:                                                         │
│   Origin: Atlanta, GA                                                   │
│   Destination: Chicago, IL                                              │
│   Equipment: Dry Van                                                    │
│   Pickup: Dec 23-29, 2024                                              │
│                                                                         │
│ [Apply Filters]  [Edit Manually]                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Search Syntax:**

| Pattern | Example | Meaning |
|---------|---------|---------|
| City to City | `atl to chi` | Origin → Destination |
| State codes | `GA FL SC` | Loads in/to these states |
| Equipment | `reefer`, `flatbed` | Equipment type |
| Price | `>$2000`, `rpm>2.5` | Rate filters |
| Time | `tomorrow`, `next week` | Pickup window |
| Broker | `@acme`, `mc:123456` | Broker filter |
| Hazmat | `hazmat`, `!hazmat` | Include/exclude hazmat |

#### Filter Bar

Persistent filter chips below the search bar:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [Dry Van ×] [ATL,GA →] [RPM ≥ $2.50 ×] [Deadhead ≤ 100mi ×] [+Add]    │
│                                                                         │
│ Saved: [My Filters ▾] ─ "High RPM Southeast" │ "Reefer CA"            │
│                                                                         │
│ [Clear All]  [Save Current]  247 loads matching                        │
└─────────────────────────────────────────────────────────────────────────┘
```

**Filter Types:**

| Filter | UI Control | Keyboard |
|--------|------------|----------|
| Equipment | Dropdown multi-select | `e` |
| Origin/Destination | City autocomplete | `o` / `d` |
| Pickup Window | Date range picker | `p` |
| Delivery Window | Date range picker | `v` |
| Rate (total) | Range slider + inputs | `r` |
| RPM | Range slider + inputs | `m` |
| Weight | Range slider | `w` |
| Deadhead | Max slider | `h` |
| Broker Rating | Min slider | `b` |
| Hazmat | Toggle | `z` |
| Detention Pay | Toggle | `t` |

#### Load List

Dense table view optimized for scanning:

```
┌───┬──────┬────────────────────┬───────────┬─────────┬────────┬───────┬─────┐
│   │SCORE │ ORIGIN → DEST      │ PICKUP    │ EQUIP   │ RATE   │ RPM   │     │
├───┼──────┼────────────────────┼───────────┼─────────┼────────┼───────┼─────┤
│ ▸ │ ██92 │ ATL,GA → CHI,IL    │ 12/20 08a │ DryVan  │ $1,850 │ $2.58 │ ⭐  │
│   │ ██87 │ DAL,TX → DEN,CO    │ 12/20 02p │ Reefer  │ $2,100 │ $2.72 │     │
│   │ █░84 │ MIA,FL → ATL,GA    │ 12/21 06a │ Flatbed │ $1,200 │ $2.45 │ ⭐  │
│   │ █░79 │ LAX,CA → PHX,AZ    │ 12/20 10a │ DryVan  │   $890 │ $2.38 │     │
│   │ █░75 │ SEA,WA → PDX,OR    │ 12/20 04p │ Reefer  │   $450 │ $2.65 │     │
│   │ ░░71 │ CHI,IL → DET,MI    │ 12/21 08a │ DryVan  │   $680 │ $2.28 │     │
└───┴──────┴────────────────────┴───────────┴─────────┴────────┴───────┴─────┘
```

**Visual Encoding:**

| Element | Encoding |
|---------|----------|
| Score bar | 5-segment fill: ██████ (90+), █████░ (80+), ████░░ (70+), etc. |
| Score color | Green (80+), Yellow (60-79), Red (<60) |
| Row selection | Blue left border `▸`, blue background tint |
| Watchlisted | Star icon `⭐` |
| Hazmat | Red `☢` badge |
| Multi-stop | `+2` badge |
| Expiring soon | Amber clock icon |

**Row Interactions:**

| Action | Trigger |
|--------|---------|
| Select row | Click, `↑`/`↓` arrows, `j`/`k` vim-style |
| Open detail | `Enter`, double-click |
| Quick add to watchlist | `s` (star) |
| Copy load ID | `c` |
| Call broker | `Shift+C` |

#### Detail Panel

Slide-in panel (right side on desktop, bottom sheet on mobile):

```
┌─────────────────────────────────────────────────────────────────────────┐
│ LOAD DETAIL                                           [Pin] [×]        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Atlanta, GA  ─────────────────────▸  Chicago, IL                      │
│  Pickup: Dec 20, 08:00-16:00          Delivery: Dec 21, 08:00-18:00   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  GREENLIGHT SCORE                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ████████████████████████████████████░░░░░░░░  92 / 100          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  SCORE BREAKDOWN                                                       │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐        │
│  │ Profitability│ Feasibility  │ Risk         │ Preference   │        │
│  │     25/30    │     24/25    │     22/25    │     21/20    │        │
│  │   ████████░░ │   █████████░ │   █████████░ │   ██████████ │        │
│  └──────────────┴──────────────┴──────────────┴──────────────┘        │
│                                                                         │
│  WHY THIS SCORE                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ✓ RPM $2.58 is 22% above lane average ($2.11)                   │   │
│  │ ✓ Deadhead 45 mi (under your 100mi max)                         │   │
│  │ ✓ Broker Acme Logistics rated 4.2★ with 32-day avg payment      │   │
│  │ ✓ You've run ATL→CHI 12 times in the past 90 days               │   │
│  │ ⚠ Pickup window starts in 18 hours (moderate urgency)           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  LOAD DETAILS                                                          │
│  ├─ Distance:      716 miles                                           │
│  ├─ Weight:        42,000 lbs                                          │
│  ├─ Equipment:     Dry Van (53')                                       │
│  ├─ Commodity:     General Freight                                     │
│  ├─ Hazmat:        No                                                  │
│  ├─ Multi-stop:    No                                                  │
│  └─ Posted:        Dec 19, 10:30 AM (4 hours ago)                      │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  BROKER                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Acme Logistics Inc                        MC-123456 │ DOT-789012│   │
│  │ ★★★★☆ 4.2 (156 reviews)                                         │   │
│  │                                                                  │   │
│  │ Authority: Active since 2018                                    │   │
│  │ Days to Pay: 32 avg / 45 P90                                    │   │
│  │ Dispute Rate: 2%                                                │   │
│  │ Risk Score: 72/100 (Low Risk)                                   │   │
│  │                                                                  │   │
│  │ [View Full Broker Profile →]                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ACTIONS                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ 📞 Call      │  │ ⭐ Watchlist │  │ 📋 Copy      │                 │
│  │ (555)123-4567│  │ Add/Remove   │  │ Load Details │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 2. Watchlists

Watchlists enable tracking loads of interest across sessions.

#### Watchlist Panel

Accessed via `W` or sidebar:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ WATCHLISTS                                              [+ New List]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ★ Hot Loads (Default)                              5 loads      │   │
│  │   Updated 2 min ago                                              │   │
│  │   ┌────────────────────────────────────────────────────────────┐│   │
│  │   │ 92 │ ATL,GA → CHI,IL │ 12/20 │ $2.58/mi │ Still Available ││   │
│  │   │ 87 │ DAL,TX → DEN,CO │ 12/20 │ $2.72/mi │ Still Available ││   │
│  │   │ 84 │ MIA,FL → ATL,GA │ 12/21 │ $2.45/mi │ ⚠ Rate Changed  ││   │
│  │   │ 71 │ SEA,WA → PDX,OR │ 12/20 │ $2.65/mi │ ❌ No Longer Avl ││   │
│  │   │ 68 │ PHX,AZ → LAX,CA │ 12/22 │ $2.31/mi │ Still Available ││   │
│  │   └────────────────────────────────────────────────────────────┘│   │
│  │   [Compare Selected] [Remove Unavailable]                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Southeast Opportunities                            3 loads      │   │
│  │   Updated 15 min ago                                [Expand ▾]  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Backhaul Options                                   8 loads      │   │
│  │   Updated 1 hour ago                                [Expand ▾]  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Load Status Indicators

| Status | Indicator | Meaning |
|--------|-----------|---------|
| Available | ✓ Still Available | Load unchanged since added |
| Rate Changed | ⚠ Rate Changed | Rate increased/decreased |
| Pickup Changed | ⚠ Time Changed | Pickup window modified |
| Booked | ❌ No Longer Available | Load removed from board |
| Expired | ❌ Expired | Pickup window passed |

#### Watchlist Actions

| Action | Keyboard | Description |
|--------|----------|-------------|
| Add load | `s` on load row | Star to default watchlist |
| Add to specific | `Shift+S` | Choose watchlist |
| Remove load | `x` in watchlist | Remove from current list |
| Compare loads | `Space` to select, `Enter` | Side-by-side comparison |
| Refresh status | `r` | Check availability |
| Create list | `n` in watchlist panel | New watchlist |
| Delete list | `Backspace` | Delete (with confirm) |
| Rename list | `F2` | Inline rename |

#### Comparison View

Multi-select loads for side-by-side comparison:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ COMPARE LOADS (3 selected)                                    [×]     │
├─────────────────────────────────────────────────────────────────────────┤
│                 │ Load A          │ Load B          │ Load C          │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Route           │ ATL → CHI       │ DAL → DEN       │ MIA → ATL       │
│ Distance        │ 716 mi          │ 770 mi          │ 490 mi          │
│ Score           │ ████92          │ ███87           │ ███84           │
│ Rate            │ $1,850          │ $2,100          │ $1,200          │
│ RPM             │ $2.58 ✓ BEST    │ $2.72 ✓ BEST    │ $2.45           │
│ Deadhead        │ 45 mi ✓ BEST    │ 120 mi          │ 78 mi           │
│ Pickup          │ 12/20 08:00     │ 12/20 14:00     │ 12/21 06:00     │
│ Broker Rating   │ 4.2★            │ 3.8★            │ 4.5★ ✓ BEST     │
│ Days to Pay     │ 32 ✓ BEST       │ 45              │ 38              │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Actions         │ [📞 Call]       │ [📞 Call]       │ [📞 Call]       │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

---

### 3. Alerts

Proactive notifications when matching loads appear.

#### Alert Management Panel

Accessed via `A` or sidebar:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ALERTS                                                  [+ New Alert]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ACTIVE ALERTS                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🔔 Chicago Dry Van                                    [On] [⚙]  │   │
│  │    Route: Any → Chicago, IL                                      │   │
│  │    Equipment: Dry Van │ RPM ≥ $2.50                             │   │
│  │    Triggered 3 times today │ Last: 2:15 PM                      │   │
│  │    ┌──────────────────────────────────────────────────────────┐ │   │
│  │    │ New! 14:15 │ ATL→CHI │ $2.68/mi │ Score 89 │ [View →]   │ │   │
│  │    │ 11:30      │ DAL→CHI │ $2.55/mi │ Score 82 │ [View →]   │ │   │
│  │    │ 09:45      │ MIA→CHI │ $2.61/mi │ Score 85 │ [View →]   │ │   │
│  │    └──────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🔔 High-Paying Reefer                                 [On] [⚙]  │   │
│  │    Equipment: Reefer │ RPM ≥ $3.00                              │   │
│  │    Triggered 1 time today │ Last: 10:30 AM                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🔕 Southeast Flatbed                               [Off] [⚙]    │   │
│  │    Origin: GA, FL, SC, NC │ Equipment: Flatbed                  │   │
│  │    Paused until Dec 26                                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Alert Creation Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CREATE ALERT                                                    [×]    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Name: [Chicago Dry Van                              ]                 │
│                                                                         │
│  FILTER CRITERIA (matches will trigger alert)                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Origin:      [Any                          ▾]                    │   │
│  │ Destination: [Chicago, IL                  ▾]                    │   │
│  │ Equipment:   [☑ Dry Van] [☐ Reefer] [☐ Flatbed] [☐ Power Only]  │   │
│  │ RPM Min:     [$2.50                        ]                     │   │
│  │ Deadhead Max:[150 miles                    ]                     │   │
│  │ Broker Min:  [3.5★                         ]                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  THRESHOLD (optional - trigger only when condition met)                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Alert Type:  [◉ Any Match] [○ Score ≥] [○ RPM ≥] [○ Count ≥]   │   │
│  │ Value:       [                         ]                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  NOTIFICATION CHANNELS                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ [☑ In-App]  [☑ Email]  [☐ SMS]  [☐ Push]                       │   │
│  │                                                                  │   │
│  │ Frequency: [◉ Instant] [○ Hourly Digest] [○ Daily Digest]      │   │
│  │ Quiet Hours: [☐ Enable] 10:00 PM - 6:00 AM                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [Cancel]                                        [Create Alert]        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Alert Types

| Type | Trigger Condition |
|------|-------------------|
| Lane Alert | Load matches origin/destination criteria |
| Price Alert | RPM or total rate exceeds threshold |
| Score Alert | GreenLight score exceeds threshold |
| Broker Alert | Specific broker posts a load |
| Capacity Alert | Market volume drops (opportunity signal) |

#### Notification Channels

| Channel | Description |
|---------|-------------|
| In-App | Banner + badge in FreightLens UI |
| Email | Immediate or digest email |
| SMS | Text message (premium) |
| Push | Browser/mobile push notification |

---

### 4. Portfolio (Fleet Management)

For users managing multiple trucks.

#### Truck Overview

Accessed via `P` or sidebar:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PORTFOLIO                                               [+ Add Truck]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  FLEET STATUS                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 3 Trucks │ 2 Active │ 1 Available │ $4,950 booked today         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🚛 Truck #1 (Dry Van)                                           │   │
│  │    Driver: John Smith                                           │   │
│  │    Status: 🟢 Available                                         │   │
│  │    Location: Nashville, TN                                      │   │
│  │    Available: Now                                               │   │
│  │    ┌──────────────────────────────────────────────────────────┐│   │
│  │    │ TOP RECOMMENDATIONS                                      ││   │
│  │    │ 92 │ NSH→CHI │ 120mi DH │ $2.58/mi │ [View] [Book]      ││   │
│  │    │ 88 │ NSH→ATL │  45mi DH │ $2.45/mi │ [View] [Book]      ││   │
│  │    │ 85 │ NSH→STL │  80mi DH │ $2.52/mi │ [View] [Book]      ││   │
│  │    └──────────────────────────────────────────────────────────┘│   │
│  │    [See All Recommendations →]                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🚛 Truck #2 (Reefer)                                            │   │
│  │    Driver: Jane Doe                                             │   │
│  │    Status: 🟡 En Route                                          │   │
│  │    Current: Atlanta, GA → Miami, FL                             │   │
│  │    ETA: Dec 20, 14:00 │ Available: Dec 20, 16:00               │   │
│  │    Next Load: Searching...                                      │   │
│  │    [Find Backhaul from Miami →]                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🚛 Truck #3 (Flatbed)                                           │   │
│  │    Driver: Bob Johnson                                          │   │
│  │    Status: 🔴 Off Duty                                          │   │
│  │    Location: Denver, CO                                         │   │
│  │    Available: Dec 22, 08:00                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Truck Detail & Recommendations

```
┌─────────────────────────────────────────────────────────────────────────┐
│ TRUCK #1 - DRY VAN                                            [⚙] [×] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  CURRENT STATUS                                                        │
│  ├─ Location:     Nashville, TN (updated 15 min ago)                   │
│  ├─ Available:    Now                                                  │
│  ├─ Driver:       John Smith                                           │
│  ├─ Equipment:    Dry Van, 53'                                         │
│  ├─ Max Weight:   45,000 lbs                                           │
│  └─ Hazmat:       Not Endorsed                                         │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PERSONALIZED RECOMMENDATIONS                                          │
│  Based on: location, equipment, preferences, lane history             │
│                                                                         │
│  ┌───┬──────┬──────────────────┬─────┬────────┬───────┬───────────────┐│
│  │   │SCORE │ ROUTE            │ DH  │ RATE   │ RPM   │ WHY           ││
│  ├───┼──────┼──────────────────┼─────┼────────┼───────┼───────────────┤│
│  │ 1 │ ██92 │ NSH,TN → CHI,IL  │ 0mi │ $1,450 │ $2.58 │ Perfect match ││
│  │ 2 │ ██88 │ NSH,TN → ATL,GA  │ 0mi │ $620   │ $2.45 │ Familiar lane ││
│  │ 3 │ █░85 │ NSH,TN → STL,MO  │ 0mi │ $780   │ $2.52 │ Good backhaul ││
│  │ 4 │ █░82 │ MEM,TN → DAL,TX  │52mi │ $1,100 │ $2.38 │ High demand   ││
│  │ 5 │ █░79 │ NSH,TN → CLE,OH  │ 0mi │ $1,200 │ $2.28 │ Broker 4.5★   ││
│  └───┴──────┴──────────────────┴─────┴────────┴───────┴───────────────┘│
│                                                                         │
│  [Load More]  [Apply Custom Filters]                                   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  RECENT HISTORY (Last 30 days)                                         │
│  ├─ Loads Completed: 12                                                │
│  ├─ Total Miles: 8,450                                                 │
│  ├─ Total Revenue: $19,800                                             │
│  ├─ Avg RPM: $2.34                                                     │
│  └─ Deadhead %: 8.5%                                                   │
│                                                                         │
│  [View Full History →]                                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Fleet Map View

Optional map overlay showing truck positions:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ FLEET MAP                                            [List] [Map ●]    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                    ┌───────────────────────────────────────────┐       │
│                    │                                           │       │
│                    │          🚛₁                              │       │
│                    │         Nashville                         │       │
│                    │                                           │       │
│                    │                    🚛₂ ──────▸            │       │
│                    │                   Atlanta    Miami        │       │
│                    │                                           │       │
│                    │   🚛₃                                     │       │
│                    │  Denver                                   │       │
│                    │                                           │       │
│                    └───────────────────────────────────────────┘       │
│                                                                         │
│  Legend: 🟢 Available  🟡 En Route  🔴 Off Duty                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Keyboard Shortcuts

### Global

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `Esc` | Close panel / Clear focus |
| `?` or `F1` | Show help |
| `W` | Open Watchlists |
| `A` | Open Alerts |
| `P` | Open Portfolio |
| `G` then `L` | Go to Loads |
| `G` then `B` | Go to Brokers |
| `G` then `S` | Go to Settings |

### Load List

| Key | Action |
|-----|--------|
| `↑` / `k` | Previous row |
| `↓` / `j` | Next row |
| `Enter` | Open detail |
| `Space` | Toggle selection |
| `s` | Star (add to watchlist) |
| `c` | Copy load ID |
| `Shift+C` | Copy broker phone |
| `r` | Refresh list |

### Filters

| Key | Action |
|-----|--------|
| `e` | Equipment filter |
| `o` | Origin filter |
| `d` | Destination filter |
| `m` | RPM filter |
| `h` | Deadhead filter |
| `Ctrl+Enter` | Apply filters |
| `Ctrl+Backspace` | Clear all filters |
| `Ctrl+S` | Save current filter |

### Detail Panel

| Key | Action |
|-----|--------|
| `Esc` | Close panel |
| `Tab` | Next section |
| `Shift+Tab` | Previous section |
| `s` | Toggle watchlist |
| `b` | View broker profile |

---

## Command Palette

Power users can access any action via command palette (`Ctrl+K` or `Cmd+K`):

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 🔍 Type a command...                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  RECENT                                                                │
│  > Filter: Dry Van only                                                │
│  > Go to Watchlists                                                    │
│  > Create Alert...                                                     │
│                                                                         │
│  COMMANDS                                                              │
│  > Filter: Set equipment...                     e                      │
│  > Filter: Set origin...                        o                      │
│  > Filter: Set destination...                   d                      │
│  > Filter: Clear all                            Ctrl+Backspace         │
│  > Filter: Save current...                      Ctrl+S                 │
│  > Watchlist: Add current load                  s                      │
│  > Watchlist: Open panel                        W                      │
│  > Alert: Create new...                                                │
│  > Alert: Open panel                            A                      │
│  > Portfolio: Open                              P                      │
│  > Settings: Open                               Ctrl+,                 │
│  > Theme: Toggle dark/light                                            │
│  > Data: Refresh                                r                      │
│  > Data: Import file...                                                │
│  > Help: Show shortcuts                         ?                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Accessibility

### WCAG 2.1 AA Compliance

| Requirement | Implementation |
|-------------|----------------|
| Color Contrast | 4.5:1 minimum for text, 3:1 for UI components |
| Keyboard Navigation | Full keyboard access, visible focus indicators |
| Screen Reader | ARIA labels, landmarks, live regions for updates |
| Motion | Respects `prefers-reduced-motion` |
| Text Scaling | Supports 200% zoom without horizontal scroll |

### Focus Management

- Clear focus ring (2px blue outline)
- Focus trapped in modals
- Focus restored on modal close
- Skip links for main content

### Screen Reader Announcements

| Event | Announcement |
|-------|--------------|
| Filter applied | "Filtered to 150 loads" |
| Load selected | "Load from Atlanta to Chicago, score 92" |
| Alert triggered | "New alert: Chicago Dry Van, 3 matching loads" |
| Data refreshed | "Data refreshed, 247 loads loaded" |

---

## Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to Interactive | <2s | Lighthouse |
| First Contentful Paint | <1s | Lighthouse |
| Filter response | <100ms | User perception |
| List scroll | 60fps | DevTools |
| Detail panel open | <150ms | User perception |
| Search autocomplete | <50ms | User perception |

### Optimization Strategies

- **Virtual scrolling** for load list (render only visible rows)
- **Debounced filtering** (50ms delay on input)
- **Optimistic UI updates** (reflect changes before server confirms)
- **Service worker caching** for static assets
- **WebSocket** for real-time updates (Phase 5)

---

## Future Enhancements

### Phase 5: Real-Time Features

- Live load updates via WebSocket
- Collaborative watchlists (team sharing)
- Live market ticker with customizable symbols
- Push notifications with deep links

### Phase 6: Analytics Dashboard

- Revenue charts and trends
- Lane performance heatmaps
- Broker payment history graphs
- Market comparison tools

### Phase 7: Mobile App

- Native iOS/Android apps
- Offline load viewing
- Location-based recommendations
- Voice commands for hands-free operation

---

## Trust & Confidence Display

Inline trust indicators throughout the UI. See [TRUST_UI_SPEC.md](TRUST_UI_SPEC.md) for complete specification.

### Summary of Trust Primitives

| Element | List View | Detail Panel | Exports |
|---------|-----------|--------------|---------|
| Confidence bucket | Colored dot (🟢🟡🔴) | Score + bucket + breakdown | Included as column |
| Freshness | Age badge if stale/expired | Timestamp + bucket | Included as column |
| Provenance | — | Source badge + name | Included as column |
| Rights state | Restricted icon if applicable | Full rights display | Restricted fields excluded |

### Interaction Summary

- **Hover confidence indicator:** Shows "Why this confidence" tooltip (500ms delay)
- **Click score factor:** Opens contribution detail popover
- **Restricted export:** Button disabled with explanatory tooltip

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `c` | Toggle confidence column visibility |
| `?` | Open "Why this score" for focused load |

### Acceptance Criteria Reference

See [TRUST_UI_SPEC.md#g-acceptance-criteria](TRUST_UI_SPEC.md#g-acceptance-criteria) for 30 testable acceptance criteria covering list view, detail panel, API contract, accessibility, and performance.
