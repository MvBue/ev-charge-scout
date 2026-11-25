# EV Charge Scout

Map of public EV charging stations in Switzerland around your phone's GPS
position: charging power (kW), AC/DC and plug type, live availability, price
(where the operator publishes it) and distance. Runs as a web app you can add
to your phone's home screen. Same setup as fantasy-stat-scout.

## How it works
- `fetch_chargers.py` downloads the federal open data from the Swiss Federal
  Office of Energy (BFE, ich-tanke-strom.ch) on data.geo.admin.ch and writes a
  compact `site/chargers.json` (stations, power, plugs, price text).
- `.github/workflows/update-data.yml` runs it daily and on every push to `main`,
  then publishes `site/` to GitHub Pages.
- `site/index.html` is the app. It loads `chargers.json`, then fetches live
  availability straight from data.geo.admin.ch every 2 minutes.

## One-time setup
1. Push this repo to GitHub (branch `main`).
2. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions → Update charger data → Run workflow**. The run shows the site address.
4. Open it in Chrome on your phone → **Add to Home screen**. GPS needs HTTPS, which Pages provides.

No secrets or API keys needed.

## Run locally
```
python3 fetch_chargers.py
cd site && python3 -m http.server 8000   # then open http://localhost:8000
```

## Limits
- Prices are only published for about a quarter of the stations; the rest show "ask operator".
- Distances are straight-line, not driving distance.
- Map tiles come from openstreetmap.org (fine for personal use; heavy use needs another tile provider).
