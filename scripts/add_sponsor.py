"""Add or replace a club partner on a Touchline page.

python3 add_sponsor.py page.html "Hashtag United" "Sponsor Ltd" logo.png [https://sponsor.example]
python3 add_sponsor.py page.html "Hashtag United" --remove
"""
import base64, io, json, re, sys
from PIL import Image

path, team = sys.argv[1], sys.argv[2]
s = open(path, encoding='utf-8').read()
m = re.search(r'^const SPONSORS = (.*);$', s, re.M)
assert m, 'page has no SPONSORS line; run patch_sponsors.py first'
sp = json.loads(m.group(1))

if sys.argv[3] == '--remove':
    sp.pop(team, None)
else:
    name, img = sys.argv[3], sys.argv[4]
    url = sys.argv[5] if len(sys.argv) > 5 else ''
    im = Image.open(img)
    im = im.convert('RGBA') if im.mode in ('P', 'LA', 'RGBA') else im.convert('RGB')
    im.thumbnail((336, 168))  # 3x the 112x56 display box
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    entry = {'name': name, 'logo': 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()}
    if url:
        entry['url'] = url
    sp[team] = entry
    print(f'{team}: {name}, logo {len(buf.getvalue()) // 1024} KB')

line = 'const SPONSORS = ' + json.dumps(sp, separators=(',', ':'), ensure_ascii=False) + ';'
s = s[:m.start()] + line + s[m.end():]
open(path, 'w', encoding='utf-8').write(s)
print('sponsors on page:', ', '.join(sp) or 'none')
