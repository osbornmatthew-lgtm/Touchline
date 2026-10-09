# Touchline home runner

Updates the Touchline sites from FA Full-Time on a machine at home, with no Claude and no open Chrome.
Full-Time refuses cloud servers, so this has to run on a home broadband connection.

## What a run does

1. Pulls the latest code, config and data from GitHub (so a fix pushed from anywhere is live next run).
2. Works out what can have changed:
   * **Sunday (match day):** only divisions and cups with games today, plus divisions whose teams have a county cup tie today. Nothing at all if there are no games.
   * **Saturday 08:50 and Monday 07:50 (full refresh):** everything.
   * Goal times are cached by fixture id and only fetched for new or changed results (and, for 14 days, results still missing some goal times). Venues are cached by name.
3. Fetches from Full-Time in a headless browser, running the same `scripts/scrape.js` as before: 2 requests at a time, 0.6 to 1.2 seconds apart, backing off on 429, stopping the whole run on a 403.
4. Checks the data (every division has teams, results and teams haven't dropped, rows look right). If a check fails, nothing is published.
5. If a league's data changed, rebuilds its site and publishes every changed site to gh-pages in **one** commit. On a match day it also republishes every 45 minutes with no change, so the site doesn't wrongly show "Scores may be behind".
6. Saves the data to `data/<league>.json` on main (the single source of truth) and writes `status.json` to the `status` branch for Touchline HQ and the watchdog.

## Set up (Windows)

**Quick way:** open PowerShell as administrator and paste
`Set-ExecutionPolicy Bypass -Scope Process -Force; iwr -UseBasicParsing https://raw.githubusercontent.com/osbornmatthew-lgtm/Touchline/main/runner/windows/setup.ps1 | iex`
It does steps 1 (power settings only) to 6 below, pausing once for you to add the deploy key on GitHub and once before going live.

**Step by step (about 30 minutes):**

**1. The machine.** BIOS: After Power Loss > Power On. Then in an admin PowerShell:
`powercfg /change standby-timeout-ac 0` and `powercfg /change hibernate-timeout-ac 0`.
Settings > Windows Update > Advanced options > Active hours: 08:00 to 20:00. Wired Ethernet.

**2. Software.** Install Git for Windows and Python 3.12 from python.org (tick "Add python.exe to PATH").

**3. A key that can only push to this repo.** In PowerShell:

```
ssh-keygen -t ed25519 -f $HOME\.ssh\touchline_deploy -N '""' -C touchline-runner
Get-Content $HOME\.ssh\touchline_deploy.pub | Set-Clipboard
```

On GitHub: Touchline repo > Settings > Deploy keys > Add deploy key. Paste, title "Home runner", tick **Allow write access**. A deploy key only works on this one repo and doesn't expire.

**4. Get the code.**

```
$ssh = "ssh -i " + ("$HOME/.ssh/touchline_deploy" -replace '\\','/') + " -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
cd C:\
git -c core.sshCommand="$ssh" clone git@github.com:osbornmatthew-lgtm/Touchline.git Touchline
cd C:\Touchline
git config core.sshCommand "$ssh"
py -3.12 -m venv .venv
.venv\Scripts\pip install -r runner\requirements.txt
.venv\Scripts\python -m playwright install chromium
```

Keep this folder for the runner only. Each run resets it to what's on GitHub.

**5. Test, in this order.**

```
.venv\Scripts\python runner\touchline.py probe               does Full-Time answer this connection?
.venv\Scripts\python runner\touchline.py check               config OK, and what a run now would fetch
.venv\Scripts\python runner\touchline.py run --mode full --dry-run    fetch and build, publish nothing
.venv\Scripts\python runner\touchline.py run --mode full      the real thing
```

The dry run puts the built sites in `.runner\out`. Open `index.html` there to look before going live.

**6. Schedule it.** `powershell -ExecutionPolicy Bypass -File runner\windows\install-tasks.ps1`
Sundays every 10 minutes 10:00 to 18:00, Saturday 08:50, Monday 07:50. Runs whether or not you're signed in.

**7. Switch off the old Claude scheduled tasks** for Touchline, so two things don't publish at once.

## Alerts

* **The watchdog** (`.github/workflows/watchdog.yml`) runs on GitHub every 15 minutes on Sundays. If a league has had no good update for 45 minutes between 10:45 and 18:00, it fails and GitHub emails you. Check GitHub > Settings > Notifications > Actions is set to email you for failed workflows. It catches everything: machine off, broadband down, Full-Time blocking, scraper broken.
* **Phone push (optional):** install the ntfy app, subscribe to a topic name only you know, then put that name in `config/leagues.json` under `alerts.ntfy_topic` (the runner tells you the moment a run fails and when it recovers) and as a repo secret `NTFY_TOPIC` (the watchdog).
* **Touchline HQ** shows each league's last update from `status.json`.

## Add an EJA age group

1. In `config/leagues.json`, copy the `bcfa` entry (it shows the "brand" style). Set `id` (e.g. `eja-u15`), `code` (`EJA`), `folder` (`u15`), `age` (`U15`), `season`, `keep_side: false`, the `divisions` (name, fixture group key, division id from the Full-Time URLs), `cups`, `desc`, and the `brand` colours and labels. `assets` can point at a folder of icons; leave it as `""` to use the shared ones.
2. `.venv\Scripts\python runner\touchline.py run --league eja-u15 --mode full --dry-run`, look at `.runner\out\eja-u15\index.html`.
3. `.venv\Scripts\python runner\touchline.py run --league eja-u15 --mode full --force` to publish. It goes live at `/Touchline/u15/` and is included in every run after that.

Under 12s and below are refused by the config check: no published tables for those ages.

## When something goes wrong

* Logs: `.runner\logs\<date>.log` on the machine.
* **Full-Time layout changed** (a check fails): fix `scripts/scrape.js` in a Claude chat, test with `python tests/run_e2e.py`, push to main. The machine picks it up on the next run.
* **Blocked by Full-Time:** the runner stops for that run and alerts. If headless is being refused, set `browser.headless` to `false` and `browser.channel` to `"chrome"` in the config. That needs a signed-in Windows session, so change the tasks to "Run only when user is logged on".
* **Manual fallback:** `scripts/scrape.js` still works pasted into Chrome on Full-Time, as before.

## Tests

`python tests/run_e2e.py` runs the whole thing against a mock Full-Time (`tests/mock_fulltime.py`) built from `tests/fixtures`, with a throwaway copy of the repo. It checks the published pages are identical to the live ones, match-day and full runs, the 45-minute republish, a block and throttling. No real Full-Time or GitHub traffic.
