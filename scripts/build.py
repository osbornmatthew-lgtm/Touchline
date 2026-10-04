import json, zipfile, os, sys, re, hashlib
from datetime import datetime, timedelta, timezone

src_path = sys.argv[1]
# GoatCounter site code (cookie-free visit counts). Empty = no counting.
GOATCOUNTER = 'touchline'
# League: python3 build.py <page.html> [eja|bcfa]
LEAGUES = {
    'eja': {'code': 'EJA', 'desc': 'EJA Under 16 league tables, results, fixtures and stats.', 'site': 'https://osbornmatthew-lgtm.github.io/Touchline/', 'assets': ''},
    'bcfa': {'code': 'BCFA', 'desc': 'BCFA Youth League Under 13 Division 3 tables, results, fixtures and stats.', 'site': 'https://osbornmatthew-lgtm.github.io/touchline-bcfa/', 'assets': 'bcfa/'},
}
LEAGUE = sys.argv[2] if len(sys.argv) > 2 else 'eja'  # also the prefix so several league sites can share one counter
LG = LEAGUES[LEAGUE]
NAME = 'Touchline ' + LG['code']
out = os.path.join(os.path.dirname(src_path), 'touchline-site')
os.makedirs(out, exist_ok=True)
src = open(src_path).read()
head = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="%DESC%">
<meta property="og:title" content="%NAME%">
<meta property="og:description" content="%DESC%">
<meta property="og:image" content="%SITE%og-image.png">
<meta name="theme-color" content="#0E1217">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="%NAME%">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="manifest" href="manifest.json">
<script>if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('sw.js'));</script>
%GC%<style>body{margin:0}[hidden]{display:none!important}:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);background:#0E1217}</style>
"""
head = head.replace('%DESC%', LG['desc']).replace('%NAME%', NAME).replace('%SITE%', LG['site'])
body = src.replace('<title>Touchline U16</title>', f'<title>{NAME}</title>', 1).replace('<title>Touchline EJA</title>', f'<title>{NAME}</title>', 1)
i = body.index('<header class="top">')
head = head.replace('%GC%', f'<script>window.goatcounter = {{ path: p => "/{LEAGUE}" + p }};</script>\n<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>\n' if GOATCOUNTER else '')
open(os.path.join(out, 'index.html'), 'w').write(head + body[:i] + '</head>\n<body>\n' + body[i:] + '\n</body>\n</html>\n')
# Brand icons from the repo's assets folder (next to this script's repo, or fetched from GitHub)
import urllib.request
ASSETS = 'https://raw.githubusercontent.com/osbornmatthew-lgtm/Touchline/main/assets/'
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', LG['assets'])
ASSETS += LG['assets']
for src_name, name in [('app-icon-512.png', 'icon-512.png'), ('app-icon-192.png', 'icon-192.png'), ('app-icon-180.png', 'apple-touch-icon.png'), ('favicon-32.png', 'favicon-32.png'), ('app-icon-1024.png', 'og-image.png')]:
    local = os.path.join(here, src_name)
    dest = os.path.join(out, name)
    if os.path.exists(local):
        open(dest, 'wb').write(open(local, 'rb').read())
    else:
        urllib.request.urlretrieve(ASSETS + src_name, dest)
json.dump({"name": NAME, "short_name": NAME, "start_url": "./", "display": "standalone", "background_color": "#0E1217", "theme_color": "#0E1217", "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}, open(os.path.join(out, 'manifest.json'), 'w'))

# Offline: network first, fall back to the last copy after 3.5s or with no signal.
open(os.path.join(out, 'sw.js'), 'w').write('''const C = 'touchline-' + '''+repr(LEAGUE)+''' + '-v3';
self.addEventListener('install', e => { self.skipWaiting(); e.waitUntil(caches.open(C).then(c => c.addAll(['./', 'manifest.json', 'icon-192.png', 'apple-touch-icon.png']))); });
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin || u.pathname.includes('/cal/')) return;
  const fromCache = () => caches.match(r, { ignoreSearch: true }).then(m => m || caches.match('./'));
  e.respondWith(new Promise(resolve => {
    let done = false; const finish = x => { if (!done && x) { done = true; resolve(x); } };
    const t = setTimeout(() => fromCache().then(finish), 3500);
    fetch(r).then(res => { clearTimeout(t); if (res.ok) { const cp = res.clone(); caches.open(C).then(c => c.put(r, cp)); } if (!done) { done = true; resolve(res); } })
      .catch(() => { clearTimeout(t); fromCache().then(m => { if (!done) { done = true; resolve(m || Response.error()); } }); });
  }));
});
''')
open(os.path.join(out, '.nojekyll'), 'w').write('')
open(os.path.join(out, '_headers'), 'w').write('''/*
  Access-Control-Allow-Origin: https://touchline-hq.netlify.app
/cal/*
  Content-Type: text/calendar; charset=utf-8
  Cache-Control: public, max-age=3600
/sw.js
  Cache-Control: no-cache
''')

# Calendar feed per team: league and cup fixtures not yet played.
DATA = json.loads(re.search(r'^const DATA = (.*);$', src, re.M).group(1))
vm = re.search(r'^const VENUES = (.*);$', src, re.M)
VENUES = json.loads(vm.group(1)) if vm else {}
now = datetime.now(timezone.utc)
start_year = now.year if now.month >= 7 else now.year - 1
def esc(t): return str(t).replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')
def fold(line):
    b = line.encode('utf-8'); parts = []
    while len(b) > 74:
        cut = 74
        while (b[cut] & 0xC0) == 0x80: cut -= 1
        parts.append(b[:cut].decode()); b = b[cut:]
    parts.append(b.decode())
    return '\r\n '.join(parts)
slug = lambda n: re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', n.lower()))
fx = []
for d in DATA['divisions']:
    fx += [(f, d['name'] + ' league') for f in d['fixtures']]
for c in DATA['cups']:
    fx += [(f, (f[7] if c.get('county') and len(f) > 7 else c['name'])) for f in c['fixtures']]
teams = sorted({t[0] for d in DATA['divisions'] for t in d['teams']})
os.makedirs(os.path.join(out, 'cal'), exist_ok=True)
stamp = now.strftime('%Y%m%dT%H%M%SZ')
TZ = ['BEGIN:VTIMEZONE', 'TZID:Europe/London', 'BEGIN:DAYLIGHT', 'TZOFFSETFROM:+0000', 'TZOFFSETTO:+0100', 'TZNAME:BST', 'DTSTART:19700329T010000', 'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU', 'END:DAYLIGHT', 'BEGIN:STANDARD', 'TZOFFSETFROM:+0100', 'TZOFFSETTO:+0000', 'TZNAME:GMT', 'DTSTART:19701025T020000', 'RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU', 'END:STANDARD', 'END:VTIMEZONE']
for team in teams:
    L = ['BEGIN:VCALENDAR', 'VERSION:2.0', f'PRODID:-//{NAME}//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
         'X-WR-CALNAME:' + esc(team + ' (Touchline)'), 'X-WR-TIMEZONE:Europe/London', 'REFRESH-INTERVAL;VALUE=DURATION:PT6H', 'X-PUBLISHED-TTL:PT6H'] + TZ
    for f, comp in fx:
        if team not in (f[2], f[3]) or f[6]: continue
        dd, mm = int(f[0][:2]), int(f[0][3:5])
        day = datetime(start_year + (1 if mm < 7 else 0), mm, dd)
        uid = (str(f[5]) if f[5] else hashlib.md5((f[0] + f[2] + f[3]).encode()).hexdigest()) + '@touchline-' + LEAGUE
        L += ['BEGIN:VEVENT', 'UID:' + uid, 'DTSTAMP:' + stamp, 'SUMMARY:' + esc(f'{f[2]} v {f[3]}' + ('' if comp.endswith(' league') else f' ({comp})'))]
        if f[1]:
            h, m = map(int, f[1].split(':')); st = day.replace(hour=h, minute=m)
            L += ['DTSTART;TZID=Europe/London:' + st.strftime('%Y%m%dT%H%M%S'), 'DTEND;TZID=Europe/London:' + (st + timedelta(minutes=100)).strftime('%Y%m%dT%H%M%S')]
        else:
            L += ['DTSTART;VALUE=DATE:' + day.strftime('%Y%m%d'), 'DTEND;VALUE=DATE:' + (day + timedelta(days=1)).strftime('%Y%m%d')]
        if f[4]: L.append('LOCATION:' + esc(VENUES.get(f[4], {}).get('q') or (f[4] + ', ' + DATA.get('venues', {}).get(f[4], {})['a'] if DATA.get('venues', {}).get(f[4], {}).get('a') else f[4])))
        L.append('DESCRIPTION:' + esc(comp + '.' + ('' if f[1] else ' Kick-off time not published yet.') + ' Check FA Full-Time for late changes.'))
        if f[5]: L.append('URL:https://fulltime.thefa.com/displayFixture.html?id=' + str(f[5]))
        L.append('END:VEVENT')
    L.append('END:VCALENDAR')
    open(os.path.join(out, 'cal', slug(team) + '.ics'), 'w', newline='').write('\r\n'.join(fold(x) for x in L) + '\r\n')

z = os.path.join(os.path.dirname(src_path), 'touchline-site.zip')
with zipfile.ZipFile(z, 'w') as zf:
    for root, _, files in os.walk(out):
        for n in files:
            fp_ = os.path.join(root, n); zf.write(fp_, os.path.relpath(fp_, out))
print(z)
