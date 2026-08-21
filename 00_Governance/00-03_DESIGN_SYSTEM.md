# WFM OS design system

## Design intent

WFM OS should feel like a premium operational instrument: calm, precise,
authoritative, and fast to scan. It is not a decorated spreadsheet.

The visual language is called **Obsidian & Pearl**:

- Obsidian provides authority for navigation and titles.
- Pearl provides a quiet analytical canvas.
- Deep teal signals interaction and ownership.
- Copper is a restrained secondary accent for planning and scenarios.
- Semantic colors are reserved for operational meaning.

## Design principles

1. Decision first: every page must answer a named operational question.
2. Hierarchy before decoration: spacing and typography carry the layout.
3. Quiet by default: color appears only for interaction, grouping, or meaning.
4. Dense but breathable: expose detail without turning the page into a grid.
5. Exceptions earn attention: red is rare and always actionable.
6. Consistent components: the same object means the same thing everywhere.
7. Business-facing: no implementation notes or AI instructions in the workbook.

## Color tokens

| Token | Hex | Use |
|---|---|---|
| `ink-900` | `111827` | primary text and figures |
| `ink-700` | `334155` | secondary labels |
| `ink-500` | `64748B` | metadata and subtitles |
| `shell-950` | `081824` | application header/navigation |
| `shell-900` | `0B2233` | header variation and dark cards |
| `pearl-050` | `F6F7F9` | workbook canvas |
| `paper-000` | `FFFFFF` | cards and report surfaces |
| `line-200` | `D8DEE7` | structural rules |
| `line-100` | `E9EDF2` | subtle separators |
| `primary-700` | `0B6670` | selected state and primary action |
| `primary-500` | `168A96` | chart series and active accents |
| `primary-100` | `DCEFF1` | controlled input fill |
| `copper-600` | `A4663F` | planning/scenario accent |
| `copper-100` | `F2E6DD` | scenario surface |
| `success-600` | `18794E` | confirmed healthy state |
| `success-100` | `DDF3E8` | healthy-state surface |
| `warning-600` | `B7791F` | attention/nonblocking issue |
| `warning-100` | `FFF1D6` | warning surface |
| `danger-600` | `B83A4B` | blocking/actionable exception |
| `danger-100` | `FBE4E8` | blocking-error surface |
| `info-600` | `315E9B` | neutral information |
| `info-100` | `E2EBF7` | informational surface |

Do not introduce an undocumented color. Opacity is simulated by using the
provided light surface tokens, not transparency or gradients.

## Typography

Use Aptos throughout for compatibility with current Microsoft 365 Excel.

| Role | Size | Weight | Color |
|---|---:|---|---|
| Application title | 24 pt | Semibold | white on shell |
| Page title | 18 pt | Semibold | `ink-900` |
| Section title | 11 pt | Semibold, uppercase | `ink-700` |
| KPI value | 24 pt | Semibold | `ink-900` |
| KPI label | 9 pt | Semibold, uppercase | `ink-500` |
| Body | 10 pt | Regular | `ink-700` |
| Table header | 9 pt | Semibold | `ink-700` |
| Metadata | 8.5 pt | Regular | `ink-500` |

Use tabular number alignment. Avoid italic text except for a short explanatory
empty state. Never use more than three font sizes in one component.

## Layout system

- Default canvas: `pearl-050`; gridlines hidden.
- Standard content span: columns `B:Q`.
- Column `A` and column `R` are quiet margins.
- Use a 4-point spacing rhythm expressed through row heights: 8, 12, 16, 20,
  24, 32, and 40 points.
- Freeze the application header and filters, not arbitrary table rows.
- Do not merge cells in tables, inputs, or technical regions.
- A business page uses at most three horizontal levels: summary, analysis, and
  action/detail.

### Standard page shell

```text
Row 1       quiet top margin
Rows 2-3    dark application header: product, page, navigation, status
Row 4       page title and one-line decision statement
Row 5       refresh timestamp, profile, period, and owner
Row 6       whitespace
Rows 7-9    filter/control rail
Rows 11-15  KPI cards
Rows 17-31  primary analysis
Rows 33+    exception/action table or supporting analysis
```

## Core components

### Application header

Use `shell-950` with a thin `primary-500` bottom rule. Show product name,
current module, compact navigation links, refresh state, and Data Quality state.
Avoid large logos or decorative banners.

### KPI card

A KPI card contains:

- short uppercase label;
- primary value with unit;
- comparison versus target or prior period;
- small status label;
- optional 8-12 point sparkline.

Cards use white surfaces, no heavy outline, and a 2-point semantic left rule.
Red is used only when the user can take a defined action.

### Control rail

Slicers, period controls, enterprise profile, activity, channel, and scenario
appear in one consistent horizontal rail. Selected controls use `primary-100`
and `primary-700`; inactive controls remain neutral.

### Data table

- White body with a subtle bottom rule; avoid boxed cells.
- Header uses `pearl-050`, semibold text, and a strong bottom rule.
- Zebra striping is optional and must be extremely subtle.
- Freeze identifiers; right-align measures; left-align labels.
- Use `—` for unavailable values and blank for structurally inapplicable values.
- Totals use a top rule and semibold type, not a dark filled row.

### Input table

Editable cells use `primary-100` with a restrained `primary-500` left rule.
Calculated and query cells remain white or `pearl-050`. A legend appears once on
each input page. Data validation messages use business language.

### Exception table

Lead with severity, decision deadline, owner, and stable case key. Use semantic
surface fills only in the severity cell, not across the whole row. Resolved rows
become neutral rather than green bands.

### Constraint funnel

Use a four-stage horizontal funnel for a decision that narrows one governed
population through scope, eligibility, hard constraints, and approval. Each
stage is a white card with a numbered label, two-line definition, explicit
empty/status label, and one module/semantic left rule. Do not use arrows,
gradients, or imply that a later stage passed merely because an earlier stage
contains rows. The named-roster control page is the reference implementation.

### Version-lineage spine

Use a five-stage horizontal spine when one publication depends on three or more
immutable versioned controls. Each stage names the version role and its state;
the final stage is always authority or release. A warning band below the spine
states the complete release gate. The roster-publication page is the reference
implementation. Never replace exact version keys with a decorative process
diagram.

### Empty, loading, and error states

- Empty: explain what source or selection is missing and the next action.
- Loading/stale: show the last successful refresh and affected sources.
- Warning: show impact and owner; allow continued use.
- Blocking: identify which decision or metric must not be used.

## Charts

- No 3D, gradients, shadows, doughnuts with many categories, speedometers, or
  decorative chart chrome.
- Use direct labels when practical; remove redundant legends.
- Actual is `primary-500`; forecast is `copper-600`; target is a thin
  `ink-500` line; prior period is `line-200` or `ink-500`.
- Semantic red/amber/green is not a general chart palette.
- Start quantitative axes at zero unless deviation analysis clearly requires a
  focused scale, in which case label that choice.
- Prefer lines for time, bars for comparisons, heatmaps for interval coverage,
  and small multiples for several activities.
- Every chart title states the measure and period, not merely a topic.

## Number formats

| Type | Format principle |
|---|---|
| Headcount/FTE | `0.0` unless physical heads require integers |
| Volume | `#,##0` |
| Percent | `0.0%` |
| Seconds | `0` with unit in label |
| Hours | `0.0` with unit in label |
| Currency | explicit currency code; no ambiguous symbol-only display |
| Variance | `+0.0%;-0.0%;—` or unit-equivalent |
| Date | locale-aware display; canonical data remains date typed |
| Date/time | include time zone on operational pages |

## Module signatures

The product remains visually unified, but modules receive one restrained accent:

| Module | Accent |
|---|---|
| Governance and quality | `info-600` |
| Forecast and capacity | `copper-600` |
| Scheduling and leave | `primary-700` |
| Intraday and attendance | `primary-500` |
| Performance and executive | `shell-900` |
| Blocking controls | semantic colors only |

## Navigation and sheet tabs

- Business sheets appear first and follow the WFM cycle.
- Configuration follows business pages.
- Python and technical sheets appear last and may be hidden normally.
- Tab colors follow module signatures; technical tabs are neutral gray.
- Every business page has Home, Previous, and Next navigation.

## Accessibility and usability

- Never communicate status by color alone; add a label or symbol.
- Maintain strong text/background contrast.
- Avoid tiny text and rotated headers.
- Provide keyboard-reachable input regions with predictable tab order.
- Protect formulas and query surfaces while leaving configured inputs unlocked.
- Default to 100% zoom and verify the standard laptop viewport.

## Versioning

The design system is version `1.1.0`. Workbook `BUILD_INFO` records the
design-system version. Any new token or component changes that version and this
document before workbook implementation.
