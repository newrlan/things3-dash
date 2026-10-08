# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Year tab: a strip of the weeks of a year, each week the darker the more tasks
  were closed in it. Navigation by year; a double click on a week opens it on
  the week tab.
- Year tab: the names of the projects started in each week above the strip and
  of the projects closed in it under the strip; hovering a name
  marks the weeks from the start of the project to its closing. Copies of
  repeating projects are left out.
- Project names are links that open the project in Things, on the year tab and
  in "Projects of the week".
- Year tab: canceled projects are shown only on hover; the "show all" switch
  names every project.
- Year tab: the totals of the year under the strip: tasks and projects, each as
  added, closed and canceled.
- "Projects of the week": a project in which no task was closed for two weeks or
  more is marked "стоит N недель".

## [0.3.1] - 2026-10-05

### Added

- MIT license.

### Changed

- `docs/history-schema.md` is translated into English.

## [0.3.0] - 2026-10-05

### Added

- Balance by area: an outer line with the tasks touched in the week (created,
  edited or closed, tasks still in the Inbox left out). Collected at every
  refresh starting from the week of the first run; earlier weeks show closures
  only.

### Changed

- Balance by area: the scale is the same for every week, 30 tasks at the outer
  ring; a larger value runs out of the ring.
- Balance by area: smaller marks on the closures line, none for an area with no
  closures.

## [0.2.0] - 2026-10-05

### Added

- Weekly history in `history.sqlite`: every complete week is frozen once and
  past weeks no longer change when areas, projects or tasks are deleted in
  Things. The first run fills the history from the current database. Schema
  and rules: `docs/history-schema.md`.
- Balance by area: a wheel of tasks closed per area in the week.
- Added and done in the week: one bar of new open, new closed and old closed tasks.
- `build_week.py` refuses an empty export or one with less than half of the
  previous to-dos, so a failed export is never frozen into the history.

### Changed

- A task belongs to the last known area of itself or its project; tasks
  outside any area, including loose ones, count as "Без области".
- `week.html` is written atomically.
- `build_week.py` reads the Things database directly, read-only, instead of
  going through CSV files.

### Removed

- Weekly burn chart.
- Per-project day-by-day history on hover in "Projects of the week".
- Special handling of the `Templates` area.
- `export.sh` and the intermediate `tasks.csv` and `areas.csv`.
- The text block under "Projects of the week".

## [0.1.0] - 2026-09-27

### Added

- Read-only export of tasks, projects, headings and areas from the local
  Things 3 database into CSV (`export.sh`).
- Self-contained weekly dashboard page `week.html` built from a template
  (`build_week.py`, `week.template.html`), with navigation by week:
  - closures by weekday against a negative binomial fitted on previous weeks;
  - weekly burn chart;
  - projects of the week, with a per-project day-by-day history on hover.
- `refresh.sh` to run the export and the build in one step.
- Local http server `serve.py` with a refresh button on the page.
- README with setup and usage instructions, dashboard screenshot.

[Unreleased]: https://github.com/newrlan/things3-dash/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/newrlan/things3-dash/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/newrlan/things3-dash/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/newrlan/things3-dash/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/newrlan/things3-dash/releases/tag/v0.1.0
