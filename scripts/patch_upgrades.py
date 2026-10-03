"""One-off: calendar subscribe buttons, usage tracking hooks and offline notice. Safe to run twice."""
import sys

CSS = """.calrow{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.calbtn{display:inline-flex;align-items:center;gap:6px;padding:9px 14px;border-radius:999px;border:1px solid var(--accent);color:var(--fg);background:transparent;font:inherit;font-size:14px;font-weight:600;text-decoration:none;cursor:pointer}
.calbtn:hover{background:color-mix(in srgb, var(--accent) 18%, transparent)}
.offline{position:sticky;top:0;z-index:30;background:var(--accent);color:#05070A;text-align:center;font-size:13px;font-weight:700;padding:6px 12px}
"""

JS = """
// Calendar feeds are built for every team by build.py and served from the public site.
const SITE = 'touchline-eja.netlify.app';
const slug = n => n.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
function calHtml(name) {
  const feed = `webcal://${SITE}/cal/${slug(name)}.ics`;
  return `<div class="calrow"><a class="calbtn" href="${feed}" data-track="calendar">Add to iPhone / Outlook</a><a class="calbtn" href="https://calendar.google.com/calendar/r?cid=${encodeURIComponent(feed)}" target="_blank" rel="noopener" data-track="calendar-google">Add to Google Calendar</a></div><p class="fine">Puts ${esc(name)}'s fixtures in your calendar. New and moved games update on their own.</p>`;
}
// Usage counts (GoatCounter, cookie-free). Only does anything on the public site once the counter script is loaded.
function track(path, title) { try { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path, title: title || path, event: true }); } catch (e) {} }
document.addEventListener('click', e => { const a = e.target.closest('[data-track]'); if (a) track(a.dataset.track); });
function offlineNote() {
  let el = document.getElementById('offline');
  if (navigator.onLine) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement('div'); el.id = 'offline'; el.className = 'offline'; document.body.prepend(el); }
  el.textContent = `No signal: showing data from ${DATA.fetched}`;
}
addEventListener('online', offlineNote); addEventListener('offline', offlineNote);
"""

for path in sys.argv[1:]:
    s = open(path, encoding='utf-8').read()
    if 'function calHtml' in s:
        print(path, 'already patched'); continue
    def rep(a, b):
        global s
        assert s.count(a) == 1, (path, a[:40])
        s = s.replace(a, b)
    rep('.sheet-body h3{', CSS + '.sheet-body h3{')
    rep("const CUP_ACCENT = '#C9F24A';", "const CUP_ACCENT = '#C9F24A';" + JS)
    rep('<section><h3>Next up</h3><ul class="list">${upHtml}</ul></section>',
        '<section><h3>Next up</h3><ul class="list">${upHtml}</ul>${calHtml(name)}</section>')
    rep('function openTeam(name) {\n', 'function openTeam(name) {\n  track(\'team/\' + slug(name), name);\n')
    rep("  document.getElementById('title').textContent = comp.name;\n",
        "  document.getElementById('title').textContent = comp.name;\n  track('view/' + slug(comp.name), comp.name);\n")
    i = s.index("document.getElementById('updated').textContent")
    j = s.index('\n', i)
    s = s[:j + 1] + 'offlineNote();\n' + s[j + 1:]
    open(path, 'w', encoding='utf-8').write(s)
    print(path, 'patched')
