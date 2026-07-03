# CLAUDE.md — Recession & Market-Peak Dashboard

Operating constraints for this repository. Read this in full before writing any code.

## Purpose
A three-lens macro dashboard (recession risk, market-peak froth, price-trend confirmation)
built entirely from sourced public data. Internal IC grade now; structured so it can be
promoted to client-facing later without a rebuild. See SPEC.md for the design.

## Non-negotiable architecture
Follow the standard dashboard architecture. Do not deviate without asking.

- `template.html` — the single source of truth for the UI. Must stay **under 200 KB**. Includes a
  `fetch` fallback so it renders standalone during development (loads from `data/` directly).
- `data/` — JSON files, one logical group per file, updated by GitHub Actions. Every data point
  carries its own source URL and as-of date (see SPEC.md schema).
- `scripts/build.py` — injects the JSON from `data/` into `template.html` and writes the result to
  `docs/index.html`.
- `docs/` — GitHub Pages output. **Generated, never hand-edited.**

## Hard file rules
- **Never open any built output over 500 KB** (`docs/index.html` in particular). Check size first:
  `wc -c <file>`. If a file you need to edit is over 200 KB, **stop and ask** for the source/template
  rather than opening it.
- Edit `template.html` with `grep -n` + `view` on line ranges + `str_replace` patches. Do not read
  the whole built file into context.
- Propose a **multi-turn build plan up front** before writing code. Do not attempt the whole thing
  in one pass.

## Data integrity (strict)
- Every displayed number must have a source. Store `source_url`, a `secondary_source_url`, and an
  `as_of` date in the JSON for each data point.
- **Cross-check every value against at least two independent sources** before it goes live.
- **Verify every data-provider series ID against two sources before first use** (e.g. FRED series
  codes). Do not assume a series ID from memory — confirm it resolves to the intended series.
- Flag any uncertain or estimated number explicitly in the UI and in the JSON `notes` field.
- Do **not** copy Adam Khoo's proprietary thresholds, weights, or the 65–70% / 80% figures. Rebuild
  every input and every threshold independently from public data. Use the reference material in
  `reference/` for taxonomy and layout only, never for values.

## Dates
- Always use a date library. Never compute weekdays or day offsets by hand.
- Confirm month indexing in a comment wherever month arithmetic appears.
- Include at least two edge-case tests: a month boundary and a year boundary.

## Style
- **No contractions anywhere** — UI copy, comments, commit messages, docstrings. Use "do not",
  "it is", "you would", etc.
- White / light theme by default, with maximally readable text.

## Analytical principle
- Where the dashboard shows conditional forward returns, apply entry-point discipline: study returns
  after flat or negative periods and after signals fire, not regime-conditioning on strong runs.

## Local development
- Node.js is installed (Windows machine).
- Quick dev: `npx serve .` then open `template.html` (uses the fetch fallback).
- Full test: `python scripts/build.py` then `npx serve docs` and open the built page.
