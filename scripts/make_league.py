"""Make a league's page from the shared page (scripts/page.html), then build.py turns it into the site.

python3 make_league.py <league> <data.json | page-with-DATA.html> "<updated>" "<fetched>" <out.html> [page.html]

League settings come from config/leagues.json. A league with "template": "native" (EJA Under 16) uses the
shared page as it is, with only the data swapped in. "brand" leagues (BCFA, other age groups) also get their
own colours, names and labels.
"""
import json, re, sys, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, '..', 'config', 'leagues.json')


def load_league(lg):
    if os.path.exists(CONFIG):
        cfg = json.load(open(CONFIG, encoding='utf-8'))
    else:  # run on its own (downloaded without the rest of the repo)
        cfg = json.loads(urllib.request.urlopen('https://raw.githubusercontent.com/osbornmatthew-lgtm/Touchline/main/config/leagues.json').read().decode('utf-8'))
    return next(x for x in cfg['leagues'] if x['id'] == lg), cfg


HISTORY = os.path.join(HERE, '..', 'data', 'history')
EJA_AGES = [13, 14, 15, 16, 18]


def cohort_history(age):
    """Past seasons for the players now in this age group: last season's U15s are this season's U16s, and so on.
    Newest first: [{season, age, divisions: [{name, teams}], results: [[dd/mm, home, away, hs, as, note, comp]]}]."""
    out = []
    if not os.path.isdir(HISTORY):
        return out
    seasons = sorted((f[:-5] for f in os.listdir(HISTORY) if re.match(r'\d{4}-\d{2}\.json$', f)), reverse=True)
    now = int(age[1:])
    for k, season in enumerate(seasons[:3], start=1):
        was = now - k
        if was not in EJA_AGES:
            was = 16 if now == 18 and k == 1 else (now if now == 18 else None)  # U18 holds two years: use last season's U16s first
        if was is None or was < 13:
            continue
        a = f'U{was}'
        h = json.load(open(os.path.join(HISTORY, season + '.json'), encoding='utf-8'))
        out.append({'season': season, 'age': a, 'divisions': [d for d in h['divisions'] if d['name'].startswith(a + ' ')],
                    'results': [r[:7] for r in h['results'] if r[7] == a]})
    return out


STOP = {'fc', 'youth', 'u17', 'u18', '18s', 'the', 'and', 'alliance', 'academy', 'development'}


def tidy(n):
    """Clean up untidy Full-Time names: "Bedford Town FC (Youth Development )U18", "St Neots Town St Neots Town"."""
    n = re.sub(r'\s*\(\s*Youth(?: Development)?\s*\)\s*(?:U1[78]\b)?', ' ', n).strip()
    w = n.split()
    for k in range(len(w) // 2, 0, -1):
        if w[:k] == w[k:2 * k]:
            w = w[k:]; break
    while len(w) > 1 and w[-1].upper() in ('FC', 'F.C.'):
        w = w[:-1]
    return ' '.join(w)


def reconcile(data):
    """Make results, fixtures and cups use the same names as the league tables (Full-Time sometimes spells a team
    differently on its results pages). A name maps to the table name it shares most words with, if clearly the best."""
    toks = lambda n: {t for t in re.findall(r'[a-z0-9]+', n.lower()) if t not in STOP}
    for d in data.get('divisions', []):
        for t in d['teams']:
            t[0] = tidy(t[0])
    table = [t[0] for d in data.get('divisions', []) for t in d['teams']]
    cache = {}
    def fix(n, pool):
        if n is None or n in table:
            return n
        key = (n, id(pool))
        if key not in cache:
            tn, best, second, pick = toks(tidy(n)), 0, 0, tidy(n)
            for c in pool:
                tc = toks(c)
                sc = len(tn & tc) / len(tn | tc) if tn | tc else 0
                if sc > best:
                    best, second, pick = sc, best, c
                elif sc > second:
                    second = sc
            cache[key] = pick if best >= 0.5 and best > second else tidy(n)
        return cache[key]
    for d in data.get('divisions', []):
        own = [t[0] for t in d['teams']]
        for r in d['results']:
            r[1], r[2] = fix(r[1], own), fix(r[2], own)
        for f in d['fixtures']:
            f[2], f[3] = fix(f[2], own), fix(f[3], own)
    for c in data.get('cups', []):
        for r in c['results']:
            r[1], r[2] = fix(r[1], table), fix(r[2], table)
        for f in c['fixtures']:
            f[2], f[3] = fix(f[2], table), fix(f[3], table)
    return data


def make_page(L, data, updated, fetched, t, site_base='https://osbornmatthew-lgtm.github.io/Touchline/'):
    def rep(a, b, n=1):
        nonlocal t
        assert t.count(a) == n, (a[:60], t.count(a))
        t = t.replace(a, b)

    if L.get('template', 'brand') != 'native':
        B = L['brand']
        site = (site_base + L['folder']).rstrip('/').replace('https://', '')
        rep('--accent:#C9F24A;', f'--accent:{B["bar"]};')
        rep('--mine:#1E2A14;', f'--mine:{B["mine"]};')
        rep('aria-label="Touchline EJA"', f'aria-label="Touchline {L["code"]}"')
        rep('<path fill="#C9F24A" d="M12 86H90V98H12Z"/>', f'<path fill="{B["bar"]}" d="M12 86H90V98H12Z"/>')
        rep('<b>Touchline</b><span>EJA</span>', f'<b>Touchline</b><span>{L["code"]}</span>')
        rep('Eastern Junior Alliance · Under 16 · 2026–27', B['eyebrow'])
        rep('Eastern Junior Alliance · Under 16</div>', B['eyebrow2'] + '</div>')
        rep("const BRAND = { code: 'EJA', bar: '#C9F24A' };", f"const BRAND = {{ code: '{L['code']}', bar: '{B['bar']}' }};")
        rep("const SITE = 'osbornmatthew-lgtm.github.io/Touchline';", f"const SITE = '{site}';")
        t = re.sub(r'^const VENUES = .*;$', lambda _: 'const VENUES = ' + json.dumps(B.get('venues', {})) + ';', t, count=1, flags=re.M)
        t = re.sub(r'^const SPONSORS = .*;$', lambda _: 'const SPONSORS = ' + json.dumps(B.get('sponsors', {})) + ';', t, count=1, flags=re.M)
        t = re.sub(r"^(const DOTS = \{.*?)( \};)$", lambda mm: mm.group(1) + ''.join(f", '{k}':'{v}'" for k, v in B.get('dots', {}).items()) + mm.group(2), t, count=1, flags=re.M)
    if L.get('template') == 'native':
        # EJA age groups share one page: set the age, the public address and this cohort's past seasons
        site = (site_base + L['folder']).rstrip('/').replace('https://', '')
        t, n = re.subn(r"^const AGE = '.*';$", f"const AGE = '{L['age']}';", t, count=1, flags=re.M)
        t = re.sub(r"^const SITE = '.*';$", f"const SITE = '{site}';", t, count=1, flags=re.M)
        t = re.sub(r'^const HIST = .*;$', lambda _: 'const HIST = ' + json.dumps(cohort_history(L['age']), separators=(',', ':'), ensure_ascii=False) + ';', t, count=1, flags=re.M)
    if L.get('template') == 'native':
        data = reconcile(json.loads(json.dumps(data)))
    data = {**data, 'cups': [c for c in data.get('cups', []) if c.get('county') or c.get('results') or c.get('fixtures')]}  # drop empty cups
    t, n = re.subn(r'^const DATA = .*;$', lambda _: 'const DATA = ' + json.dumps(data, separators=(',', ':'), ensure_ascii=False) + ';', t, count=1, flags=re.M)
    assert n == 1, 'const DATA line not found in the page'
    t, n = re.subn(r"^DATA\.updated = '.*';$", lambda _: f"DATA.updated = '{updated}';", t, count=1, flags=re.M)
    assert n == 1, 'DATA.updated line not found in the page'
    t, n = re.subn(r"^DATA\.fetched = '.*';$", lambda _: f"DATA.fetched = '{fetched}';", t, count=1, flags=re.M)
    assert n == 1, 'DATA.fetched line not found in the page'
    return t


if __name__ == '__main__':
    lg, src, updated, fetched, out = sys.argv[1:6]
    L, cfg = load_league(lg)
    tpl_path = sys.argv[6] if len(sys.argv) > 6 else os.path.join(HERE, 'page.html')
    if os.path.exists(tpl_path):
        t = open(tpl_path, encoding='utf-8').read()
    else:
        t = urllib.request.urlopen('https://raw.githubusercontent.com/osbornmatthew-lgtm/Touchline/main/scripts/page.html').read().decode()
    raw = open(src, encoding='utf-8').read()
    m = re.search(r'^const DATA = (.*);$', raw, re.M)
    data = json.loads(m.group(1)) if m else json.loads(raw)
    open(out, 'w', encoding='utf-8').write(make_page(L, data, updated, fetched, t, cfg.get('site_base')))
    print('wrote', out)
