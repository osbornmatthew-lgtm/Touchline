// Touchline pull for Claude scheduled runs (Matt's desktop browser, on a fulltime.thefa.com page).
// Set window.__tlmode = 'matchday' or 'full' first, then run this. It works through every enabled league
// with the same plan rules as runner/touchline.py (plan_for), and leaves:
//   window.__tlres  {league id: {plan, summary, out}}   window.__tllog  progress lines, ending 'DONE'
// Then save window.__tlres gzipped and pass it to runner/claude/publish.py.
window.__tlres = {}; window.__tllog = [];
(async () => {
  const mode = window.__tlmode || 'matchday';
  const raw = p => fetch('https://raw.githubusercontent.com/osbornmatthew-lgtm/Touchline/main/' + p + '?x=' + Date.now())
    .then(r => { if (!r.ok) throw new Error(p + ' ' + r.status); return r.text(); });
  const cfg = JSON.parse(await raw('config/leagues.json'));
  const src = await raw('scripts/scrape.js');
  const AF = Object.getPrototypeOf(async function(){}).constructor;
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Europe/London' }));
  const dm = d => String(d.getDate()).padStart(2, '0') + '/' + String(d.getMonth() + 1).padStart(2, '0');
  const seasonDay = ddmm => { const d = +ddmm.slice(0, 2), m = +ddmm.slice(3, 5); const start = now.getMonth() + 1 >= 7 ? now.getFullYear() : now.getFullYear() - 1; return new Date(m >= 7 ? start : start + 1, m - 1, d); };
  const f = cfg.fetch;
  for (const L of cfg.leagues.filter(l => l.enabled !== false && !((m => m && +m[1] <= 12)(String(l.age || '').match(/^U(\d+)$/))))) {
    const t0 = Date.now();
    try {
      let prev = null;
      try { prev = JSON.parse((await raw('data/' + L.id + '.json')).replace(/\bNaN\b/g, 'null')); } catch (e) { prev = null; }
      const full = mode === 'full' || !prev || (prev.divisions || []).map(d => d.name).join('|') !== L.divisions.map(d => d[0]).join('|');
      const recheck = cfg[full ? 'full_refresh' : 'match_day'].goal_times_recheck_days;
      const events = {};
      for (const d of (prev || {}).divisions || []) for (const r of d.results) {
        if (r.length > 7 && r[6] && r[3] !== null) {
          const ev = r[7] || [];
          if (ev.length < r[3] + r[4] && (now - seasonDay(r[0])) / 864e5 <= recheck) continue;
          events[String(r[6])] = { s: r[3] + '-' + r[4], e: ev };
        }
      }
      const plan = { full, only_divs: null, only_cups: null };
      if (!full) {
        const days = new Set([dm(now), dm(new Date(now - 864e5))]);
        const county = prev.cups.find(c => c.county) || { results: [], fixtures: [] };
        const ct = new Set();
        for (const r of county.results) if (days.has(r[0])) { ct.add(r[1]); ct.add(r[2]); }
        for (const x of county.fixtures) if (days.has(x[0])) { ct.add(x[2]); ct.add(x[3]); }
        plan.only_divs = prev.divisions.filter(d => d.fixtures.some(x => days.has(x[0])) || d.results.some(r => days.has(r[0])) || d.teams.some(t => ct.has(t[0]))).map(d => d.name);
        const names = new Set(L.cups.map(c => c[0]));
        plan.only_cups = prev.cups.filter(c => !c.county && names.has(c.name) && (c.fixtures.some(x => days.has(x[0])) || c.results.some(r => days.has(r[0])))).map(c => c.name);
        if (!plan.only_divs.length && !plan.only_cups.length) { window.__tlres[L.id] = { plan, summary: 'no games today', out: null }; window.__tllog.push(L.id + ': no games today'); continue; }
      }
      window.__tlcfg = { S: L.season, DIVS: L.divisions, CUPS: L.cups, AGE: L.age_match || L.age, KEEP_SIDE: L.keep_side, CLEAN: L.clean ?? null,
        ONLY_DIVS: plan.only_divs, ONLY_CUPS: plan.only_cups, EVENTS: events, KNOWN_VENUES: Object.keys((prev || {}).venues || {}), NO_EVENTS: !(L.events ?? true),
        FILTER_FIXTURES: L.filter_fixtures || false, LIMIT: f.concurrency || 2, DELAY: f.delay_ms || [600, 1200], RETRIES: f.retries || 2,
        DEADLINE_MS: (f.run_limit_minutes || 10) * 60000, NO_DOM: true };
      window.__tlout = null;
      const summary = await new AF(src.replace(/\n([^\n]*)\s*$/, '\nreturn $1'))();
      window.__tlres[L.id] = { plan, summary, out: window.__tlout };
      window.__tllog.push(L.id + ': ok (' + Math.round((Date.now() - t0) / 1000) + 's)');
    } catch (e) {
      window.__tllog.push(L.id + ': ERROR ' + e.message);
      if (/HTTP (403|429)/.test(e.message)) { window.__tllog.push('BLOCKED'); break; }
    }
  }
  window.__tllog.push('DONE');
})();
'started'
