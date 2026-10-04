"""End-to-end test of the home runner against the mock Full-Time and a throwaway copy of the repo.

    python tests/run_e2e.py [--real-delays]

Makes a local 'origin' (a bare copy of this repo with the working-tree code committed), a runner clone of it,
and a mock Full-Time on 127.0.0.1:8765 built from tests/fixtures. Then runs the runner through a full refresh,
quiet and busy match-day checks, a heartbeat republish, a block and throttling, and checks what lands on
gh-pages, main and the status branch. Nothing touches GitHub or Full-Time.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from mock_fulltime import make, serve  # noqa: E402

PORT = 8765
fails = []


def sh(*cmd, cwd=None, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8')
    if check and r.returncode:
        raise SystemExit(f'{" ".join(cmd)} failed:\n{r.stdout}\n{r.stderr}')
    return r


def ok(cond, what):
    print(('  PASS ' if cond else '  FAIL ') + what)
    if not cond:
        fails.append(what)


def setup(tmp, real_delays):
    origin, runner = tmp / 'origin.git', tmp / 'runner'
    sh('git', 'init', '-q', '--bare', '-b', 'main', str(origin))
    sh('git', 'clone', '-q', str(origin), str(runner))
    # main: the current working tree; gh-pages: the current live branch
    for item in REPO.iterdir():
        if item.name in ('.git', '.runner') or item.name.startswith('__'):
            continue
        (shutil.copytree(item, runner / item.name, ignore=shutil.ignore_patterns('__pycache__')) if item.is_dir() else shutil.copy2(item, runner / item.name))
    if not real_delays:
        cfgp = runner / 'config' / 'leagues.json'
        c = json.loads(cfgp.read_text(encoding='utf-8'))
        c['fetch']['delay_ms'] = [5, 20]
        cfgp.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding='utf-8')
    sh('git', 'add', '-A', cwd=runner)
    sh('git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'code under test', cwd=runner)
    sh('git', 'push', '-q', 'origin', 'HEAD:main', cwd=runner)
    pages = sh('git', '-C', str(REPO), 'rev-parse', 'gh-pages').stdout.strip()
    sh('git', 'fetch', '-q', str(REPO), 'gh-pages', cwd=runner)
    snap = sh('git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit-tree', f'{pages}^{{tree}}', '-m', 'live gh-pages', cwd=runner).stdout.strip()
    sh('git', 'push', '-q', 'origin', f'{snap}:refs/heads/gh-pages', cwd=runner)
    return origin, runner


def run(runner, now, *args, block=False, fail=0.0):
    import urllib.request
    urllib.request.urlopen(f'http://127.0.0.1:{PORT}/__reset?block={int(block)}&fail={fail}').read()
    env = {**os.environ, 'TOUCHLINE_FULLTIME_URL': f'http://127.0.0.1:{PORT}', 'TOUCHLINE_NOW': now}
    r = sh(sys.executable, 'runner/touchline.py', 'run', *args, cwd=runner, env=env, check=False)
    hits = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/__hits').read())
    print('   ' + '\n   '.join(r.stdout.strip().splitlines()[-8:]))
    if r.stderr.strip():
        print('   stderr: ' + r.stderr.strip().splitlines()[-1])
    return r.returncode, hits


def show(origin, ref, path):
    r = sh('git', '--git-dir', str(origin), 'show', f'{ref}:{path}', check=False)
    return r.stdout if r.returncode == 0 else None


def count(origin, ref):
    return int(sh('git', '--git-dir', str(origin), 'rev-list', '--count', ref).stdout)


def strip_volatile(html):
    return re.sub(r"^DATA\.fetched = '.*';$", '', html, flags=re.M)


def main():
    real = '--real-delays' in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix='touchline-e2e-'))
    origin, runner = setup(tmp, real)
    live = {lg: json.loads((HERE / 'fixtures' / f'{lg}.json').read_text(encoding='utf-8')) for lg in ('eja', 'bcfa')}
    mocks = {lg: make(json.loads(json.dumps(live[lg])), lg) for lg in live}
    srv = serve(list(mocks.values()), PORT)
    live_html = {'eja': sh('git', '-C', str(REPO), 'show', 'gh-pages:index.html').stdout,
                 'bcfa': sh('git', '-C', str(REPO), 'show', 'gh-pages:bcfa/index.html').stdout}
    try:
        print('A. Saturday-style full refresh, first ever run')
        code, hits = run(runner, '2026-10-04T13:00', '--mode', 'full', '--force')
        ok(code == 0, 'run succeeded')
        st = json.loads(show(origin, 'status', 'status.json') or '{}')
        ok(st.get('ok') is True, 'status.json on the status branch says ok')
        for lg, path in (('eja', 'index.html'), ('bcfa', 'bcfa/index.html')):
            built = show(origin, 'gh-pages', path)
            ok(built is not None and strip_volatile(built) == strip_volatile(live_html[lg]),
               f'{lg}: published page identical to the live one apart from the "checked at" time')
            ok(json.loads(show(origin, 'main', f'data/{lg}.json') or 'null') == live[lg], f'{lg}: data/{lg}.json on main matches')
        ok(show(origin, 'gh-pages', 'cal/aveley.ics') is not None, 'EJA calendar feeds still there')
        ok(show(origin, 'gh-pages', 'bcfa/sw.js') is not None, 'BCFA folder kept alongside EJA')
        print(f'   requests: {sum(hits.values())} ({hits.get("/displayFixture.html", 0)} match pages)')
        pages_after_a = count(origin, 'gh-pages')

        print('B. Sunday 13:20 match-day check, nothing new')
        code, hits = run(runner, '2026-10-04T13:20')
        st = json.loads(show(origin, 'status', 'status.json'))
        ok(code == 0 and st['ok'], 'run succeeded')
        ok(count(origin, 'gh-pages') == pages_after_a, 'nothing published (no change, checked recently)')
        ok(hits.get('/displayFixture.html', 0) <= 30, f'goal-time pages mostly skipped ({hits.get("/displayFixture.html", 0)} fetched)')
        ok(st['leagues']['eja']['note'] == 'no change', 'status note says no change')
        print(f'   requests: {sum(hits.values())}, EJA checked: {st["leagues"]["eja"]["checked"]}')

        print('C. Sunday 13:30, a score is corrected on Full-Time')
        m = mocks['eja']
        div = next(d for d in m.data['divisions'] if any(r[0] == '04/10' and r[3] is not None for r in d['results']))
        r = next(r for r in div['results'] if r[0] == '04/10' and r[3] is not None)
        r[3] += 1
        m.events[r[6]] = (r[1], r[2], (r[7] or []) + [[88, 'H', 'G']])
        code, hits = run(runner, '2026-10-04T13:30')
        page = show(origin, 'gh-pages', 'index.html')
        ok(code == 0, 'run succeeded')
        ok(count(origin, 'gh-pages') == pages_after_a + 1, 'one gh-pages commit')
        ok(f'"{r[1]}","{r[2]}",{r[3]},{r[4]}' in page, f'new score {r[1]} {r[3]}-{r[4]} {r[2]} is live')
        ok('[88,"H","G"]' in page, 'new goal time picked up')
        ok("DATA.fetched = 'Sunday 4 October, 13:30';" in page, 'checked time updated')

        print('D. Sunday 15:10, no change but over 45 minutes since the last publish (heartbeat)')
        code, hits = run(runner, '2026-10-04T15:10')
        page = show(origin, 'gh-pages', 'index.html')
        ok(code == 0 and "DATA.fetched = 'Sunday 4 October, 15:10';" in page, 'republished so the site does not show "Scores may be behind" wrongly')

        print('E. Sunday 15:20, Full-Time blocks us')
        before = count(origin, 'gh-pages')
        code, hits = run(runner, '2026-10-04T15:20', block=True)
        st = json.loads(show(origin, 'status', 'status.json'))
        ok(code != 0 and not st['ok'], 'run reported as failed')
        ok(count(origin, 'gh-pages') == before, 'nothing published')
        ok(sum(hits.values()) <= 3, f'stopped knocking straight away ({sum(hits.values())} requests)')
        ok(st['leagues']['eja']['last_success'].startswith('2026-10-04T15:10'), 'last success still shows 15:10, so the watchdog will notice')

        print('F. Sunday 15:30, Full-Time throttling 5% of requests')
        code, hits = run(runner, '2026-10-04T15:30', fail=0.05)
        st = json.loads(show(origin, 'status', 'status.json'))
        ok(code == 0 and st['ok'], 'run succeeded after backing off')

        print('G. Monday 07:50 full refresh')
        code, hits = run(runner, '2026-10-05T07:50')
        st = json.loads(show(origin, 'status', 'status.json'))
        ok(code == 0 and st['ok'] and st['leagues']['eja']['mode'] == 'full', 'full refresh succeeded')
        print(f'   requests: {sum(hits.values())} ({hits.get("/displayFixture.html", 0)} match pages)')

        print('H. Wednesday 7 October, no games that day')
        code, hits = run(runner, '2026-10-07T12:00')
        st = json.loads(show(origin, 'status', 'status.json'))
        ok(code == 0 and st['leagues']['eja']['note'] == 'no games today' and sum(hits.values()) == 0, 'quiet day: no requests at all')
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: ' + '; '.join(fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
