# things3-dash

A weekly dashboard for [Things 3](https://culturedcode.com/things/) on macOS.
It reads the local Things database (read-only) and builds a single
self-contained HTML page: data embedded, no external requests, works offline.

The page interface is in Russian.

![Dashboard for one week](docs/screenshot.png)

## What the page shows

Navigation by week (Monday to Sunday), from the first week with data up to the
current one.

1. **Closures by weekday.** One strip per weekday: the darker the cell, the more
   likely that many closures on that day. The distribution is a negative
   binomial fitted on up to 55 previous full weeks. The highlighted cell is the
   selected week. All closures count, including tasks outside projects and areas.
2. **Weekly burn.** One column per day. Above the line: tasks added this week
   and still open at the end of the day. Below: tasks closed that day, split into
   "created before the week" and "added this week".
3. **Projects of the week.** One row per active project: closed tasks to the
   right, open tasks to the left, each split into "created earlier" and
   "created this week". Hover a project name to see its whole day-by-day history
   together with its headings.

## Requirements

- macOS with the Things 3 Mac app and its local database
- `bash` and `sqlite3` (both ship with macOS)
- Python 3.7 or newer, standard library only

## Install

```sh
git clone https://github.com/newrlan/things3-dash.git
cd things3-dash
```

No dependencies to install.

## Usage

### Build the page once

```sh
./refresh.sh
open week.html
```

`refresh.sh` runs two steps:

1. `export.sh` reads the Things database and writes `tasks.csv` and `areas.csv`
   next to the scripts.
2. `build_week.py` builds `week.html` from `week.template.html` and the CSV files.

To see fresh data, run `./refresh.sh` again and reload the page.

### Refresh from the browser

```sh
python3 serve.py          # default port 8765
python3 serve.py 9000     # another port
```

Open http://127.0.0.1:8765/week.html. Served over http, the page shows the
refresh data button: it asks `serve.py` to run
`refresh.sh` and reloads the page when done. The button is hidden when the page
is opened as a local file.

## How the data is read

- The database is found at
  `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-*/Things Database.thingsdatabase/main.sqlite`.
  If there are several `ThingsData-*` directories, the most recently modified
  one is used.
- `sqlite3` opens it read-only (`-readonly`, `mode=ro`). Nothing is copied or
  written into the Things container.
- If macOS refuses access to the database, allow your terminal app access in
  System Settings > Privacy & Security.

## Privacy

- To-do titles are not exported. Only project and heading titles leave the
  database; they are embedded in `week.html`.
- `tasks.csv`, `areas.csv` and `week.html` hold your personal data and are
  listed in `.gitignore`. Do not publish them.

## What is counted

- Trashed items are excluded.
- Canceled projects are not shown as rows, but their tasks count in the burn chart.
- Projects currently in Someday are hidden. Things keeps no history of moves,
  so for past weeks this reflects where a project is now, not where it was then.
- An area named `Templates` is excluded completely (the name is hard-coded in
  `build_week.py`).
- A task whose closing date is earlier than its creation date is treated as
  closed on its creation day.

## Known limitations

- Canceled tasks count as closed, the same as completed ones.
- Repeating to-dos are not filtered out.
- The export relies on the Things database schema (`TMTask`, `TMArea`). A Things
  update that changes the schema can break it; `export.sh` prints the `TMTask`
  columns on every run to make such a change visible.
- `serve.py` listens on `127.0.0.1` only, but `POST /refresh` has no protection
  against requests sent by other web pages open in the same browser, and the
  server gives out every file in the project directory, including the CSV
  exports. Run it only while you need it.

## Files

| File | Purpose |
|---|---|
| `export.sh` | Read-only export from the Things database into CSV |
| `build_week.py` | Builds `week.html` from the CSV files and the template |
| `week.template.html` | Page template: styles, charts, the `/*__DATA__*/` placeholder |
| `refresh.sh` | Runs the export and the build |
| `serve.py` | Local http server with the refresh endpoint |
