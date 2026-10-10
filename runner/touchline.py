#!/usr/bin/env python3
"""Touchline home runner: update the league sites from FA Full-Time with no Claude and no open Chrome.

Run by the home machine's own scheduler (see runner/README.md):

    python runner/touchline.py run                  Saturday and Monday: full refresh. Sunday: match-day check.
    python runner/touchline.py run --mode full      everything, whatever the day
    python runner/touchline.py run --league bcfa --dry-run    fetch and build, publish nothing
    python runner/touchline.py probe                does plain HTTP work from here, and does the headless browser?
    python runner/touchline.py check                check the config and show what a run now would fetch

Each run: pull the latest code and data from GitHub, fetch from Full-Time in a headless browser using the
same scripts/scrape.js as before (only what can have changed), check the data, rebuild a site only if its
data changed, publish all changed sites to gh-pages in one commit, save the data to data/<league>.json on
main, and write status.json to the 'status' branch for Touchline HQ and the watchdog.
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / '.runner'
LDN = ZoneInfo('Europe/London')
FULLTIME = os.environ.get('TOUCHLINE_FULLTIME_URL', 'https://fulltime.thefa.com').rstrip('/')
sys.path.insert(0, str(ROOT / 'scripts'))
from make_league import make_page  # noqa: E402

LOGFILE = None


def log(msg):
    line = f'{datetime.now(LDN):%H:%M:%S} {msg}'
    print(line, flush=True)
    if LOGFILE:
        with open(LOGFILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')


class Blocked(Exception):
    """Full-Time refused us (403 or kept throttling). Stop for this run, don't keep knocking."""


# ---------------------------------------------------------------------------------------------------- config

def load_config():
    cfg = json.loads((ROOT / 'config' / 'leagues.json').read_text(encoding='utf-8'))
    ids, folders = set(), set()
    for L in cfg['leagues']:
        for k in ('id', 'code', 'folder', 'age', 'season', 'divisions', 'cups', 'desc', 'template', 'keep_side'):
            if k not in L:
                raise SystemExit(f'config: league {L.get("id", "?")} is missing "{k}"')
        if L['id'] in ids or L['folder'] in folders:
            raise SystemExit(f'config: id or folder used twice ({L["id"]}, "{L["folder"]}")')
        ids.add(L['id']); folders.add(L['folder'])
        m = re.match(r'U(\d+)$', L['age'])
        if not m:
            raise SystemExit(f'config: {L["id"]} age should look like U16')
        if int(m.group(1)) <= 12:
            raise SystemExit(f'config: {L["id"]} is {L["age"]}. Touchline does not publish tables for Under 12s and below.')
        if L['template'] == 'brand' and 'brand' not in L:
            raise SystemExit(f'config: {L["id"]} needs a "brand" block (colours and labels)')
        if not L['divisions']:
            raise SystemExit(f'config: {L["id"]} has no divisions')
    if sum(1 for L in cfg['leagues'] if L['folder'] == '') > 1:
        raise SystemExit('config: only one league can sit at the root of the site (folder "")')
    return cfg


# ---------------------------------------------------------------------------------------------------- git

def git(*args, cwd=ROOT, check=True, quiet=False):
    r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8')
    if check and r.returncode:
        raise RuntimeError(f'git {args[0]} failed: {(r.stderr or r.stdout).strip().splitlines()[-1:] or r.returncode}')
    return r.stdout.strip()


def self_update():
    """Take the latest code and data from GitHub, so a fix pushed from anywhere goes live on the next run."""
    git('fetch', '-q', 'origin', 'main')
    git('checkout', '-q', 'main')
    git('reset', '-q', '--hard', 'origin/main')


def push_with_retry(cwd, ref, redo=None):
    for attempt in range(2):
        r = subprocess.run(['git', 'push', '-q', 'origin', ref], cwd=cwd, capture_output=True, text=True, encoding='utf-8')
        if r.returncode == 0:
            return
        if attempt == 0 and redo:
            log(f'push refused ({r.stderr.strip().splitlines()[-1:]}), catching up and trying once more')
            redo()
            continue
        raise RuntimeError('push failed: ' + ' '.join(r.stderr.strip().splitlines()[-2:]))


def commit_identity():
    return ['-c', 'user.name=Touchline runner', '-c', 'user.email=touchline-runner@users.noreply.github.com']


# ---------------------------------------------------------------------------------------------------- dates

def season_day(ddmm, now):
    dd, mm = int(ddmm[:2]), int(ddmm[3:5])
    start = now.year if now.month >= 7 else now.year - 1
    return datetime(start if mm >= 7 else start + 1, mm, dd, tzinfo=LDN)


def label_updated(data, now):
    days = [season_day(r[0], now) for d in data['divisions'] for r in d['results'] if r[3] is not None]
    if not days:
        return 'start of season'
    d = max(days)
    return f'{d:%A} {d.day} {d:%B} {d.year}'


def label_fetched(now):
    return f'{now:%A} {now.day} {now:%B}, {now:%H:%M}'


# ---------------------------------------------------------------------------------------------------- data files

def data_path(L):
    return ROOT / 'data' / f'{L["id"]}.json'


def meta_path(L):
    return ROOT / 'data' / f'{L["id"]}.meta.json'


def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def write_json(p, obj, compact=True):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(',', ':'), ensure_ascii=False) if compact else json.dumps(obj, indent=1, ensure_ascii=False)
    Path(p).write_text(text + '\n', encoding='utf-8', newline='')


def seed_from_live(L, cfg):
    """First run for a league: start from the data on the live site, so caches are warm from day one."""
    url = cfg['site_base'] + (L['folder'] + '/' if L['folder'] else '') + f'?x={int(time.time())}'
    try:
        page = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'touchline-runner'}), timeout=30).read().decode('utf-8')
        m = re.search(r'^const DATA = (.*);$', page, re.M)
        return json.loads(m.group(1)) if m else None
    except Exception as e:
        log(f'{L["id"]}: no live data to start from ({e})')
        return None


# ---------------------------------------------------------------------------------------------------- what to fetch

def teams_of(d):
    return {t[0] for t in d['teams']}


def plan_for(L, prev, meta, mode, now, cfg):
    """Decide what this run fetches. Full: everything (goal times and venues still cached). Match day: only
    divisions and cups with games today, plus divisions whose teams have a county cup tie today."""
    full = mode == 'full' or not prev or len(prev.get('divisions', [])) != len(L['divisions']) \
        or [d['name'] for d in prev['divisions']] != [d[0] for d in L['divisions']]
    recheck = cfg['full_refresh' if full else 'match_day']['goal_times_recheck_days']
    events = {}
    for d in (prev or {}).get('divisions', []):
        for r in d['results']:
            if len(r) > 7 and r[6] and r[3] is not None:
                ev = r[7] or []
                incomplete = len(ev) < r[3] + r[4]
                recent = (now - season_day(r[0], now)).days <= recheck
                if incomplete and recent:
                    continue  # goal times may still be going in: look again
                events[str(r[6])] = {'s': f'{r[3]}-{r[4]}', 'e': ev}
    known = list((prev or {}).get('venues', {}).keys())
    if not full:
        known += (meta or {}).get('venue_misses', [])  # nothing found last time: only retry on a full refresh
    p = {'full': full, 'events': events, 'known_venues': known, 'only_divs': None, 'only_cups': None}
    if full:
        return p
    today = now.strftime('%d/%m')
    active = []
    county = next((c for c in prev['cups'] if c.get('county')), {'results': [], 'fixtures': []})
    county_teams = {x for rows in (county['results'], county['fixtures']) for r in rows if r[0] == today
                    for x in ((r[1], r[2]) if rows is county['results'] else (r[2], r[3]))}
    for d in prev['divisions']:
        if any(f[0] == today for f in d['fixtures']) or any(r[0] == today for r in d['results']) or teams_of(d) & county_teams:
            active.append(d['name'])
    cups = [c['name'] for c in prev['cups'] if not c.get('county') and
            (any(f[0] == today for f in c['fixtures']) or any(r[0] == today for r in c['results']))]
    p['only_divs'], p['only_cups'] = active, [c for c in cups if c in {x[0] for x in L['cups']}]
    return p


def games_today(data, now):
    today = now.strftime('%d/%m')
    rows = [r for d in data['divisions'] for r in d['fixtures'] + d['results']]
    rows += [r for c in data['cups'] for r in c['fixtures'] + c['results']]
    return any(r[0] == today for r in rows)


# ---------------------------------------------------------------------------------------------------- merge and check

def key_r(r):
    return (r[0], r[1], r[2])


def key_f(f):
    return (f[0], f[2], f[3])


def ordered_venues(data, pool):
    """Venues in the order a full run finds them (first fixture that mentions each), only those still in use."""
    out = {}
    for f in [f for d in data['divisions'] for f in d['fixtures']] + [f for c in data['cups'] for f in c['fixtures']]:
        if f[4] and f[5] and f[4] in pool and f[4] not in out:
            out[f[4]] = pool[f[4]]
    return out


def merge(L, prev, new, plan):
    venues = {**(prev or {}).get('venues', {}), **new.get('venues', {})}
    if plan['full']:
        data = {'divisions': new['divisions'], 'cups': new['cups']}
    else:
        got = {d['name']: d for d in new['divisions']}
        divisions = [got.get(d['name'], d) for d in prev['divisions']]
        got_c = {c['name']: c for c in new['cups'] if not c.get('county')}
        prev_c = {c['name']: c for c in prev['cups'] if not c.get('county')}
        cups = []
        for name, *_ in L['cups']:
            if name in plan['only_cups']:
                if name in got_c:
                    cups.append(got_c[name])
            elif name in prev_c:
                cups.append(prev_c[name])
        # County cup ties: fresh for teams in the divisions we checked, kept from last time for the rest,
        # put back in the order a full run would give (division by division).
        pc = next((c for c in prev['cups'] if c.get('county')), {'results': [], 'fixtures': []})
        nc = next((c for c in new['cups'] if c.get('county')), {'results': [], 'fixtures': []})
        res, fix = {}, {}
        for d in divisions:
            src = nc if d['name'] in got else pc
            tm = teams_of(d)
            for r in src['results']:
                if (r[1] in tm or r[2] in tm) and key_r(r) not in res:
                    res[key_r(r)] = r
            for f in src['fixtures']:
                if (f[2] in tm or f[3] in tm) and key_f(f) not in fix:
                    fix[key_f(f)] = f
        cups.append({'name': 'County Cups', 'county': True, 'results': list(res.values()), 'fixtures': list(fix.values())})
        data = {'divisions': divisions, 'cups': cups}
    data['venues'] = ordered_venues(data, venues)
    return data


def check(L, data, prev):
    problems = []
    if [d['name'] for d in data['divisions']] != [d[0] for d in L['divisions']]:
        problems.append('divisions do not match the config')
    for d in data['divisions']:
        if not d['teams']:
            problems.append(f'{d["name"]} came back with no teams')
        for r in d['results']:
            if len(r) != 8 or any(not (isinstance(e, list) and len(e) == 3 and isinstance(e[0], int)
                                       and e[1] in ('H', 'A') and e[2] in ('G', 'P', 'O')) for e in r[7]):
                problems.append(f'{d["name"]} has a result in an unexpected shape'); break
        for f in d['fixtures']:
            if len(f) != 7:
                problems.append(f'{d["name"]} has a fixture in an unexpected shape'); break
    if prev:
        before = sum(len(d['results']) for d in prev['divisions'])
        after = sum(len(d['results']) for d in data['divisions'])
        if before >= 10 and after < before * 0.8:
            problems.append(f'league results dropped from {before} to {after}')
        t_before = sum(len(d['teams']) for d in prev['divisions'])
        t_after = sum(len(d['teams']) for d in data['divisions'])
        if t_after < t_before * 0.8:
            problems.append(f'teams dropped from {t_before} to {t_after}')
    return problems


# ---------------------------------------------------------------------------------------------------- Full-Time

RUN_JS = """async ([src, cfg]) => {
  window.__tlcfg = cfg; window.__tlout = null;
  const AF = Object.getPrototypeOf(async function(){}).constructor;
  const summary = await new AF(src.replace(/\\n([^\\n]*)\\s*$/, '\\nreturn $1'))();
  return { summary, out: window.__tlout };
}"""


class FullTime:
    """A headless browser on Full-Time, running scripts/scrape.js inside the page as Chrome did before."""

    def __init__(self, cfg):
        self.cfg = cfg

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        b = self.cfg.get('browser', {})
        headless = b.get('headless', True)
        opts = dict(headless=headless, channel=b.get('channel') or None, args=b.get('args') or [],
                    ignore_default_args=['--enable-automation'], locale='en-GB', timezone_id='Europe/London')
        if headless:  # the headless build announces itself in its user agent, so present a normal one
            opts['user_agent'] = self.cfg['fetch'].get('user_agent') or \
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
        # A profile kept between runs, so once Full-Time's bot check trusts this browser its cookies are reused.
        prof = ROOT / '.runner' / 'chrome-profile'
        prof.mkdir(parents=True, exist_ok=True)
        self.ctx = self.pw.chromium.launch_persistent_context(str(prof), **opts)
        self.ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        return self

    def __exit__(self, *a):
        try:
            self.ctx.close()
        finally:
            self.pw.stop()

    def _status(self, url):
        return self.page.evaluate("async u => (await fetch(u)).status", url)

    def open(self, season, probe_div=None):
        """Load Full-Time like a person would and give its bot check time to finish before fetching."""
        settle = int(self.cfg.get('browser', {}).get('settle_seconds', 6)) * 1000
        r = self.page.goto(f'{FULLTIME}/index.html?selectedSeason={season}', wait_until='load', timeout=60000)
        if r is None or r.status in (403, 429):
            raise Blocked(f'Full-Time answered {r.status if r else "nothing"} on its home page')
        if r.status >= 400:
            raise RuntimeError(f'Full-Time answered {r.status} on its home page')
        self.page.wait_for_timeout(settle)
        if probe_div:
            test = f'/table.html?selectedSeason={season}&selectedDivision={probe_div}'
            for attempt in range(3):
                if self._status(test) == 200:
                    return
                # open a real page as a navigation (not a background fetch), then wait and try again
                self.page.goto(FULLTIME + test, wait_until='load', timeout=60000)
                self.page.wait_for_timeout(settle)
                self.page.goto(f'{FULLTIME}/index.html?selectedSeason={season}', wait_until='load', timeout=60000)
                self.page.wait_for_timeout(settle // 2)
            raise Blocked('Full-Time still refuses background requests after waiting for its bot check')

    def scrape(self, L, plan):
        f = self.cfg['fetch']
        js_cfg = {'S': L['season'], 'DIVS': L['divisions'], 'CUPS': L['cups'], 'AGE': L['age'], 'KEEP_SIDE': L['keep_side'],
                  'ONLY_DIVS': plan['only_divs'], 'ONLY_CUPS': plan['only_cups'], 'EVENTS': plan['events'],
                  'KNOWN_VENUES': plan['known_venues'], 'LIMIT': f.get('concurrency', 2), 'DELAY': f.get('delay_ms', [600, 1200]),
                  'RETRIES': f.get('retries', 2), 'DEADLINE_MS': int(f.get('run_limit_minutes', 10) * 60000), 'NO_DOM': True}
        self.open(L['season'], L['divisions'][0][2] if L['divisions'] else None)
        src = (ROOT / 'scripts' / 'scrape.js').read_text(encoding='utf-8')
        try:
            res = self.page.evaluate(RUN_JS, [src, js_cfg])
        except Exception as e:
            msg = str(e).split('\n')[0]
            if re.search(r'HTTP (403|429)', msg):
                raise Blocked(msg) from None
            raise RuntimeError(msg) from None
        return res['out']['data'], res['out']['meta'], res['summary']


# ---------------------------------------------------------------------------------------------------- build and publish

def build_site(L, data, updated, fetched, cfg, workdir):
    tpl = (ROOT / 'scripts' / 'page.html').read_text(encoding='utf-8')
    page = workdir / f'{L["id"]}' / 'page.html'
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(make_page(L, data, updated, fetched, tpl, cfg['site_base']), encoding='utf-8', newline='')
    r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build.py'), str(page), L['id']], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('build failed: ' + (r.stderr.strip().splitlines() or ['?'])[-1])
    return page.parent / 'touchline-site'


def pages_worktree():
    wt = STATE / 'pages'
    git('fetch', '-q', 'origin', 'gh-pages')
    if not (wt / '.git').exists():
        git('worktree', 'prune')
        git('worktree', 'add', '-q', '--detach', str(wt), 'origin/gh-pages')
    else:
        git('reset', '-q', '--hard', 'origin/gh-pages', cwd=wt)
        git('clean', '-qfdx', cwd=wt)
    return wt


def place_sites(wt, sites, cfg):
    other_folders = {L['folder'] for L in cfg['leagues'] if L['folder']}
    for L, site in sites:
        if L['folder'] == '':
            for item in wt.iterdir():
                if item.name == '.git' or item.name in other_folders:
                    continue
                shutil.rmtree(item) if item.is_dir() else item.unlink()
            shutil.copytree(site, wt, dirs_exist_ok=True)
            (wt / '_headers').unlink(missing_ok=True)
        else:
            dest = wt / L['folder']
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(site, dest)
            for extra in ('_headers', '.nojekyll'):
                (dest / extra).unlink(missing_ok=True)


def publish_pages(sites, cfg, message):
    wt = pages_worktree()
    place_sites(wt, sites, cfg)
    git('add', '-A', cwd=wt)
    if not git('status', '--porcelain', cwd=wt):
        return False

    def redo():
        pages_worktree(); place_sites(wt, sites, cfg); git('add', '-A', cwd=wt)
        git(*commit_identity(), 'commit', '-qm', message, cwd=wt)

    git(*commit_identity(), 'commit', '-qm', message, cwd=wt)
    push_with_retry(wt, 'HEAD:gh-pages', redo)
    return True


def save_data(paths, message):
    git('add', *[str(p) for p in paths])
    if not git('diff', '--cached', '--name-only'):
        return

    def redo():
        git(*commit_identity(), 'pull', '-q', '--rebase', 'origin', 'main')

    git(*commit_identity(), 'commit', '-qm', message)
    push_with_retry(ROOT, 'HEAD:main', redo)


def read_status():
    try:
        git('fetch', '-q', 'origin', 'status')
        return json.loads(git('show', 'origin/status:status.json'))
    except Exception:
        return {}


def publish_status(status):
    """status.json on its own branch, one commit replaced each time, so main's history stays clean and
    GitHub Pages doesn't rebuild every 10 minutes."""
    text = json.dumps(status, indent=1, ensure_ascii=False) + '\n'
    with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8', newline='', suffix='.json') as f:
        f.write(text)
    try:
        blob = git('hash-object', '-w', f.name)
    finally:
        os.unlink(f.name)
    tree = subprocess.run(['git', 'mktree'], cwd=ROOT, input=f'100644 blob {blob}\tstatus.json\n', capture_output=True, text=True, check=True).stdout.strip()
    commit = git(*commit_identity(), 'commit-tree', tree, '-m', f'Status {status["updated"]}')
    git('push', '-q', '-f', 'origin', f'{commit}:refs/heads/status')


def notify(cfg, title, body):
    topic = os.environ.get('TOUCHLINE_NTFY_TOPIC') or cfg.get('alerts', {}).get('ntfy_topic')
    if not topic:
        return
    try:
        req = urllib.request.Request(f'https://ntfy.sh/{topic}', data=body.encode('utf-8'), method='POST',
                                     headers={'Title': title.encode('ascii', 'ignore').decode(), 'Tags': 'soccer'})
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        log(f'could not send the phone alert: {e}')


# ---------------------------------------------------------------------------------------------------- run

def now_ldn():
    fake = os.environ.get('TOUCHLINE_NOW')  # tests only: pretend it is this time
    return datetime.fromisoformat(fake).replace(tzinfo=LDN) if fake else datetime.now(LDN)


def pick_mode(arg, now):
    if arg != 'auto':
        return arg
    return 'full' if now.weekday() in (5, 0) else 'matchday'  # Saturday and Monday mornings: full refresh


def acquire_lock():
    STATE.mkdir(exist_ok=True)
    lock = STATE / 'run.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        return lock
    except FileExistsError:
        if time.time() - lock.stat().st_mtime > 20 * 60:
            lock.unlink(missing_ok=True)
            return acquire_lock()
        return None


def cmd_run(a):
    global LOGFILE
    lock = acquire_lock()
    if not lock:
        print('Another run is still going, so this one is skipped.')
        return 0
    try:
        (STATE / 'logs').mkdir(parents=True, exist_ok=True)
        LOGFILE = STATE / 'logs' / f'{datetime.now(LDN):%Y-%m-%d}.log'
        for old in sorted((STATE / 'logs').glob('*.log'))[:-21]:
            old.unlink(missing_ok=True)
        return run(a)
    finally:
        lock.unlink(missing_ok=True)


def run(a):
    t0 = time.time()
    if not a.no_pull and not a.dry_run:
        try:
            self_update()
        except Exception as e:
            log(f'could not pull the latest from GitHub ({e}); carrying on with what is here')
    cfg = load_config()
    now = now_ldn()
    mode = pick_mode(a.mode, now)
    leagues = [L for L in cfg['leagues'] if L.get('enabled', True) and (not a.league or L['id'] == a.league)]
    if a.league and not leagues:
        raise SystemExit(f'no enabled league called {a.league}')
    prev_status = {} if a.dry_run else read_status()
    prev_lg = prev_status.get('leagues', {})
    status = {'updated': now.isoformat(timespec='seconds'), 'host': socket.gethostname(), 'mode': mode,
              'version': git('rev-parse', '--short', 'HEAD', check=False), 'ok': True, 'leagues': dict(prev_lg)}
    log(f'Touchline run, {mode}, leagues: {", ".join(L["id"] for L in leagues)}')

    work = Path(tempfile.mkdtemp(prefix='touchline-'))
    to_publish, data_files, blocked = [], [], None
    try:
        browser = None
        for L in leagues:
            s = dict(prev_lg.get(L['id'], {}))
            s.update({'ok': False, 'error': None, 'note': None, 'changed': False, 'published': False, 'requests': 0})
            status['leagues'][L['id']] = s
            lt = time.time()
            try:
                if blocked:
                    raise Blocked(f'skipped: {blocked}')
                prev = read_json(data_path(L)) or seed_from_live(L, cfg)
                meta = read_json(meta_path(L), {})
                plan = plan_for(L, prev, meta, mode, now, cfg)
                s['mode'] = 'full' if plan['full'] else 'matchday'
                s['checked'] = 'all' if plan['full'] else plan['only_divs'] + plan['only_cups']
                if not plan['full'] and not plan['only_divs'] and not plan['only_cups']:
                    s.update(ok=True, note='no games today', last_success=now.isoformat(timespec='seconds'))
                    log(f'{L["id"]}: no games today, nothing to check')
                    continue
                if browser is None:
                    browser = FullTime(cfg).__enter__()
                new, smeta, summary = browser.scrape(L, plan)
                s['requests'] = smeta.get('requests', 0)
                log(f'{L["id"]}: {summary} ({smeta.get("ms", 0) / 1000:.0f}s, {smeta.get("eventsReused", 0)} goal-time pages skipped)')
                data = merge(L, prev, new, plan)
                problems = check(L, data, prev)
                if problems:
                    raise RuntimeError('data failed checks, nothing published: ' + '; '.join(problems))
                changed = data != {k: prev[k] for k in ('divisions', 'cups', 'venues') if k in prev} if prev else True
                last_pub = meta.get('published_at')
                stale = not last_pub or now - datetime.fromisoformat(last_pub) >= timedelta(minutes=cfg['match_day']['heartbeat_minutes'])
                heartbeat = not changed and s['mode'] == 'matchday' and games_today(data, now) and stale
                misses = sorted(set(smeta.get('venueMisses', [])) | (set(meta.get('venue_misses', [])) if not plan['full'] else set()))
                meta_new = {**meta, 'venue_misses': misses, 'last_check': now.isoformat(timespec='seconds')}
                if plan['full']:
                    meta_new['last_full'] = meta_new['last_check']
                if changed or heartbeat or a.force:
                    updated, fetched = label_updated(data, now), label_fetched(now)
                    site = build_site(L, data, updated, fetched, cfg, work)
                    to_publish.append((L, site))
                    meta_new.update(updated=updated, fetched=fetched, published_at=now.isoformat(timespec='seconds'))
                    s['note'] = 'changed' if changed else ('forced' if a.force else 'no change; republished so the site shows it was checked')
                    if changed:
                        s['last_change'] = now.isoformat(timespec='seconds')
                else:
                    s['note'] = 'no change'
                s['changed'] = changed
                if not a.dry_run:
                    write_json(data_path(L), data)
                    write_json(meta_path(L), meta_new, compact=False)
                    data_files += [data_path(L), meta_path(L)]
                s.update(ok=True, results_to=label_updated(data, now))
                s['last_success'] = now.isoformat(timespec='seconds')
            except Blocked as e:
                blocked = blocked or str(e)
                s['error'] = f'Full-Time blocked or throttled us: {e}'
                log(f'{L["id"]}: {s["error"]}')
            except Exception as e:
                s['error'] = str(e)
                log(f'{L["id"]}: FAILED: {e}')
                if a.verbose:
                    traceback.print_exc()
            finally:
                s['duration_s'] = round(time.time() - lt, 1)
        if browser:
            browser.__exit__(None, None, None)

        if to_publish:
            when = f'{now:%a %d %b %H:%M}'
            if a.dry_run:
                out = STATE / 'out'
                shutil.rmtree(out, ignore_errors=True)
                for L, site in to_publish:
                    shutil.copytree(site, out / (L['id']))
                log(f'dry run: built {", ".join(L["id"] for L, _ in to_publish)} into {out}, published nothing')
            else:
                try:
                    publish_pages(to_publish, cfg, f'Results update {when} ({", ".join(L["id"] for L, _ in to_publish)})')
                    for L, _ in to_publish:
                        status['leagues'][L['id']].update(published=True, last_publish=now.isoformat(timespec='seconds'))
                    log('published ' + ', '.join(L['id'] for L, _ in to_publish))
                except Exception as e:
                    for L, _ in to_publish:
                        st = status['leagues'][L['id']]
                        st.update(ok=False, error=f'publish failed: {e}', last_success=prev_lg.get(L['id'], {}).get('last_success'))
                    data_files = [p for p in data_files if not any(p.name.startswith(L['id'] + '.') for L, _ in to_publish)]
                    log(f'publish FAILED: {e}')
        if data_files and not a.dry_run:
            try:
                save_data(data_files, f'Data {now:%a %d %b %H:%M}')
            except Exception as e:
                log(f'could not save the data to GitHub: {e}')
                status['data_save_error'] = str(e)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    run_lg = [status['leagues'][L['id']] for L in leagues]
    status['ok'] = all(x['ok'] for x in run_lg)
    status['duration_s'] = round(time.time() - t0, 1)
    errors = [f'{L["id"]}: {status["leagues"][L["id"]]["error"]}' for L in leagues if status['leagues'][L['id']].get('error')]
    status['errors'] = errors
    if a.dry_run:
        print(json.dumps(status, indent=1))
        return 0 if status['ok'] else 1
    try:
        publish_status(status)
    except Exception as e:
        log(f'could not publish status.json: {e}')
    was_ok = prev_status.get('ok', True)
    if not status['ok'] and was_ok:
        notify(cfg, 'Touchline update failed', '\n'.join(errors) or 'See the runner log.')
    elif status['ok'] and not was_ok:
        notify(cfg, 'Touchline is updating again', 'The last run worked.')
    log(f'done in {status["duration_s"]}s, {"ok" if status["ok"] else "FAILED"}')
    return 0 if status['ok'] else 1


# ---------------------------------------------------------------------------------------------------- probe and check

def cmd_probe(a):
    cfg = load_config()
    L = next(L for L in cfg['leagues'] if L.get('enabled', True))
    div = L['divisions'][0][2]
    url = f'{FULLTIME}/table.html?selectedSeason={L["season"]}&selectedDivision={div}'
    print('1. Plain HTTP request (no browser) from this connection')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode('utf-8', 'replace')
            print(f'   {r.status}, {len(body)} bytes, league table found: {"<table" in body}')
    except urllib.error.HTTPError as e:
        print(f'   refused: HTTP {e.code}')
    except Exception as e:
        print(f'   failed: {e}')
    print('2. Browser (what the runner uses: ' + ('headless' if cfg.get('browser', {}).get('headless', True) else 'Chrome window') + ')')
    try:
        with FullTime(cfg) as ft:
            try:
                ft.open(L['season'], div)
            except Blocked as e:
                print(f'   {e}')
            n = ft.page.evaluate("async u => { const r = await fetch(u); return [r.status, (await r.text()).length]; }",
                                 f'/table.html?selectedSeason={L["season"]}&selectedDivision={div}')
            print(f'   home page OK, league table: HTTP {n[0]}, {n[1]} bytes')
    except Exception as e:
        print(f'   failed: {str(e).splitlines()[0]}')
    return 0


def cmd_check(a):
    cfg = load_config()
    now = now_ldn()
    mode = pick_mode(a.mode, now)
    for L in cfg['leagues']:
        if not L.get('enabled', True):
            print(f'{L["id"]}: switched off'); continue
        prev = read_json(data_path(L))
        p = plan_for(L, prev, read_json(meta_path(L), {}), mode, now, cfg)
        what = 'everything' if p['full'] else (', '.join(p['only_divs'] + p['only_cups']) or 'nothing (no games today)')
        print(f'{L["id"]} ({L["age"]}, /{L["folder"]}): {mode} run would fetch {what}; '
              f'{len(p["events"])} goal-time pages cached, {len(p["known_venues"])} venues known'
              + ('' if prev else '; no saved data yet, the first run starts from the live site'))
    print('config OK')
    return 0


def main():
    ap = argparse.ArgumentParser(description='Touchline home runner')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--mode', choices=['auto', 'matchday', 'full'], default='auto')
    r.add_argument('--league')
    r.add_argument('--dry-run', action='store_true', help='fetch and build, publish nothing')
    r.add_argument('--force', action='store_true', help='publish even if nothing changed')
    r.add_argument('--no-pull', action='store_true', help="don't update from GitHub first")
    r.add_argument('-v', '--verbose', action='store_true')
    sub.add_parser('probe')
    c = sub.add_parser('check')
    c.add_argument('--mode', choices=['auto', 'matchday', 'full'], default='auto')
    a = ap.parse_args()
    sys.exit({'run': cmd_run, 'probe': cmd_probe, 'check': cmd_check}[a.cmd](a))


if __name__ == '__main__':
    main()
