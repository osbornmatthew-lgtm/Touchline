import json, zipfile, os, sys
from PIL import Image, ImageDraw, ImageFont
src_path = sys.argv[1]
out = os.path.join(os.path.dirname(src_path), 'touchline-site')
os.makedirs(out, exist_ok=True)
src = open(src_path).read()
head = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="EJA Under 16 league tables, results, fixtures and stats.">
<meta property="og:title" content="Touchline EJA">
<meta property="og:description" content="EJA Under 16 league tables, results, fixtures and stats.">
<meta property="og:image" content="icon-512.png">
<meta name="theme-color" content="#0E1217">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Touchline">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" href="icon-192.png">
<link rel="manifest" href="manifest.json">
<style>body{margin:0}[hidden]{display:none!important}:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);background:#0E1217}</style>
"""
body = src.replace('<title>Touchline U16</title>', '<title>Touchline EJA</title>', 1)
i = body.index('<header class="top">')
open(os.path.join(out, 'index.html'), 'w').write(head + body[:i] + '</head>\n<body>\n' + body[i:] + '\n</body>\n</html>\n')
fp = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
for size, name in [(512, 'icon-512.png'), (192, 'icon-192.png'), (180, 'apple-touch-icon.png')]:
    im = Image.new('RGB', (size, size), '#0E1217'); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(fp, int(size * 0.6)) if os.path.exists(fp) else ImageFont.load_default()
    b = d.textbbox((0, 0), 'T', font=f); w, h = b[2] - b[0], b[3] - b[1]
    d.text(((size - w) / 2 - b[0], (size - h) / 2 - b[1] - size * 0.05), 'T', font=f, fill='#C9F24A')
    d.rectangle([size * 0.22, size * 0.8, size * 0.78, size * 0.84], fill='#C9F24A')
    im.save(os.path.join(out, name))
json.dump({"name": "Touchline EJA", "short_name": "Touchline", "start_url": "./", "display": "standalone", "background_color": "#0E1217", "theme_color": "#0E1217", "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]}, open(os.path.join(out, 'manifest.json'), 'w'))
z = os.path.join(os.path.dirname(src_path), 'touchline-site.zip')
with zipfile.ZipFile(z, 'w') as zf:
    for n in os.listdir(out): zf.write(os.path.join(out, n), n)
print(z)
