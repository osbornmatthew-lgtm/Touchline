# Touchline

Phone-friendly youth league tables, results and fixtures from FA Full-Time.

- EJA Under 16: https://osbornmatthew-lgtm.github.io/Touchline/
- BCFA Under 13 Division 3: https://osbornmatthew-lgtm.github.io/Touchline/bcfa/

How it fits together:

- `config/leagues.json` lists the leagues (season, divisions, cups, age group, colours, folder).
- `runner/touchline.py` runs on a machine at home and keeps the sites up to date. Set-up and day-to-day notes: [runner/README.md](runner/README.md).
- `scripts/scrape.js` reads Full-Time (in a browser page). `scripts/page.html` is the site page; `scripts/make_league.py` and `scripts/build.py` turn page plus data into a site.
- `data/<league>.json` on main is the current data for each league. The live sites are on the `gh-pages` branch (EJA at the root, other leagues in their folders). `status.json` on the `status` branch says how the last update went.
- `hq/` is Touchline HQ, the usage and health dashboard.
- `tests/run_e2e.py` tests the whole update against a mock Full-Time.

`scripts/update.py`, `template.html`, `site/` and `.github/workflows/update.yml` are from the earlier Netlify version and are no longer used.
