"""Pull EJA Under 16 tables, results and fixtures from FA Full-Time and rebuild site/index.html."""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = 'https://fulltime.thefa.com'
SEASON = '817991894'
DIVS = [
    ('U16 Black', '1_626466325', 71055166), ('U16 Blue', '1_940550859', 833400234),
    ('U16 Brown', '1_540512685', 362745292), ('U16 Green', '1_467206401', 610727353),
    ('U16 Purple', '1_706654984', 786917750), ('U16 Red', '1_882985552', 209907016),
    ('U16 Yellow', '1_132116272', 66673950),
]
ROOT = Path(__file__).resolve().parent.parent

session = requests.Session()
session.headers['User-Agent'] = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                 '(KHTML, like Gecko) Chrome/128.0 Safari/537.36')


def get(path):
    r = session.get(BASE + path, timeout=30)
    r.raise_for_status()
    time.sleep(1)
    return BeautifulSoup(r.text, 'html.parser')


def txt(el):
    return re.sub(r'\s+', ' ', el.get_text(' ')).strip() if el else ''


def clean(n):
    s = re.sub(r'\s+U1[0-9]\b.*$', '', n)
    s = re.sub(r'\s*\((Youth|Ltd|Youth Development)\)', '', s).strip()
    while True:
        p = s
        s = re.sub(r'\s+(Youth|Y|FC|F\.C\.?|Community|Academy)$', '', s).strip()
        if s == p:
            return s


def tc(v):
    v = re.sub(r'\b([a-z])', lambda m: m.group(1).upper(), v.lower())
    for a, b in [(r'\bFc\b', 'FC'), (r'\bAnd\b', 'and'), (r'\bFdc\b', 'FDC'), (r'\bFa\b', 'FA'), (r"'S\b", "'s")]:
        v = re.sub(a, b, v)
    return v


def venue(v):
    return None if (not v or re.search(r'\bU1[0-9]\b|#\d', v)) else tc(v)


def results(key, opt):
    soup = get(f'/results.html?selectedSeason={SEASON}&selectedFixtureGroupKey={key}'
               f'&selectedRelatedFixtureOption={opt}&itemsPerPage=100')
    out = []
    for r in soup.select('.tbody > div'):
        h = txt(r.select_one('.home-team-col .team-name'))
        a = txt(r.select_one('.road-team-col .team-name'))
        if not h and not a:
            continue
        m = re.match(r'^(\d+)\s*-\s*(\d+)', txt(r.select_one('.score-col')))
        note = re.sub(r'^\(|\)$', '', txt(r.select_one('.additional-scores-col')))
        out.append({'type': txt(r.select_one('.type-col')), 'raw': [h, a],
                    'row': [txt(r.select_one('.datetime-col'))[:5], clean(h), clean(a),
                            int(m.group(1)) if m else None, int(m.group(2)) if m else None, note]})
    return out


def fixtures(key, opt):
    soup = get(f'/fixtures.html?selectedSeason={SEASON}&selectedFixtureGroupKey={key}'
               f'&selectedRelatedFixtureOption={opt}&itemsPerPage=100')
    out = []
    for r in soup.select('table tbody tr'):
        c = r.find_all(['td', 'th'], recursive=False)
        if len(c) < 9:
            continue
        a = r.find('a', href=True)
        m = re.search(r'id=(\d+)', a['href']) if a else None
        dt = txt(c[1])
        ko = dt[9:14]
        out.append({'type': txt(c[0]), 'raw': [txt(c[2]), txt(c[6])],
                    'row': [dt[:5], None if (not ko or ko == '00:00') else ko, clean(txt(c[2])), clean(txt(c[6])),
                            venue(txt(c[7])), int(m.group(1)) if m else None, txt(c[9]) if len(c) > 9 else '']})
    return out


def scrape():
    opts = [(o.get('value', ''), o.get_text(strip=True))
            for o in get(f'/fixtures.html?selectedSeason={SEASON}').select('select[name=selectedFixtureGroupKey] option')]
    key_of = lambda rx: next((v for v, t in opts if re.search(rx, t, re.I)), None)
    data = {'divisions': [], 'cups': []}
    cc_r, cc_f = {}, {}
    for name, key, div in DIVS:
        tables = get(f'/table.html?selectedSeason={SEASON}&selectedDivision={div}').select('table')
        teams = []
        for tr in tables[-1].select('tbody tr'):
            v = [x for x in (c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'], recursive=False)) if x != '']
            n = len(v)
            teams.append([clean(v[1]), int(v[2]), int(v[n-7]), int(v[n-6]), int(v[n-5]), int(v[n-4]), int(v[n-3]), int(v[n-1])])
        data['divisions'].append({'name': name, 'teams': teams,
                                  'results': [x['row'] for x in results(key, 1)],
                                  'fixtures': [x['row'] for x in fixtures(key, 1)]})
        for x in results(key, 3):
            if x['type'].startswith('CC'):
                cc_r[x['row'][0] + ','.join(x['raw'])] = x['row'] + [x['type'][3:]]
        for x in fixtures(key, 3):
            if x['type'].startswith('CC'):
                cc_f[x['row'][0] + ','.join(x['raw'])] = x['row'] + [x['type'][3:]]
    u16 = lambda n: re.search(r'\bU16\b', n)
    for label, rx in [('League Cup', r'League Cup U16'), ('RT Litho Cup', r'RT litho')]:
        k = key_of(rx)
        if not k:
            continue
        data['cups'].append({'name': label,
                             'results': [x['row'] for x in results(k, 1) if any(map(u16, x['raw']))],
                             'fixtures': [x['row'] for x in fixtures(k, 1) if any(map(u16, x['raw']))]})
    short = lambda s: re.sub(r'\s+(sponsored|supported) by .*$', '', s, flags=re.I)
    for r in cc_r.values():
        r[6] = short(r[6])
    for f in cc_f.values():
        f[7] = short(f[7])
    data['cups'].append({'name': 'County Cups', 'county': True,
                         'results': list(cc_r.values()), 'fixtures': list(cc_f.values())})
    return data


def label(d, year=True):
    s = f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"
    return f"{s} {d.year}" if year else s


def main():
    data = scrape()
    summary = '; '.join(f"{d['name']}: {len(d['teams'])}t/{len(d['results'])}r/{len(d['fixtures'])}f" for d in data['divisions'])
    print(summary)
    if any(len(d['teams']) == 0 for d in data['divisions']):
        sys.exit('A division came back with no teams, so the site was not rebuilt.')
    now = datetime.now(ZoneInfo('Europe/London'))
    dates = []
    for d in data['divisions']:
        for r in d['results']:
            if r[3] is not None:
                dd, mm = map(int, r[0].split('/'))
                dates.append(datetime(now.year if mm <= now.month + 1 else now.year - 1, mm, dd))
    updated = label(max(dates)) if dates else 'start of season'
    tpl = (ROOT / 'scripts' / 'template.html').read_text()
    html = (tpl.replace('/*DATA*/', json.dumps(data, separators=(',', ':')))
               .replace('/*UPDATED*/', updated)
               .replace('/*FETCHED*/', label(now, year=False)))
    (ROOT / 'site' / 'index.html').write_text(html)
    (ROOT / 'site' / 'data.json').write_text(json.dumps(data, separators=(',', ':')))


if __name__ == '__main__':
    main()
