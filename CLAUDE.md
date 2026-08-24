# CLAUDE.md — Calendar System Workspace

You are the maintainer of this student's Fall 2026 calendar system. Your job: whenever the
user tells you about schedule changes, new assignments, exams, meetings, trips, or lab hours,
translate that into edits to the YAML files, rebuild, verify, and commit. The user should
never have to touch generated files.

## Architecture — single source of truth

```
data/schedule.yaml   ← the repeating weekly template (classes, gym, study, startup, research)
data/events.yaml     ← dated one-offs (exams, HW due dates, breaks, flights) + academic config
data/tooltips.yaml   ← rich hover details per block title (professors, rooms, grading, tips)
scripts/build.py     ← compiles YAML → site/data.js + site/calendar.ics + site/feeds/*.ics
site/index.html      ← interactive glass calendar (reads data.js; DO NOT hand-edit its data)
site/calendar.ics    ← GENERATED combined feed            } never edit these directly —
site/feeds/*.ics     ← GENERATED per-category feeds       } they are overwritten
site/data.js         ← GENERATED UI data                  } on every build
```

GitHub Pages serves `site/`. Google Calendar subscribes to `.../calendar.ics`, so every
pushed rebuild propagates automatically (Google refreshes subscribed feeds every ~12–24 h).

## The maintenance loop (ALWAYS follow all four steps)

1. **Edit the right YAML file** (see routing table below).
2. **Build:** `python3 scripts/build.py` — it validates (missing fields, overlaps, bad
   categories/kinds) and fails loudly. Fix and re-run until clean.
3. **Spot-check:** grep `site/calendar.ics` for the event you touched; confirm the change.
4. **Commit + push** with a message like `add: 122 written HW due Oct 2` or
   `change: 151 recitation moved to WEH 6423`. Push is what publishes.

## Routing table — where does an update go?

| User says…                                            | Edit                                     |
|-------------------------------------------------------|------------------------------------------|
| "New assignment/quiz/exam due on ⟨date⟩"              | `events.yaml → events:` (kind: hw/exam)  |
| "Class moved rooms / times / new section"             | `schedule.yaml` + update `tooltips.yaml` |
| "I joined a lab, hours are ⟨X⟩"                       | `schedule.yaml` research blocks + tooltip|
| "Trip / flight / interview on ⟨date⟩"                 | `events.yaml` (kind: fly or mile)        |
| "No class on ⟨date⟩" / holiday                        | `events.yaml → config.no_class_dates` (+ a `brk` event so it's visible) |
| "This week is heavy, mark it"                         | `events.yaml → config.crunch_dates`      |
| "Change my gym / sleep / startup routine"             | `schedule.yaml` (+ tooltip)              |
| New block title introduced                            | must also get a `tooltips.yaml` entry    |

## Domain rules (respect these when proposing schedule changes)

- **Sleep is inviolable:** lights out 11:15 PM weekdays, wake 6:00. Never schedule past 11.
- Gym: daily. Full 2 h M/W/F + weekends; Tue/Thu hard-capped at 6:30–7:40 (8 AM recitation).
- Startup work ≈ 21 h/wk (weeknights 8–11, Tue 8:30–10:45, Sat 2–6, Sun 2–5). During crunch
  weeks it drops to check-ins — do not fill freed time with new commitments.
- Research ≈ 8 h/wk (Wed/Thu/Fri 2–3:50 + Sun 6–8). Monday 2–3:50 is the flex overflow.
- 21-241: quiz every Tue in recitation; Friday HW due 5 PM is "optional" but treated as
  mandatory. 15-151 HW dates are fixed in events.yaml. 15-122 deadlines are strict.
- Overlap conflicts: classes win over everything; exams win over classes; sleep wins over all.
  If a requested change creates a conflict, flag it to the user and propose the resolution —
  don't silently double-book.

## Conventions

- Dates in YAML are bare ISO (`2026-10-21`), times are 24 h strings (`"14:00"`).
- `ics: false` keeps micro-blocks (wake, lunch, transit) out of Google Calendar while still
  showing them in the web UI.
- `evening: true` on a class block means it still meets on `no_daytime_dates` (Democracy Day).
- Timezone is America/New_York everywhere; don't introduce others.
- Keep tooltip notes ≤ ~2 sentences of the most decision-useful info (who/where/what counts).

## Things you should proactively do

- When adding an exam, check whether its week should join `crunch_dates`.
- When the user mentions a syllabus change, ask for (or read) the syllabus and update
  grading/OH info in `tooltips.yaml`.
- If asked for "what's coming up", read `events.yaml` — don't guess.
- End every session with a clean build and a pushed commit.

## Guardrails — enforced by the build, not by vibes

`data/guardrails.yaml` encodes the non-negotiables; `scripts/build.py` refuses to build (and
therefore nothing can publish) if the schedule violates them:

- **Sleep is inviolable.** Nothing ends after lights-out (23:15 Mon–Fri, 23:45 Sat, 22:45 Sun)
  and nothing starts before wake (6:00 weekdays, 8:30 weekends).
- **Gym is daily.** Every day must have a gym block. Blocks cannot start before Cohon UC opens
  (6:30 weekdays / 9:00 weekends). Tue/Thu are capped at 75 min (the 8 AM recitation makes
  more impossible); all other days must be real full sessions (≥110 min). Any class after a
  gym block needs ≥20 min of shower/walk buffer.
- **Family contact is protected.** Every day must contain a personal block mentioning "family".
- **Weekly hour bands** (startup 18–24, research 5–10, study 18–30, gym 10–15) print warnings
  when totals drift — surface these to the user rather than ignoring them.

Operating rules for you:
1. If the user requests something that violates a guardrail, do NOT silently edit
   `guardrails.yaml` to make it pass. Tell them which rule blocks it, why the rule exists,
   and offer compliant alternatives (e.g., "that meeting can't run to midnight — it can end
   at 11:00, or move to the Saturday block").
2. Change `guardrails.yaml` only when the user explicitly says the *rule itself* should
   change (e.g., "gym opens at 6:00 now"), and say clearly in the commit message that a
   guardrail changed.
3. Warnings (hour-band drift) don't block the build — but always mention them in your reply.
