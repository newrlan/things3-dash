# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/newrlan/things3-dash/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/newrlan/things3-dash/releases/tag/v0.1.0
