# Handoff: Vaultly V1 — Web App Screens ("Ledger" design system)

## Overview
Complete V1 screen set for Vaultly, a secure family document vault (receipts, warranties, insurance, medical bills, emergency access). Screens `2a`–`2k` in `Vaultly Screens.dc.html` are FINAL and approved. Section 1 (1a/1b/1c) contains earlier dashboard explorations — **1a "Ledger" is the chosen direction**; the approved dashboard IS 1a. Ignore 1b and 1c.

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes showing intended look and behavior, not production code to copy directly. Your task is to **recreate these designs in the target codebase's environment** (the planned stack is Next.js 14 App Router + Tailwind + TypeScript) using its established patterns. If no codebase exists yet, scaffold Next.js + Tailwind and implement there. Open `Vaultly Screens.dc.html` in a browser to view all screens on one pannable canvas (each screen is anchored: #1a, #2a … #2k).

## Fidelity
**High-fidelity.** Colors, typography, spacing, radii, and copy are final — recreate pixel-perfectly. Icons are geometric placeholders in the mocks; replace with **Lucide icons, 1.5px stroke**. All data shown is illustrative sample data — wire to real APIs.

## Screens / Views
| Anchor | Screen | Purpose |
|---|---|---|
| 1a | Dashboard (approved) | Greeting, ⌘K ask bar, 4 KPI stat cards, upcoming-deadlines list w/ date chips, category grid, recent imports, emergency-binder card |
| 2a | Sign in | 44% navy brand panel (trust bullets) + centered 380px auth card: email, password, Continue, Google OAuth, 2FA note. Sign-up reuses layout + name field + password rules |
| 2b | Upload + OCR | Dashed dropzone, processing queue (states: Extracted / OCR % progress / Queued), extracted-field chips, "warranty detected → create warranty + reminder" suggestion banner, right rail: Gmail sync toggle, email-in address, phone scan |
| 2c | Search / AI answer | Focused query bar w/ latency, navy "VAULTLY ANSWER" card w/ action buttons + source count, filter chips, ranked results with highlighted snippet (`<mark>`-style bg #FDF4DD) + relevance score |
| 2d | Document detail | Breadcrumb, title + type tag + Download/Share/Delete, left: document preview, right stack: extracted fields (2-col grid), linked records, visibility, activity/audit log |
| 2e | Reminders center | Two urgency groups ("Needs attention · next 30 days" / "Later"), rows: checkbox, title, source-doc link, channel, mono date, urgency pill; right rail: Email/Push toggles, lead-time chips 30d/7d/1d, 99.4% delivery stat |
| 2f | Insurance center | Summary line, 2-col policy cards (provider, policy #, status tag, coverage rows, premium mono + renewal, doc count), dashed "add policy" slot |
| 2g | Medical bills | 3 summary stats (Outstanding / Claims pending / Paid YTD), table: Provider·Date·Amount·Insurance status tag·Due·Action, email-in tip |
| 2h | Emergency binder | 3 cols: contents checklist (✓ done green / ＋ missing orange), navy QR card (print / revoke, PIN + audit notes), delegates list + empty-state access log (dashed card) |
| 2i | Family | Members list w/ role dropdowns (Owner/Admin/Member/Emergency only) + pending invite row, category-access matrix (● full ◯ view · none) |
| 2j | Mobile dashboard | 390px: top bar, ask bar, deadlines card, 2-col category grid, bottom tab bar w/ raised navy Add FAB (44px targets) |
| 2k | Handoff sheet | On-canvas spec: all tokens, type scale, geometry, components, states — mirror of this README |

Shared shell (desktop screens 2b–2i): 232px white sidebar (`LedgerSidebar.dc.html`) — logo, 7 nav items (active: bg #EAF0F6, navy text/dot; Reminders badge count), storage meter pinned bottom. Content area bg #F4F5F7, padding 24px 32px.

## Design Tokens
Colors:
- ink/primary `#16324F` — primary buttons, active nav, answer card, QR card bg
- text `#1C2733` · text-sub `#6B7683` · text-faint `#8D97A3`
- border `#E2E6EA` (cards, inputs) · hairline `#EEF1F4` (row dividers) · app bg `#F4F5F7` · card `#FFFFFF`
- link/info `#2A6FDB`
- urgent `#C2410C` on `#FFF1E7` (<14 days, errors) · warn `#946200` on `#FDF4DD` (14–30 days) · ok `#3D6B5E` on `#E9F2EE`
- active-nav bg `#EAF0F6` · input border `#DFE4E9`

Typography — IBM Plex Sans (UI), IBM Plex Mono (ALL numbers, dates, amounts, codes, policy #s):
- Page title 21/600 · card title 14/600 · body 13.5/400 · secondary 12/400 · meta 11.5 · KPI numbers 26/600 Mono · table headers 10/600 Mono uppercase tracking .1em

Geometry:
- Spacing 4px base: 8/12/16/20/24/32
- Radius: 5px tags · 7–9px buttons/inputs/date-chips · 10–12px cards
- Shadows rare: max `0 1px 3px rgba(22,50,79,.06)`

Components:
- Primary button: navy bg, white 13/600, radius 8–9, padding 11px 18px
- Secondary: white bg, 1px #DFE4E9 border, navy text
- Tags/pills: 11.5/600, padding 3px 9px, radius 5 (urgency colorways above)
- Date chip: 44px wide, urgency bg, mono day + 9.5px month
- Input: 1px #DFE4E9, radius 8, padding 11px 14px; focus 1.5px #16324F
- Toggle: 34×20 pill, navy when on
- Avatar: circle, bg #DBE3EA, navy initials 11–12/600

## Interactions & Behavior
- ⌘K opens ask/search overlay from anywhere; any item ≤3 clicks from dashboard
- Hover rows: bg #F8FAFC · Loading: skeleton blocks #EEF1F4 w/ 1.2s pulse
- Empty states: 1px dashed border card + one-line explainer (see 2h access log)
- Upload: drag-drop + browse; queue rows show progress bar in state color; OCR completion reveals field chips + suggestion banner (Create both / Dismiss)
- Search answer card actions create reminders / open docs; results filterable by category/date/owner chips
- Reminders checkbox completes; lead-time chips editable
- Emergency QR: print, revoke & reissue; every scan notifies owner + writes audit log
- Family roles via dropdown; permission matrix cells cycle full → view → none
- Mobile: bottom tabs, center FAB = Add, min 44px hit targets
- Responsive: sidebar collapses to bottom tabs <768px (2j shows the mobile pattern)

## State Management (implementation hints)
- Auth session + 2FA step state · upload queue (per-file OCR status/progress) · search query/filters/answer · reminder toggles & lead times · role/permission matrix · binder completeness + delegate list
- Sample data lives in the DC logic class at the bottom of `Vaultly Screens.dc.html` (deadlines, cats, policies, bills, members, etc.) — use as API response shapes

## Assets
No image assets. Fonts via Google Fonts: IBM Plex Sans (400–700), IBM Plex Mono (400–600). QR in 2h is a placeholder grid — generate real QR codes at runtime. Google logo in 2a is a placeholder — use official asset.

## Files
- `Vaultly Screens.dc.html` — all screens (section id=t2 → screens 2a–2k final; section t1 → 1a approved dashboard)
- `LedgerSidebar.dc.html` — shared sidebar component (prop: `active`)
- `support.js` — runtime that renders the .dc.html files in a browser (reference only; do not port)
