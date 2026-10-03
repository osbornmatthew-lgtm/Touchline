"""One-off: add the club partner (sponsor) slot to a Touchline page. Safe to run twice."""
import sys

CSS = """.partner{display:flex;align-items:center;gap:14px;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--fg);text-decoration:none}
.partner .logo{flex:0 0 auto;width:112px;height:56px;border-radius:8px;background:#fff;display:flex;align-items:center;justify-content:center;padding:6px}
.partner .logo img{max-width:100%;max-height:100%;object-fit:contain}
.partner .pn{font-weight:700;font-size:16px}
.partner .go{margin-left:auto;color:var(--accent);font-size:13px;font-weight:600;white-space:nowrap}
a.partner:hover{border-color:var(--accent)}
"""

JS = """
// Club partners. Key is the club name as it appears in the table. logo is a data: URI or an https URL; url is optional.
const SPONSORS = {};
function partnerHtml(name) {
  const p = SPONSORS[name];
  if (!p) return '';
  const inner = `<span class="logo"><img src="${esc(p.logo)}" alt="${esc(p.name)} logo"></span><span><span class="eyebrow">Club partner</span><br><span class="pn">${esc(p.name)}</span></span>${p.url ? '<span class="go">Visit ↗</span>' : ''}`;
  return p.url ? `<a class="partner" href="${esc(p.url)}" target="_blank" rel="noopener sponsored">${inner}</a>` : `<div class="partner">${inner}</div>`;
}
"""

for path in sys.argv[1:]:
    s = open(path, encoding='utf-8').read()
    if 'const SPONSORS' in s:
        print(path, 'already patched'); continue
    a = '.sheet-body h3{'
    assert s.count(a) == 1, (path, 'css anchor')
    s = s.replace(a, CSS + a)
    b = "const CUP_ACCENT = '#C9F24A';"
    assert s.count(b) == 1, (path, 'js anchor')
    s = s.replace(b, b + JS)
    c = "    </header>\n    <div class=\"stats six\">"
    assert s.count(c) == 1, (path, 'markup anchor')
    s = s.replace(c, "    </header>\n    ${partnerHtml(name)}\n    <div class=\"stats six\">")
    open(path, 'w', encoding='utf-8').write(s)
    print(path, 'patched')
