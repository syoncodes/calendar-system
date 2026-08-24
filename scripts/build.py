#!/usr/bin/env python3
"""
build.py — compiles data/*.yaml into:
  site/data.js       (powers the interactive glass calendar)
  site/calendar.ics  (subscribable feed for Google Calendar)

Run after ANY edit to data/:  python scripts/build.py
Exits non-zero on validation errors.
"""
import json, sys, datetime as dt
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA, SITE = ROOT / "data", ROOT / "site"

DAY_ORDER = ["sunday","monday","tuesday","wednesday","thursday","friday","saturday"]
ICS_DAY = {0:"SU",1:"MO",2:"TU",3:"WE",4:"TH",5:"FR",6:"SA"}
VALID_CATS = {"class","study","research","startup","gym","personal","transit"}
VALID_KINDS = {"exam","hw","brk","fly","adm","mile"}

def load(name):
    with open(DATA / name) as f:
        return yaml.safe_load(f)

def hm_to_float(s):
    h, m = map(int, str(s).split(":"))
    return h + m / 60

def die(msg):
    print(f"FAIL  {msg}"); sys.exit(1)

def validate(schedule, events):
    for day in DAY_ORDER:
        blocks = schedule.get(day, [])
        prev_end = -1
        for b in blocks:
            if not isinstance(b, dict):
                die(f"{day}: malformed block entry (empty or bad YAML): {b!r}")
            for f in ("start","end","cat","title"):
                if f not in b: die(f"{day}: block missing '{f}': {b}")
            if b["cat"] not in VALID_CATS: die(f"{day}: bad cat '{b['cat']}' in '{b['title']}'")
            s, e = hm_to_float(b["start"]), hm_to_float(b["end"])
            if e <= s: die(f"{day}: '{b['title']}' ends before it starts")
            if s < prev_end - 1e-9:
                die(f"{day}: '{b['title']}' overlaps the previous block")
            prev_end = e
    for ev in events["events"]:
        if ev.get("kind") not in VALID_KINDS: die(f"event bad kind: {ev}")
        if not isinstance(ev.get("date"), dt.date): die(f"event bad/missing date: {ev}")
    print("ok  validation passed")

# ---------------- guardrails ----------------
WEEKDAYS = ["monday","tuesday","wednesday","thursday","friday"]

def enforce_guardrails(schedule, guard):
    errs, warns = [], []
    g_sleep, g_gym = guard["sleep"], guard["gym"]
    lights = {d: hm_to_float(g_sleep["weekday_lights_out"]) for d in WEEKDAYS}
    lights["saturday"] = hm_to_float(g_sleep["saturday_lights_out"])
    lights["sunday"] = hm_to_float(g_sleep["sunday_lights_out"])
    wake = {d: hm_to_float(g_sleep["weekday_wake"]) for d in WEEKDAYS}
    wake["saturday"] = wake["sunday"] = hm_to_float(g_sleep["weekend_wake_earliest"])

    for day in DAY_ORDER:
        blocks = schedule.get(day, [])
        if not blocks:
            errs.append(f"{day}: empty day — the system schedules every day"); continue
        # sleep window
        first_s = hm_to_float(blocks[0]["start"]); last_e = hm_to_float(blocks[-1]["end"])
        if first_s < wake[day] - 1e-9:
            errs.append(f"{day}: '{blocks[0]['title']}' starts {blocks[0]['start']} — before wake floor {'%05.2f'%wake[day]} (sleep is inviolable)")
        if last_e > lights[day] + 1e-9:
            errs.append(f"{day}: '{blocks[-1]['title']}' ends {blocks[-1]['end']} — past lights-out (sleep is inviolable)")
        # gym rules
        gyms = [b for b in blocks if b["cat"] == "gym"]
        if g_gym.get("required_daily") and not gyms:
            errs.append(f"{day}: no gym block — gym is daily, non-negotiable")
        opens = hm_to_float(g_gym["opens"]["weekend" if day in ("saturday","sunday") else "weekday"])
        for gb in gyms:
            gs, ge = hm_to_float(gb["start"]), hm_to_float(gb["end"])
            dur = round((ge - gs) * 60)
            if gs < opens - 1e-9:
                errs.append(f"{day}: gym starts {gb['start']} but Cohon UC opens {'%.2f'%opens} — impossible")
            if day in g_gym["short_days"] and dur > g_gym["short_max_minutes"]:
                errs.append(f"{day}: gym is {dur} min — short-day ceiling is {g_gym['short_max_minutes']} min (8 AM recitation)")
            if day not in g_gym["short_days"] and dur < g_gym["full_min_minutes"]:
                errs.append(f"{day}: gym is {dur} min — full-session floor is {g_gym['full_min_minutes']} min")
            # shower buffer before the next class
            nxt = next((b for b in blocks if b["cat"] == "class" and hm_to_float(b["start"]) >= ge), None)
            if nxt:
                gap = round((hm_to_float(nxt["start"]) - ge) * 60)
                if gap < g_gym["post_gym_class_buffer_minutes"]:
                    errs.append(f"{day}: only {gap} min between gym and '{nxt['title']}' — need {g_gym['post_gym_class_buffer_minutes']} for shower + walk")
        # family contact
        if guard["protected"].get("daily_family_contact"):
            if not any(b["cat"] == "personal" and "family" in b["title"].lower() for b in blocks):
                errs.append(f"{day}: no family-contact block — daily 10–15 min is protected by design")

    # weekly hour bands (warnings)
    totals = {}
    for day in DAY_ORDER:
        for b in schedule.get(day, []):
            totals[b["cat"]] = totals.get(b["cat"], 0) + (hm_to_float(b["end"]) - hm_to_float(b["start"]))
    for cat, band in guard.get("weekly_hours", {}).items():
        h = round(totals.get(cat, 0), 1)
        if h < band["min"]: warns.append(f"{cat}: {h} h/week is under the {band['min']}–{band['max']} band")
        if h > band["max"]: warns.append(f"{cat}: {h} h/week is over the {band['min']}–{band['max']} band")

    for w in warns: print(f"warn  {w}")
    if errs:
        print("\nGUARDRAIL VIOLATIONS — build blocked:")
        for e in errs: print(f"  ✗ {e}")
        print("\nFix the schedule, or — only with the user's explicit sign-off — change data/guardrails.yaml.")
        sys.exit(1)
    print(f"ok  guardrails passed  (weekly: " + ", ".join(f"{c} {round(totals.get(c,0),1)}h" for c in ("class","study","research","startup","gym")) + ")")

# ---------------- data.js ----------------
def build_datajs(schedule, events, tooltips):
    cfg = events["config"]
    week = {}
    for i, day in enumerate(DAY_ORDER):
        week[i] = [[hm_to_float(b["start"]), hm_to_float(b["end"]), b["cat"], b["title"], b.get("meta","")]
                   for b in schedule.get(day, [])]
    S = {}
    for ev in events["events"]:
        S.setdefault(str(ev["date"]), []).append({"t": ev["title"], "k": ev["kind"]})
    cal = {
        "week": week,
        "S": S,
        "noClassAll": [str(d) for d in cfg["no_class_dates"]],
        "noDaytime": [str(d) for d in cfg["no_daytime_dates"]],
        "crunch": [str(d) for d in cfg["crunch_dates"]],
        "INFO": tooltips,
        "semStart": str(cfg["semester_start"]),
        "semEnd": str(cfg["last_day_of_classes"]),
    }
    out = "window.CAL=" + json.dumps(cal, ensure_ascii=False) + ";\n"
    (SITE / "data.js").write_text(out)
    print(f"ok  site/data.js  ({len(out)//1024} KB)")

# ---------------- calendar.ics ----------------
def ics_escape(s):
    return s.replace("\\","\\\\").replace(",","\\,").replace(";","\\;").replace("\n","\\n")

def first_on_or_after(start, weekday):
    # weekday: 0=Sunday .. 6=Saturday; python date.weekday(): Mon=0..Sun=6
    py = (weekday - 1) % 7
    d = start
    while d.weekday() != py:
        d += dt.timedelta(days=1)
    return d

def build_ics(schedule, events):
    cfg = events["config"]
    tz = cfg["timezone"]
    sem_start = cfg["semester_start"]
    # both end dates are inclusive; UNTIL compares against occurrence starts, so extend past midnight
    class_until = cfg["last_day_of_classes"] + dt.timedelta(days=1)
    other_until = cfg["recurring_until"] + dt.timedelta(days=1)
    no_class = set(cfg["no_class_dates"])
    no_day = set(cfg["no_daytime_dates"])

    L = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//CalendarSystem//Fall2026//EN",
         "CALSCALE:GREGORIAN","X-WR-CALNAME:Fall 2026 System",f"X-WR-TIMEZONE:{tz}",
         "BEGIN:VTIMEZONE",f"TZID:{tz}",
         "BEGIN:DAYLIGHT","TZOFFSETFROM:-0500","TZOFFSETTO:-0400","TZNAME:EDT",
         "DTSTART:19700308T020000","RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU","END:DAYLIGHT",
         "BEGIN:STANDARD","TZOFFSETFROM:-0400","TZOFFSETTO:-0500","TZNAME:EST",
         "DTSTART:19701101T020000","RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU","END:STANDARD",
         "END:VTIMEZONE"]

    uid_n = 0
    def uid():
        nonlocal uid_n; uid_n += 1
        return f"blk-{uid_n}@calendar-system"

    # RFC 5545 requires DTSTAMP in every VEVENT; a fixed value keeps rebuilds byte-identical
    dtstamp = f"DTSTAMP:{sem_start:%Y%m%d}T000000Z"

    # recurring weekly blocks
    for i, day in enumerate(DAY_ORDER):
        for b in schedule.get(day, []):
            if b.get("ics") is False:
                continue
            is_class = b["cat"] == "class"
            until = class_until if is_class else other_until
            start_date = first_on_or_after(sem_start, i)
            sh, sm = map(int, b["start"].split(":"))
            eh, em = map(int, b["end"].split(":"))
            dstart = f"{start_date:%Y%m%d}T{sh:02d}{sm:02d}00"
            dend   = f"{start_date:%Y%m%d}T{eh:02d}{em:02d}00"
            L += ["BEGIN:VEVENT", f"UID:{uid()}", dtstamp,
                  f"DTSTART;TZID={tz}:{dstart}", f"DTEND;TZID={tz}:{dend}",
                  f"RRULE:FREQ=WEEKLY;BYDAY={ICS_DAY[i]};UNTIL={until:%Y%m%d}T045959Z"]
            if is_class:
                cancelled = [d for d in no_class if d.isoweekday() % 7 == i]
                if hm_to_float(b["start"]) < 17 and not b.get("evening"):
                    cancelled += [d for d in no_day if d.isoweekday() % 7 == i]
                for d in sorted(cancelled):
                    L.append(f"EXDATE;TZID={tz}:{d:%Y%m%d}T{sh:02d}{sm:02d}00")
            summary = b["title"] + (f" - {b['meta']}" if b.get("meta") else "")
            L.append(f"SUMMARY:{ics_escape(summary)}")
            L.append("END:VEVENT")

    # one-off events
    for ev in events["events"]:
        L += ["BEGIN:VEVENT", f"UID:{uid()}", dtstamp]
        if ev.get("time"):
            h, m = map(int, str(ev["time"]).split(":"))
            dur = int(ev.get("duration_min", 60))
            st = dt.datetime.combine(ev["date"], dt.time(h, m))
            en = st + dt.timedelta(minutes=dur)
            L += [f"DTSTART;TZID={tz}:{st:%Y%m%dT%H%M%S}", f"DTEND;TZID={tz}:{en:%Y%m%dT%H%M%S}"]
        else:
            L.append(f"DTSTART;VALUE=DATE:{ev['date']:%Y%m%d}")
        prefix = {"exam":"[EXAM] ","hw":"[HW] ","brk":"[BREAK] ","fly":"[FLIGHT] ","adm":"[DEADLINE] ","mile":"[KEY] "}[ev["kind"]]
        L.append(f"SUMMARY:{ics_escape(prefix + ev['title'])}")
        if ev.get("location"):
            L.append(f"LOCATION:{ics_escape(ev['location'])}")
        L.append("END:VEVENT")

    L.append("END:VCALENDAR")
    (SITE / "calendar.ics").write_text("\r\n".join(L) + "\r\n")
    n = sum(1 for x in L if x == "BEGIN:VEVENT")
    print(f"ok  site/calendar.ics  ({n} events)")

def main():
    schedule = load("schedule.yaml")
    events = load("events.yaml")
    tooltips = load("tooltips.yaml")
    guard = load("guardrails.yaml")
    validate(schedule, events)
    enforce_guardrails(schedule, guard)
    SITE.mkdir(exist_ok=True)
    build_datajs(schedule, events, tooltips)
    build_ics(schedule, events)
    print("ok  build complete - commit & push to publish")

if __name__ == "__main__":
    main()
