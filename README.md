# Touchline

EJA Under 16 league tables, results and fixtures, live at https://touchline-eja.netlify.app

- `scripts/update.py` pulls the latest tables, results, fixtures and cup ties from FA Full-Time and rebuilds `site/index.html`.
- `.github/workflows/update.yml` runs it on Saturday morning, Sunday evening and Monday evening, and can be run by hand from the Actions tab.
- Netlify publishes the `site` folder whenever it changes.
