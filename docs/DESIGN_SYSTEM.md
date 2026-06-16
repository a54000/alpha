# NSE Research Platform — Design System

## Visual Identity

**Concept:** Personal quant terminal. Not a consumer app. Not a fintech startup.
The aesthetic is an oscilloscope meets a trading desk — precision instruments
for serious decisions made under time pressure (7:45 AM, before open).

---

## Color Tokens

```css
--color-canvas:      #0A0E1A  /* deep navy-black, main background */
--color-surface:     #111827  /* sidebar, top bar */
--color-card:        #1E293B  /* stock cards, panels */
--color-card-hover:  #263347  /* card hover state */
--color-border:      #1E293B  /* dividers */
--color-border-dim:  #162032  /* subtle dividers */

/* Signal colors */
--color-bull:        #10B981  /* emerald — bullish, positive */
--color-bear:        #EF4444  /* rose — bearish, stop loss */
--color-amber:       #F59E0B  /* amber — scores, primary accent */
--color-amber-dim:   #92400E  /* muted amber for backgrounds */
--color-neutral:     #6366F1  /* indigo — neutral/positional */

/* Text */
--color-text-primary:   #F1F5F9  /* near white */
--color-text-secondary: #94A3B8  /* slate — labels, metadata */
--color-text-muted:     #475569  /* dimmed — tertiary info */
```

---

## Typography

```
Display / Numbers:  JetBrains Mono — scores, prices, percentages
Body / Labels:      Inter — prose, labels, explanations
```

**Scale:**
```
Score number:    48px / Mono / 700
Stock symbol:    20px / Mono / 600
Price:           16px / Mono / 500
Label:           11px / Inter / 500 / uppercase / tracking-wider
Body:            14px / Inter / 400
Explanation:     13px / Inter / 400 / line-height 1.6
```

---

## Signature Element — Signal Heat Bar

Each stock card has a horizontal segmented bar divided into 5 signal categories.
Each segment fills proportionally to that category's contribution.
Color shifts from muted slate → amber → emerald as score increases.

```
[MOMENTUM ████░░] [VOLUME ██░░░░] [BREAKOUT ████░░] [RS ███░░░] [FUND ██░░░░]
```

This is an oscilloscope readout, not a generic progress bar.

---

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  MACRO STRIP — Nifty +0.4%  │  Defence ↑↑  │  IT ↓  │  8 signals fired today │
├──────────────┬──────────────────────────────────────────────────┤
│              │  [SWING]  [POSITIONAL]  [LONG-TERM]              │
│  SECTOR      ├──────────────────────────────────────────────────┤
│  ROTATION    │  ┌──────────────┐  ┌──────────────┐             │
│  SIDEBAR     │  │  STOCK CARD  │  │  STOCK CARD  │  ...        │
│              │  └──────────────┘  └──────────────┘             │
│  Defence ↑↑  │                                                  │
│  PSU Bank ↑  │  [Selected card expands to show full detail]     │
│  IT ↓        │                                                  │
│              │                                                  │
└──────────────┴──────────────────────────────────────────────────┘
```

---

## Component Library

### Stock Card (collapsed)
- Symbol + company name
- Score badge (amber, large mono)
- Signal heat bar
- 3 top signal tags
- Entry / SL / Target in one line

### Stock Card (expanded)
- Full signal breakdown
- LLM explanation
- Fundamentals mini-table
- Event intel badge
- R:R visualization

### Sector Rotation Widget
- Vertical list, sector name + sparkline bar
- Color coded: green (hot), red (cold)
- Last updated timestamp

### Score Badge
- Large number in JetBrains Mono
- Ring/arc fill around it
- Color: <50 slate, 50-70 amber, >70 emerald

---

## Motion

- Card expand: 200ms ease-out height transition
- Score badge: count-up animation on load (300ms)
- Heat bar: left-to-right fill on card mount (400ms, staggered per segment)
- Macro strip: no animation (it's data, not decoration)
- Tab switch: instant (no cross-fade — feels faster)
