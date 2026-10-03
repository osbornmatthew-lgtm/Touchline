"""Collect Touchline HQ numbers: GoatCounter usage plus a health check of the public site.

GOATCOUNTER_TOKEN=... python3 hq_collect.py > hq.json
Without a token it still returns the site health part.
"""
import json, os, re, sys, urllib.request, urllib.error
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

GC = 'https://touchline.goatcounter.com/api/v0'
SITE = 'https://touchline-eja.netlify.app'
LAUNCH = date(2026, 10, 1)
TOKEN = os.environ.get('GOATCOUNTER_TOKEN', '').strip()
today = datetime.now(timezone.utc).date()


def get(url, auth=True):
    req = urllib.request.Request(url, headers={'User-Agent': 'touchline-hq', **({'Authorization': 'Bearer ' + TOKEN} if auth else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{e.code} on {url.split("?")[0].replace(GC, "")}') from None


def gc(path, **q):
    qs = '&'.join(f'{k}={v}' for k, v in q.items())
    return json.loads(get(f'{GC}{path}?{qs}'))


out = {'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'errors': []}

# Usage
if TOKEN:
    try:
        rng = dict(start=LAUNCH.isoformat(), end=(today + timedelta(days=1)).isoformat())
        hits, more, exclude = [], True, ''
        while more and len(hits) < 500:
            h = gc('/stats/hits', limit=100, **rng, **({'exclude_paths': exclude} if exclude else {}))
            batch = h.get('hits', [])
            hits += batch
            more = h.get('more') and batch
            exclude = ','.join(str(x['path_id']) for x in hits if 'path_id' in x)
        pages = [{'path': x.get('path', ''), 'title': x.get('title', ''), 'event': bool(x.get('event')), 'n': x.get('count', 0)} for x in hits]
        out['pages'] = sorted(pages, key=lambda p: -p['n'])
        # Visits = app opens (page views); taps on divisions, teams and buttons are events.
        days = defaultdict(int)
        for x in hits:
            if not x.get('event'):
                for st in x.get('stats', []):
                    days[st['day']] += st.get('daily', 0)
        span = [(today - timedelta(days=i)).isoformat() for i in range(27, -1, -1)]
        out['daily'] = [{'d': d, 'n': days.get(d, 0)} for d in span]
        wk = sum(days.get((today - timedelta(days=i)).isoformat(), 0) for i in range(7))
        pwk = sum(days.get((today - timedelta(days=i)).isoformat(), 0) for i in range(7, 14))
        out['totals'] = {'today': days.get(today.isoformat(), 0), 'week': wk, 'prevWeek': pwk,
                         'all': sum(days.values()), 'taps': sum(p['n'] for p in pages if p['event'])}
        div, team, cal = defaultdict(int), defaultdict(int), 0
        for p in pages:
            m = re.match(r'^/?(\w+)/(view|team)/', p['path'])
            if m and m.group(2) == 'view':
                div[p['title'] or p['path']] += p['n']
            elif m:
                team[p['title'] or p['path']] += p['n']
            elif re.search(r'/calendar', p['path']):
                cal += p['n']
        out['divisions'] = [{'name': k, 'n': v} for k, v in sorted(div.items(), key=lambda kv: -kv[1])]
        out['teams'] = [{'name': k, 'n': v} for k, v in sorted(team.items(), key=lambda kv: -kv[1])]
        out['calendar'] = cal
        try:
            sz = gc('/stats/sizes', **rng)
            NAMES = {'phone': 'Phones', 'tablet': 'Tablets', 'desktop': 'Computers', 'desktophd': 'Large screens', 'unknown': 'Unknown'}
            out['devices'] = [{'name': s.get('name') or NAMES.get(s.get('id'), s.get('id')), 'n': s.get('count', 0)} for s in sz.get('stats', []) if s.get('count')]
        except Exception as e:
            out['errors'].append(f'devices: {e}')
    except Exception as e:
        out['errors'].append(f'GoatCounter: {e}')
else:
    out['errors'].append('No GoatCounter token set, so usage numbers are missing.')

# Site health
h = {}
try:
    page = get(SITE + '/?x=' + str(int(datetime.now().timestamp())), auth=False)
    h['siteUp'] = True
    m = re.search(r"DATA\.updated = '([^']*)'", page); h['resultsTo'] = m.group(1) if m else None
    m = re.search(r"DATA\.fetched = '([^']*)'", page); h['fetched'] = m.group(1) if m else None
    m = re.search(r'^const DATA = (.*);$', page, re.M)
    if m:
        D = json.loads(m.group(1))
        h['divisions'] = len(D['divisions'])
        h['teams'] = sum(len(d['teams']) for d in D['divisions'])
        h['results'] = sum(len(d['results']) for d in D['divisions'])
        h['fixtures'] = sum(len(d['fixtures']) for d in D['divisions'])
        h['timedGoals'] = sum(len(r[7]) for d in D['divisions'] for r in d['results'] if len(r) > 7 and r[7])
        h['cupTies'] = sum(len(c['results']) + len(c['fixtures']) for c in D['cups'])
    m = re.search(r'^const SPONSORS = (.*);$', page, re.M)
    if m:
        S = json.loads(m.group(1))
        h['partners'] = [{'team': t, 'names': [p['name'] for p in (v if isinstance(v, list) else [v])]} for t, v in S.items()]
    h['counter'] = 'goatcounter.com/count' in page
    h['offline'] = "serviceWorker.register" in page
except Exception as e:
    h['siteUp'] = False
    out['errors'].append(f'site: {e}')
try:
    ics = get(SITE + '/cal/hashtag-united.ics', auth=False)
    h['calendarFeeds'] = ics.startswith('BEGIN:VCALENDAR')
except Exception as e:
    h['calendarFeeds'] = False
out['health'] = h

# Partner exposure = views of the partnered teams' pages
if 'teams' in out and h.get('partners'):
    tv = {t['name']: t['n'] for t in out['teams']}
    out['partnerViews'] = [{'team': p['team'], 'names': p['names'], 'n': tv.get(p['team'], 0)} for p in h['partners']]

json.dump(out, sys.stdout, separators=(',', ':'))
