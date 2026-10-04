"""A fake FA Full-Time for testing the scraper without touching the real site.

It rebuilds Full-Time style pages (fixtures, results, tables, match pages) from a Touchline
DATA object, using the same page structure scrape.js reads. Feed it the DATA from a live
Touchline page and the scraper should get the same data back.

    python tests/mock_fulltime.py eja:tests/fixtures/eja.json bcfa:tests/fixtures/bcfa.json [--port 8765]

Failure tests: GET /__reset?fail=0.2 (random 429s) or /__reset?block=1 (every request 403); /__hits counts requests.
"""
import argparse
import html
import json
import random
import sys
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

E = html.escape


class Mock:
    def __init__(self, data, league, season, divs, cups, age, side_suffix):
        self.data, self.season, self.age = data, season, age
        self.divs, self.cups = divs, cups            # divs: [[name, key, id]], cups: [[label, option text]]
        self.raw = lambda n: f'{n} {side_suffix}'     # how Full-Time names a side
        # Fixture and result ids, so match pages can carry events and venue details
        self.events, self.venue_of = {}, {}
        for d in data['divisions']:
            for r in d['results']:
                if len(r) > 6 and r[6]:
                    self.events[r[6]] = (r[1], r[2], r[7] if len(r) > 7 else [])
            for f in d['fixtures']:
                if f[5] and f[4]:
                    self.venue_of.setdefault(f[5], f[4])
        for c in data['cups']:
            for f in c['fixtures']:
                if f[5] and f[4]:
                    self.venue_of.setdefault(f[5], f[4])
        self.team_div = {t[0]: d['name'] for d in data['divisions'] for t in d['teams']}

    # ---- rows -------------------------------------------------------------------------
    def fx_row(self, f, typ='L', comp=None):
        dt = f'{f[0]}/26' + (f' {f[1]}' if f[1] else '')
        link = f'<a href="/displayFixture.html?id={f[5]}">v</a>' if f[5] else ''
        ven = E(f[4]) if f[4] else ''
        return (f'<tr><td>{E(typ if comp is None else "CC " + comp)}</td><td>{dt}</td><td>{E(self.raw(f[2]))}</td>'
                f'<td></td><td>{link}</td><td></td><td>{E(self.raw(f[3]))}</td><td>{ven}</td><td></td><td>{E(f[6] or "")}</td></tr>')

    def rs_row(self, r, typ='L', comp=None):
        score = f'{r[3]} - {r[4]}' if r[3] is not None else 'P - P'
        rid = r[6] if len(r) > 6 and isinstance(r[6], int) else None
        link = f'<a href="/displayFixture.html?id={rid}">{score}</a>' if rid else score
        note = f'({E(r[5])})' if r[5] else ''
        return (f'<div><div class="type-col">{E(typ if comp is None else "CC " + comp)}</div><div class="datetime-col">{r[0]}/26 10:00</div>'
                f'<div class="home-team-col"><div class="team-name">{E(self.raw(r[1]))}</div></div>'
                f'<div class="score-col">{link}</div>'
                f'<div class="road-team-col"><div class="team-name">{E(self.raw(r[2]))}</div></div>'
                f'<div class="additional-scores-col">{note}</div></div>')

    def page(self, body):
        return f'<!doctype html><html><head><title>Full-Time</title></head><body>{body}</body></html>'

    def county(self):
        return next((c for c in self.data['cups'] if c.get('county')), {'results': [], 'fixtures': []})

    def div_by_key(self, key):
        for name, k, _ in self.divs:
            if k == key:
                return next(d for d in self.data['divisions'] if d['name'] == name)

    # ---- pages ------------------------------------------------------------------------
    def fixtures(self, q):
        key, opt = q.get('selectedFixtureGroupKey'), q.get('selectedRelatedFixtureOption', '1')
        if not key:
            opts = [f'<option value="{k}">{E(n)}</option>' for n, k, _ in self.divs]
            opts += [f'<option value="cup{i}">{E(text)}</option>' for i, (_, text) in enumerate(self.cups)]
            return self.page(f'<select name="selectedFixtureGroupKey">{"".join(opts)}</select>')
        rows = []
        d = self.div_by_key(key)
        if d is not None:
            rows = [self.fx_row(f) for f in d['fixtures']]
            if opt == '3':
                teams = {t[0] for t in d['teams']}
                rows += [self.fx_row(f[:7], comp=f[7]) for f in self.county()['fixtures'] if f[2] in teams or f[3] in teams]
        elif key.startswith('cup'):
            label = self.cups[int(key[3:])][0]
            cup = next((c for c in self.data['cups'] if c['name'] == label), {'fixtures': []})
            rows = [self.fx_row(f) for f in cup['fixtures']]
        return self.page(f'<table><thead><tr><th>Type</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')

    def results(self, q):
        key, opt = q.get('selectedFixtureGroupKey'), q.get('selectedRelatedFixtureOption', '1')
        rows = []
        d = self.div_by_key(key)
        if d is not None:
            rows = [self.rs_row(r) for r in d['results']]
            if opt == '3':
                teams = {t[0] for t in d['teams']}
                rows += [self.rs_row(r[:6], comp=r[6]) for r in self.county()['results'] if r[1] in teams or r[2] in teams]
        elif key and key.startswith('cup'):
            label = self.cups[int(key[3:])][0]
            cup = next((c for c in self.data['cups'] if c['name'] == label), {'results': []})
            rows = [self.rs_row(r) for r in cup['results']]
        return self.page(f'<div class="results"><div class="thead"></div><div class="tbody">{"".join(rows)}</div></div>')

    def table(self, q):
        div = int(q.get('selectedDivision', 0))
        name = next((n for n, _, i in self.divs if i == div), None)
        d = next((x for x in self.data['divisions'] if x['name'] == name), None)
        rows = ''
        if d:
            for i, t in enumerate(d['teams'], 1):
                n, p, w, dr, l, gf, ga, pts = t
                rows += (f'<tr><td>{i}</td><td>{E(self.raw(n))}</td><td>{p}</td><td>{w}</td><td>{dr}</td><td>{l}</td>'
                         f'<td>{gf}</td><td>{ga}</td><td>{gf - ga}</td><td>{pts}</td></tr>')
        return self.page(f'<table><tr><td>key</td></tr></table><table><thead><tr><th>Pos</th></tr></thead><tbody>{rows}</tbody></table>')

    def match(self, q):
        fid = int(q.get('id', 0))
        body = '<h1>Match</h1>'
        if fid in self.events:
            h, a, ev = self.events[fid]
            stat = {'G': 'Goal', 'P': 'Penalty', 'O': 'Own Goal'}
            rows = ''.join(f'<tr><td>{m}</td><td>{E(self.raw(h if s == "H" else a))}</td><td>{stat[k]}</td></tr>' for m, s, k in ev)
            body += f'<table>\n<thead><tr>\n<th>Time</th>\n<th>Team</th>\n<th>Stat</th>\n</tr></thead>\n<tbody>{rows}</tbody>\n</table>'
        v = self.venue_of.get(fid)
        info = self.data.get('venues', {}).get(v) if v else None
        if info:
            if info.get('a'):
                body += f'<address>{E(info["a"])}</address>'
            if info.get('ll'):
                body += f'<a href="https://maps.google.com/?ll={info["ll"]}">Map</a>'
            if info.get('p'):
                body += f'<p>Car park: {E(info["p"])}</p>'
        return self.page(body)


def serve(mocks, port):
    """Serve one or more mock leagues on one port, routed by season id (match pages by fixture id)."""
    mocks = mocks if isinstance(mocks, list) else [mocks]
    by_season = {m.season: m for m in mocks}
    hits, ctl = Counter(), {'block': False, 'fail': 0.0}
    lock = threading.Lock()

    def pick(q):
        if 'selectedSeason' in q:
            return by_season.get(q['selectedSeason'], mocks[0])
        fid = int(q.get('id', 0) or 0)
        return next((m for m in mocks if fid in m.events or fid in m.venue_of), mocks[0])

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if u.path == '/__hits':
                return self.send(200, json.dumps(hits), 'application/json')
            if u.path == '/__reset':
                with lock:
                    hits.clear()
                ctl['block'] = q.get('block') == '1'
                ctl['fail'] = float(q.get('fail', 0))
                return self.send(200, 'ok')
            with lock:
                hits[u.path] += 1
            if ctl['block']:
                return self.send(403, 'Forbidden')
            if u.path != '/index.html' and random.random() < ctl['fail']:
                return self.send(429, 'Too many', extra={'Retry-After': '1'})
            m = pick(q)
            route = {'/fixtures.html': m.fixtures, '/results.html': m.results, '/table.html': m.table,
                     '/displayFixture.html': m.match, '/index.html': lambda q: m.page('<p>Full-Time</p>')}.get(u.path)
            if not route:
                return self.send(404, 'nope')
            self.send(200, route(q))

        def send(self, code, body, ctype='text/html; charset=utf-8', extra=None):
            b = body.encode()
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(b)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(b)

    srv = ThreadingHTTPServer(('127.0.0.1', port), H)
    srv.hits, srv.ctl = hits, ctl
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


EJA = dict(season='817991894', age='U16', side_suffix='U16',
           divs=[['U16 Black', '1_626466325', 71055166], ['U16 Blue', '1_940550859', 833400234],
                 ['U16 Brown', '1_540512685', 362745292], ['U16 Green', '1_467206401', 610727353],
                 ['U16 Purple', '1_706654984', 786917750], ['U16 Red', '1_882985552', 209907016],
                 ['U16 Yellow', '1_132116272', 66673950]],
           cups=[['League Cup', 'League Cup U16'], ['RT Litho Cup', 'RT Litho Cup U16']])
BCFA = dict(season='486141579', age='U13', side_suffix='U13', divs=[['Division 3', '1_420434328', 80469024]], cups=[])


def make(data, league):
    return Mock(data, league, **(EJA if league == 'eja' else BCFA))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('data', nargs='+', help='one or more league:data.json, e.g. eja:tests/fixtures/eja.json')
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    serve([make(json.load(open(p, encoding='utf-8')), lg) for lg, p in (x.split(':', 1) for x in a.data)], a.port)
    print(f'mock Full-Time on http://127.0.0.1:{a.port}', file=sys.stderr)
    threading.Event().wait()
