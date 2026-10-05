"""Builds week.html from the Things database and keeps the weekly history.

Steps:
  1. read the Things database (read-only) and refuse an export that looks broken;
  2. update the reference tables of history.sqlite (areas, projects with their
     last known area);
  3. freeze every complete week that is not frozen yet;
  4. take the frozen weeks from the history, compute the running week live with
     the same code, and embed it all into week.html.

The schema and its rules are described in docs/history-schema.md.
"""

import glob
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import quote

SRC = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(SRC, "history.sqlite")
# Things keeps one directory per data set
THINGS = os.path.expanduser("~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/"
                            "ThingsData-*/Things Database.thingsdatabase/main.sqlite")
TODAY = date.today()
RULES = 1                      # version of the counting rules, stored with every frozen week
NO_AREA = ""                   # area uuid of "Без области"
NO_AREA_TITLE = "Без области"
MIN_KEEP = 0.5                 # an export with fewer to-dos than this share of the previous one is refused

DATE = "TEXT NOT NULL CHECK ({0} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')"
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS area (
  area_uuid   TEXT PRIMARY KEY,
  title       TEXT NOT NULL,
  first_seen  {DATE.format("first_seen")},
  last_seen   {DATE.format("last_seen")},
  deleted_at  TEXT
);
CREATE TABLE IF NOT EXISTS project (
  project_uuid TEXT PRIMARY KEY,
  title        TEXT NOT NULL,
  area_uuid    TEXT NOT NULL REFERENCES area,
  created      {DATE.format("created")},
  closed       TEXT,
  status       INTEGER NOT NULL,
  first_seen   {DATE.format("first_seen")},
  last_seen    {DATE.format("last_seen")},
  deleted_at   TEXT
);
CREATE TABLE IF NOT EXISTS meta (
  key    TEXT PRIMARY KEY,
  value  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS week (
  week_start  TEXT PRIMARY KEY,
  frozen_at   TEXT NOT NULL,
  rules       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS day_flow (
  day            {DATE.format("day")},
  area_uuid      TEXT NOT NULL REFERENCES area,
  new_open       INTEGER NOT NULL,
  new_completed  INTEGER NOT NULL,
  new_canceled   INTEGER NOT NULL,
  old_completed  INTEGER NOT NULL,
  old_canceled   INTEGER NOT NULL,
  PRIMARY KEY (day, area_uuid)
);
CREATE TABLE IF NOT EXISTS area_week (
  week_start  TEXT NOT NULL REFERENCES week,
  area_uuid   TEXT NOT NULL REFERENCES area,
  title       TEXT NOT NULL,
  PRIMARY KEY (week_start, area_uuid)
);
CREATE TABLE IF NOT EXISTS project_week (
  week_start      TEXT NOT NULL REFERENCES week,
  project_uuid    TEXT NOT NULL REFERENCES project,
  area_uuid       TEXT NOT NULL REFERENCES area,
  someday         INTEGER NOT NULL,
  state           INTEGER NOT NULL,
  open_old        INTEGER NOT NULL,
  open_new        INTEGER NOT NULL,
  closed_old_completed INTEGER NOT NULL,
  closed_old_canceled  INTEGER NOT NULL,
  closed_new_completed INTEGER NOT NULL,
  closed_new_canceled  INTEGER NOT NULL,
  PRIMARY KEY (week_start, project_uuid)
);
"""


def d(v):
    return datetime.fromtimestamp(float(v)).date() if v else None


def iso(x):
    return x.isoformat() if x else None


def week_start(x):
    return x - timedelta(days=x.weekday())          # weeks run Monday..Sunday


def cutoff(ws):
    """Last day that counts for the week: its Sunday, or today for the running week."""
    return min(ws + timedelta(days=6), TODAY)


def stop_of(row):
    """Closing date, never earlier than creation.

    Some rows carry a stopDate before their creationDate. Left as is, such a task
    would be counted as closed on a day it did not yet exist.
    """
    c, s = d(row["creationDate"]), d(row["stopDate"])
    return None if s is None else (c if c and s < c else s)


def keep_area(now, prev, alive):
    """Last known area, see "Последняя известная область" in docs/history-schema.md."""
    if now:
        return now
    if prev and prev not in alive:                  # the area was deleted: keep it
        return prev
    return NO_AREA


# ---- 1. export --------------------------------------------------------------

def read_things():
    """Areas and the rows of TMTask, straight from the Things database.

    Read-only: the database is opened with mode=ro, nothing is copied and nothing
    is written into the Things container. Titles of to-dos are NOT read, only the
    titles of projects and headings.
    """
    try:
        found = glob.glob(THINGS)
    except OSError as e:
        sys.exit(f"нет доступа к базе Things: {e}")
    if not found:
        sys.exit(f"база Things не найдена или к ней нет доступа: {THINGS}")
    path = max(found, key=os.path.getmtime)         # several data sets: the most recently modified
    print("база Things:", path)
    try:
        con = sqlite3.connect(f"file:{quote(path)}?mode=ro", uri=True, timeout=30)
        con.row_factory = sqlite3.Row
        areas = {r["uuid"]: r["title"] for r in con.execute("SELECT uuid, title FROM TMArea")}
        rows = [dict(r) for r in con.execute("""
            SELECT uuid,
                   type,            -- 0 = to-do, 1 = project, 2 = heading
                   status,          -- 0 = open, 2 = canceled, 3 = completed
                   creationDate,    -- unix time
                   stopDate,        -- unix time, set when completed or canceled
                   start,           -- 0 = Inbox, 1 = Anytime, 2 = Someday
                   project,         -- uuid of the parent project
                   heading,         -- uuid of the parent heading, when the item sits under one
                   area,            -- uuid of the area
                   CASE WHEN type IN (1, 2) THEN title ELSE '' END AS item_title
            FROM TMTask
            WHERE trashed = 0""")]
        con.close()
    except sqlite3.Error as e:
        # a Things update that changes the schema shows up here, with the name of what is missing
        sys.exit(f"не удалось прочитать базу Things: {e}")
    return areas, rows


def check_export(con, todos):
    """Refuses an export that looks broken, then remembers its size for the next run."""
    if not todos:
        sys.exit("в базе Things нет задач, обновление прервано")
    row = con.execute("SELECT value FROM meta WHERE key = 'export_todos'").fetchone()
    prev = int(row[0]) if row else 0
    if prev and len(todos) < prev * MIN_KEEP:
        sys.exit(f"в выгрузке {len(todos)} задач, в прошлой было {prev}: "
                 "похоже на сбой чтения базы, обновление прервано")
    con.execute("INSERT INTO meta (key, value) VALUES ('export_todos', ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (str(len(todos)),))


# ---- 2. reference tables ----------------------------------------------------

def update_areas(con, areas):
    """Returns the uuids of the areas that exist now, "Без области" included."""
    alive = set(areas) | {NO_AREA}
    today = iso(TODAY)
    rows = [(u, t, today, today) for u, t in areas.items()] + [(NO_AREA, NO_AREA_TITLE, today, today)]
    con.executemany("""
        INSERT INTO area (area_uuid, title, first_seen, last_seen) VALUES (?, ?, ?, ?)
        ON CONFLICT (area_uuid) DO UPDATE SET
          title = excluded.title, last_seen = excluded.last_seen, deleted_at = NULL""", rows)
    gone = [(today, u) for (u,) in con.execute("SELECT area_uuid FROM area WHERE deleted_at IS NULL")
            if u not in alive]
    con.executemany("UPDATE area SET deleted_at = ? WHERE area_uuid = ?", gone)
    return alive


def update_projects(con, rows, alive):
    """Returns {project uuid: (last known area, export row)} for the projects in the export."""
    prev = dict(con.execute("SELECT project_uuid, area_uuid FROM project"))
    today = iso(TODAY)
    out, upserts = {}, []
    for r in rows:
        if r["type"] != 1:
            continue
        area = keep_area(r["area"], prev.get(r["uuid"]), alive)
        out[r["uuid"]] = (area, r)
        upserts.append((r["uuid"], r["item_title"] or "(без названия)", area, iso(d(r["creationDate"])),
                        iso(d(r["stopDate"])), int(r["status"]), today, today))
    con.executemany("""
        INSERT INTO project (project_uuid, title, area_uuid, created, closed, status, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (project_uuid) DO UPDATE SET
          title = excluded.title, area_uuid = excluded.area_uuid, created = excluded.created,
          closed = excluded.closed, status = excluded.status, last_seen = excluded.last_seen,
          deleted_at = NULL""", upserts)
    gone = [(today, u) for (u,) in con.execute("SELECT project_uuid FROM project WHERE deleted_at IS NULL")
            if u not in out]
    con.executemany("UPDATE project SET deleted_at = ? WHERE project_uuid = ?", gone)
    return out


def read_tasks(con, todos, heads):
    """The to-dos ready for counting. A to-do takes its own area, else its project's
    last known area; a to-do outside projects whose area was deleted falls under
    "Без области"."""
    project_area = dict(con.execute("SELECT project_uuid, area_uuid FROM project"))
    tasks = []
    for r in todos:
        c = d(r["creationDate"])
        if not c:
            continue
        # a to-do under a heading belongs to the heading's project
        pu = r["project"] or heads.get(r["heading"], {}).get("project") or ""
        area = r["area"] or project_area.get(pu, NO_AREA)
        tasks.append({"c": c, "s": stop_of(r), "canceled": r["status"] == 2, "area": area, "project": pu})
    return tasks


# ---- 3. weekly numbers, shared by the freeze and the running week ----------

def day_flows(tasks):
    """{week start: {(day, area): [new_open, new_completed, new_canceled, old_completed, old_canceled]}}"""
    out = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0]))
    for t in tasks:
        c, s = t["c"], t["s"]
        wc = week_start(c)
        if c <= TODAY and (s is None or s > cutoff(wc)):
            out[wc][(c, t["area"])][0] += 1
        if s and s <= TODAY:
            ws = week_start(s)
            col = (1 if c >= ws else 3) + (1 if t["canceled"] else 0)
            out[ws][(s, t["area"])][col] += 1
    return out


def project_weeks(tasks, projects):
    """{week start: {project uuid: [area, someday, state, open_old, open_new,
    closed_old_completed, closed_old_canceled, closed_new_completed, closed_new_canceled]}}"""
    by_project = defaultdict(list)
    for t in tasks:
        if t["project"] in projects:
            by_project[t["project"]].append(t)
    current = week_start(TODAY)
    out = defaultdict(dict)
    for pu, ts in by_project.items():
        area, r = projects[pu]
        pc, ps, status, someday = d(r["creationDate"]), d(r["stopDate"]), int(r["status"]), int(r["start"] == 2)
        counts = defaultdict(lambda: [0] * 6)
        for t in ts:
            c, s = t["c"], t["s"]
            w, last = week_start(c), min(week_start(s) if s else current, current)
            while w <= last:
                end, new = cutoff(w), c >= w
                if s and w <= s <= end:
                    counts[w][(4 if new else 2) + (1 if t["canceled"] else 0)] += 1
                elif s is None or s > end:
                    counts[w][1 if new else 0] += 1
                w += timedelta(days=7)
        for w, n in counts.items():
            end = cutoff(w)
            # a project belongs to a week if it already existed then and was not closed before it
            if (pc and pc > end) or (ps and ps < w) or not any(n):
                continue
            state = status if ps and ps <= end else 0
            out[w][pu] = [area, someday, state] + n
    return out


def freeze(con, flows, pweeks, alive):
    """Writes every complete week that is not frozen yet. Plain INSERT on purpose:
    writing a frozen week twice is a bug and must fail, not overwrite."""
    frozen = {w for (w,) in con.execute("SELECT week_start FROM week")}
    titles = dict(con.execute("SELECT area_uuid, title FROM area"))
    now = datetime.now().isoformat(timespec="seconds")
    w = min([*flows, *pweeks], default=week_start(TODAY))
    last, n = week_start(TODAY) - timedelta(days=7), 0
    while w <= last:
        if iso(w) not in frozen:
            con.execute("INSERT INTO week (week_start, frozen_at, rules) VALUES (?, ?, ?)", (iso(w), now, RULES))
            rows = flows.get(w, {})
            con.executemany("INSERT INTO day_flow VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [(iso(day), a, *v) for (day, a), v in rows.items()])
            # spokes of the week: the areas that exist now, plus any area with activity in it
            con.executemany("INSERT INTO area_week VALUES (?, ?, ?)",
                            [(iso(w), a, titles[a]) for a in alive | {a for _, a in rows}])
            con.executemany("INSERT INTO project_week VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            [(iso(w), pu, *v) for pu, v in pweeks.get(w, {}).items()])
            n += 1
        w += timedelta(days=7)
    return n


# ---- 4. page data ------------------------------------------------------------

def week_payload(ws, flow_rows, spokes, project_rows, meta):
    """One week for the page: wheel spokes, the flow bar, project rows."""
    closed = defaultdict(int)
    new_open = new_closed = old_closed = 0
    for (_, a), v in flow_rows:
        closed[a] += v[1] + v[2] + v[3] + v[4]
        new_open += v[0]
        new_closed += v[1] + v[2]
        old_closed += v[3] + v[4]
    title = lambda a: spokes.get(a) or meta["areas"][a]
    wheel = [[title(a), closed[a]] for a in sorted(set(spokes) | set(closed), key=title)]

    end = iso(cutoff(ws))
    rows = []
    for pu, v in project_rows.items():
        name, closed_on, status = meta["projects"][pu]
        if v[1] or status == 2:                     # Someday and canceled projects stay out
            continue
        oo, on, coc, coca, cnc, cnca = v[3:]
        state = "open" if not closed_on else ("wk" if closed_on <= end else "later")
        rows.append([name, state, closed_on, coc + coca, cnc + cnca, oo, on])
    return {"a": wheel, "f": [new_open, new_closed, old_closed], "p": rows}


def build_payload(con, flows, pweeks, alive):
    current = week_start(TODAY)
    meta = {
        "areas": dict(con.execute("SELECT area_uuid, title FROM area")),
        "projects": {u: (t, c, s) for u, t, c, s in
                     con.execute("SELECT project_uuid, title, closed, status FROM project")},
    }
    week_flow = defaultdict(list)
    for day, a, *v in con.execute("SELECT * FROM day_flow"):
        week_flow[iso(week_start(date.fromisoformat(day)))].append(((day, a), v))
    week_spokes = defaultdict(dict)
    for w, a, t in con.execute("SELECT week_start, area_uuid, title FROM area_week"):
        week_spokes[w][a] = t
    week_projects = defaultdict(dict)
    for w, pu, *v in con.execute("SELECT * FROM project_week"):
        week_projects[w][pu] = v
    frozen = [w for (w,) in con.execute("SELECT week_start FROM week ORDER BY week_start")]

    wk = {w: week_payload(date.fromisoformat(w), week_flow[w], week_spokes[w], week_projects[w], meta)
          for w in frozen}
    # the running week is computed live; its spokes are the areas that exist now
    week_flow[iso(current)] = [((iso(day), a), v) for (day, a), v in flows.get(current, {}).items()]
    wk[iso(current)] = week_payload(current, week_flow[iso(current)], {a: meta["areas"][a] for a in alive},
                                    pweeks.get(current, {}), meta)

    weeks = sorted(wk)
    # closures per day from the first week to today, for the weekday chart
    first = date.fromisoformat(weeks[0])
    closed = [0] * ((TODAY - first).days + 1)
    for w in weeks:
        for (day, _), v in week_flow[w]:
            closed[(date.fromisoformat(day) - first).days] += v[1] + v[2] + v[3] + v[4]
    return {"weeks": weeks, "current": iso(current), "today": iso(TODAY),
            "days": {"s": iso(first), "closed": closed}, "wk": wk, "frozen": len(frozen)}


def main():
    areas, rows = read_things()
    todos = [r for r in rows if r["type"] == 0]
    heads = {r["uuid"]: r for r in rows if r["type"] == 2}

    con = sqlite3.connect(DB, isolation_level=None, timeout=30)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    # one write transaction: a second refresh waits for the first one and then
    # finds the weeks already frozen
    con.execute("BEGIN IMMEDIATE")
    try:
        check_export(con, todos)
        alive = update_areas(con, areas)
        projects = update_projects(con, rows, alive)
        tasks = read_tasks(con, todos, heads)
        flows = day_flows(tasks)
        pweeks = project_weeks(tasks, projects)
        n = freeze(con, flows, pweeks, alive)
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise

    payload = build_payload(con, flows, pweeks, alive)
    con.close()

    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(SRC, "week.template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "/*__DATA__*/" in tpl, "template lost its data placeholder"
    out = os.path.join(SRC, "week.html")
    with open(out + ".tmp", "w", encoding="utf-8") as f:
        f.write(tpl.replace("/*__DATA__*/", blob))
    os.replace(out + ".tmp", out)                   # the server never sees a half-written page

    print("написан week.html")
    print("задач в базе Things:", len(todos), "| проектов:", len(projects), "| областей:", len(areas))
    print("недель в истории:", payload["frozen"], "| заморожено сейчас:", n,
          "| текущая неделя:", payload["current"])


if __name__ == "__main__":
    main()
