import csv, json, os
from datetime import datetime, date, timedelta

SRC = os.path.dirname(os.path.abspath(__file__))
TODAY = date.today()

def d(v):
    return datetime.fromtimestamp(float(v)).date() if v else None


def stop_of(row):
    """Closing date, never earlier than creation.

    103 rows in the export carry a stopDate before their creationDate - repeating
    instances, most likely. Left as is, such a task would be counted as closed on a
    day it did not yet exist, and the running open count would dip below zero.
    """
    c, s = d(row["creationDate"]), d(row["stopDate"])
    return None if s is None else (c if c and s < c else s)

areas = {r["uuid"]: r["title"] for r in csv.DictReader(open(f"{SRC}/areas.csv", encoding="utf-8"))}
rows = list(csv.DictReader(open(f"{SRC}/tasks.csv", encoding="utf-8")))
heads = {r["uuid"]: r for r in rows if r["type"] == "2"}

def proj_of(r):
    if r["project"]:
        return r["project"]
    h = heads.get(r["heading"])
    return h["project"] if h else None

tasks = {}
for r in rows:
    if r["type"] == "0":
        p = proj_of(r)
        if p:
            tasks.setdefault(p, []).append(r)

hs = {}
for h in heads.values():
    if h["project"]:
        hs.setdefault(h["project"], []).append(h)

def series(tl, start, end):
    """Daily [oo, no, oc, nc] over [start, end], run-length encoded.

    oo - created earlier, still open at the end of the day
    no - created that day, still open at the end of it
    oc - created earlier, closed that day
    nc - created and closed the same day
    Computed by a sweep instead of rescanning every task per day:
      open_at_end(day) = running sum of (created - closed)
      old(day)         = open_at_end(day) - (created that day and still open after it)
    """
    span = (end - start).days + 1
    created = [0] * span
    closed = [0] * span
    born_open = [0] * span
    # carried in: created before the window and not yet closed when it opens.
    # Closures that land on the first day are subtracted by the sweep below,
    # so they must still be counted here.
    before = 0
    for c, s in tl:
        ci = (c - start).days
        si = (s - start).days if s else None
        if ci < 0:
            if s is None or s >= start:
                before += 1
        elif ci < span:
            created[ci] += 1
            if s is None or s > c:
                born_open[ci] += 1
        if si is not None and 0 <= si < span:
            closed[si] += 1

    out, cur = [], before
    for i in range(span):
        cur += created[i] - closed[i]
        no = born_open[i]
        nc = created[i] - no                 # created and closed the same day
        oc = closed[i] - nc                  # created earlier, closed that day
        out.append([cur - no, no, oc, nc])

    rle = []
    for e in out:
        if rle and rle[-1][:4] == e:
            rle[-1][4] += 1
        else:
            rle.append(e + [1])
    return rle

projects, earliest = [], TODAY
for r in rows:
    if r["type"] != "1" or r["status"] == "2":      # canceled projects stay out
        continue
    area = areas.get(r["area"], "")
    if area == "Templates":
        continue
    tl, pairs = [], []
    for t in tasks.get(r["uuid"], []):
        c, s = d(t["creationDate"]), stop_of(t)
        if c is None:
            continue
        tl.append([c.isoformat(), s.isoformat() if s else None])
        pairs.append((c, s))
        earliest = min(earliest, c)
    if not tl:
        continue

    pc, ps = d(r["creationDate"]), d(r["stopDate"])
    stops = [s for _, s in pairs if s]
    rec = {
        "u": r["uuid"],
        "t": r["item_title"] or "(без названия)",
        "a": area or "Без области",
        "sd": int(r["start"]),
        "st": int(r["status"]),
        "cd": pc.isoformat(),
        "ed": ps.isoformat() if ps else None,
        "k": tl,
    }
    if stops:
        s0 = min(stops)
        e0 = ps if ps else TODAY
        if e0 < s0:
            e0 = s0
        rec["s"] = s0.isoformat()
        rec["e"] = e0.isoformat()
        rec["r"] = series(pairs, s0, e0)

        hrows = []
        for h in hs.get(r["uuid"], []):
            hts = [stop_of(t) for t in tasks.get(r["uuid"], [])
                   if t["heading"] == h["uuid"] and t["stopDate"]]
            started = bool(hts)
            hstart = min(hts) if started else d(h["creationDate"])
            if hstart is None:
                continue
            hstop = d(h["stopDate"]) or e0
            o = (max(hstart, s0) - s0).days
            e2 = (min(hstop, e0) - s0).days
            hrows.append({"t": h["item_title"] or "(без названия)",
                          "o": o, "e": max(e2, o),
                          "started": started, "open": h["stopDate"] == ""})
        hrows.sort(key=lambda x: (x["o"], x["e"]))
        rec["h"] = hrows
    projects.append(rec)

projects.sort(key=lambda p: p["t"].lower())
# weeks run Monday..Sunday: weekday() is already Mon=0
def week_start(x):
    return x - timedelta(days=x.weekday())

wstart = week_start(TODAY)          # the week holding today, still running
weeks = []
m = week_start(earliest)
while m <= wstart:
    weeks.append(m.isoformat())
    m += timedelta(days=7)

# ---- burndown: every task that belongs to a project or sits in an area ----
tpl_area = {u for u, t in areas.items() if t == "Templates"}
tpl_proj = {r["uuid"] for r in rows if r["type"] == "1" and r["area"] in tpl_area}

proj_area = {r["uuid"]: r["area"] for r in rows if r["type"] == "1"}

burn = []
for r in rows:
    if r["type"] != "0":
        continue
    pu = proj_of(r)
    if pu in tpl_proj or r["area"] in tpl_area:
        continue
    if not pu and not r["area"]:
        continue                       # loose task: no project, no area
    c, sd2 = d(r["creationDate"]), stop_of(r)
    if not c:
        continue
    # the task's own area, else the area its project sits in
    au = r["area"] or (proj_area.get(pu, "") if pu else "")
    burn.append((c, sd2, areas.get(au, "") or "Без области", d(r["userModificationDate"])))

burn_areas = sorted({a for _, _, a, _ in burn})
aidx = {a: i for i, a in enumerate(burn_areas)}
# every closure and every last edit, including tasks filed in no project and no area
closed_all, modified_all = [], []
for r in rows:
    if r["type"] != "0":
        continue
    pu = proj_of(r)
    if pu in tpl_proj or r["area"] in tpl_area:
        continue
    sd2 = stop_of(r)
    if sd2:
        closed_all.append(sd2)
    md = d(r["userModificationDate"])
    if md:
        modified_all.append(md)

b0 = min(c for c, _, _, _ in burn)
# [created, closed, area, last edit] as day offsets from b0. Things keeps only the
# date of the latest edit, so an older week loses every task edited again since.
pairs = [[(c - b0).days, ((sd2 - b0).days if sd2 else None), aidx[a], ((md - b0).days if md else None)]
         for c, sd2, a, md in burn]
pairs.sort(key=lambda x: (x[0], x[1] if x[1] is not None else 1 << 30))

span_all = (TODAY - b0).days + 1
all_by_day = [0] * span_all
for sd2 in closed_all:
    i = (sd2 - b0).days
    if 0 <= i < span_all:
        all_by_day[i] += 1
mod_by_day = [0] * span_all
for md in modified_all:
    i = (md - b0).days
    if 0 <= i < span_all:
        mod_by_day[i] += 1

payload = {"projects": projects, "weeks": weeks, "current": wstart.isoformat(), "today": TODAY.isoformat(),
           "burn": {"s": b0.isoformat(), "k": pairs, "areas": burn_areas, "all": all_by_day,
                    "mod": mod_by_day}}
blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
tpl = open(os.path.join(SRC, "week.template.html"), encoding="utf-8").read()
assert "/*__DATA__*/" in tpl, "template lost its data placeholder"
open(os.path.join(SRC, "week.html"), "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/", blob))
print("написан week.html")

print("проектов (без отменённых и Templates):", len(projects))
print("  открытых:", sum(1 for p in projects if p["st"] == 0),
      "| завершённых:", sum(1 for p in projects if p["st"] == 3))
print("  с подневным графиком:", sum(1 for p in projects if "r" in p))
print("задач:", sum(len(p["k"]) for p in projects), "| недель:", len(weeks))
print("текущая неделя:", wstart.isoformat())
print("заголовков:", sum(len(p.get("h", [])) for p in projects),
      "| начатых:", sum(1 for p in projects for h in p.get("h", []) if h["started"]))
print("сжигание: задач", len(burn), "| пар", len(pairs), "| с", b0.isoformat())
print("все закрытия, включая задачи вне проектов и областей:", sum(all_by_day),
      "| только с проектом или областью:", sum(1 for _, x, _, _ in pairs if x is not None))
import collections as _c
for a, n in _c.Counter(a for _, _, a, _ in burn).most_common():
    print(f"   {a:<16}{n}")
