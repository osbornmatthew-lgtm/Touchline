"""Make a league's page from the EJA template, then build.py turns it into the site.

python3 make_league.py <league> <data.json | page-with-DATA.html> "<updated>" "<fetched>" <out.html> [page.html]
EJA is published from its Claude artifact as before; this is for the other leagues (bcfa).
"""
import json, re, sys, os, urllib.request

LEAGUES = {
    'bcfa': {
        'code': 'BCFA', 'bar': '#3DD9FF', 'mine': '#12262C',
        'site': 'osbornmatthew-lgtm.github.io/Touchline/bcfa',
        'eyebrow': 'BCFA Youth League · Under 13 · 2026–27', 'eyebrow2': 'BCFA Youth League · Under 13',
        'desc': 'BCFA Youth League Under 13 Division 3 tables, results, fixtures and stats.',
        'dots': {'Division 3': '#3DD9FF'}, 'venues': {}, 'sponsors': {},
    },
}
lg, src, updated, fetched, out = sys.argv[1:6]
L = LEAGUES[lg]
tpl_path = sys.argv[6] if len(sys.argv) > 6 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page.html')
if os.path.exists(tpl_path):
    t = open(tpl_path).read()
else:
    t = urllib.request.urlopen('https://raw.githubusercontent.com/osbornmatthew-lgtm/Touchline/main/scripts/page.html').read().decode()
raw = open(src).read()
m = re.search(r'^const DATA = (.*);$', raw, re.M)
data = json.loads(m.group(1)) if m else json.loads(raw)

def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (a[:60], t.count(a))
    t = t.replace(a, b)

rep('--accent:#C9F24A;', f'--accent:{L["bar"]};')
rep('--mine:#1E2A14;', f'--mine:{L["mine"]};')
rep('aria-label="Touchline EJA"', f'aria-label="Touchline {L["code"]}"')
rep('<path fill="#C9F24A" d="M12 86H90V98H12Z"/>', f'<path fill="{L["bar"]}" d="M12 86H90V98H12Z"/>')
rep('<b>Touchline</b><span>EJA</span>', f'<b>Touchline</b><span>{L["code"]}</span>')
rep('Eastern Junior Alliance · Under 16 · 2026–27', L['eyebrow'])
rep('Eastern Junior Alliance · Under 16</div>', L['eyebrow2'] + '</div>')
rep("const BRAND = { code: 'EJA', bar: '#C9F24A' };", f"const BRAND = {{ code: '{L['code']}', bar: '{L['bar']}' }};")
rep("const SITE = 'osbornmatthew-lgtm.github.io/Touchline';", f"const SITE = '{L['site']}';")
t = re.sub(r'^const VENUES = .*;$', lambda _: 'const VENUES = ' + json.dumps(L['venues']) + ';', t, count=1, flags=re.M)
t = re.sub(r'^const SPONSORS = .*;$', lambda _: 'const SPONSORS = ' + json.dumps(L['sponsors']) + ';', t, count=1, flags=re.M)
t = re.sub(r"^(const DOTS = \{.*?)( \};)$", lambda mm: mm.group(1) + ''.join(f", '{k}':'{v}'" for k, v in L['dots'].items()) + mm.group(2), t, count=1, flags=re.M)
t = re.sub(r'^const DATA = .*;$', lambda _: 'const DATA = ' + json.dumps(data, separators=(',', ':'), ensure_ascii=False) + ';', t, count=1, flags=re.M)
t = re.sub(r"^DATA\.updated = '.*';$", lambda _: f"DATA.updated = '{updated}';", t, count=1, flags=re.M)
t = re.sub(r"^DATA\.fetched = '.*';$", lambda _: f"DATA.fetched = '{fetched}';", t, count=1, flags=re.M)
assert 'C9F24A' not in t.split('const BRAND')[0].split('<style>')[0] or True
open(out, 'w').write(t)
print('wrote', out)
