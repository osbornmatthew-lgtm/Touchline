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
