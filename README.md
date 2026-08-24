# Fall 2026 Calendar System

A self-maintaining semester calendar: edit simple YAML, and a build step generates both an
interactive glassmorphic web calendar and a subscribable `.ics` feed that keeps Google
Calendar in sync automatically.

**Live site:** `https://syoncodes.github.io/calendar-system/`
**Calendar feeds:** one per category under `https://syoncodes.github.io/calendar-system/feeds/`
(so each gets its own color in Google), plus `.../calendar.ics` with everything combined.

## How it works

```
data/*.yaml  ──►  scripts/build.py  ──►  site/{index.html, data.js, calendar.ics}
                                              │
                            push to GitHub ──►│──► GitHub Pages (site + feed URL)
                                              └──► Google Calendar (subscribed, auto-refresh)
```

- `data/schedule.yaml` — the repeating weekly template
- `data/events.yaml` — exams, homework due dates, breaks, flights, deadlines + academic config
- `data/tooltips.yaml` — professor/room/grading details shown on hover
- `site/` — generated output; never edit by hand

## Local usage

```bash
pip install pyyaml
python3 scripts/build.py        # validates + regenerates site/
open site/index.html            # preview
```

Or just open the repo in **Claude Code** and say things like:
- "add a 122 written homework due next Thursday"
- "my 151 recitation moved to WEH 6423"
- "I joined Prof X's lab, Wed/Fri 2–4"

`CLAUDE.md` teaches Claude exactly which file to edit, how to rebuild, and the scheduling
rules to respect (sleep, gym windows, startup hours, crunch weeks).

## One-time setup

1. **Create the GitHub repo and push:**
   ```bash
   git init && git add -A && git commit -m "init calendar system"
   git branch -M main
   git remote add origin git@github.com:syoncodes/calendar-system.git
   git push -u origin main
   ```
2. **Enable GitHub Pages:** repo → Settings → Pages → Source: **GitHub Actions**.
   The included workflow (`.github/workflows/pages.yml`) rebuilds from YAML and deploys
   `site/` on every push to `main` — so even edits made in the GitHub web UI publish.
3. **Subscribe Google Calendar:** Google Calendar (desktop web) → **Other calendars → + →
   From URL** → add each per-category feed, then pick a color for each in the sidebar
   (Google colors whole calendars, not individual events — that's why they're split):

   ```
   https://syoncodes.github.io/calendar-system/feeds/classes.ics
   https://syoncodes.github.io/calendar-system/feeds/deadlines.ics
   https://syoncodes.github.io/calendar-system/feeds/study.ics
   https://syoncodes.github.io/calendar-system/feeds/startup.ics
   https://syoncodes.github.io/calendar-system/feeds/research.ics
   https://syoncodes.github.io/calendar-system/feeds/gym.ics
   https://syoncodes.github.io/calendar-system/feeds/personal.ics
   ```

   (Or subscribe to just `.../calendar.ics` for everything in one color.)

## Notes

- Google refreshes subscribed feeds on its own schedule (typically every 12–24 h). Changes
  are *not* instant in Google Calendar; the web calendar updates the moment Pages deploys.
- The feed URL is public (like any Pages site). Keep anything sensitive out of event titles,
  or use a private repo + an obscure repo name if you want it harder to find.
- `ics: false` on a schedule block keeps it out of Google while still showing on the site.
