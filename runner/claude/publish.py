#!/usr/bin/env python3
"""Publish a Touchline pull made in Matt's browser by a Claude scheduled run (runner/claude/pull.js).

    python3 runner/claude/publish.py <pull.json or pull.json.gz> [--dry-run]

Runs the normal runner (runner/touchline.py: merge, checks, build, publish to gh-pages, data to main, status.json),
with Full-Time replaced by the pulled data and each league's plan taken from the pull, so the merge matches what was fetched.
Mode (match day or full) comes from the plans in the pull.
"""
import argparse, gzip, json, socket, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import touchline as T

src = Path(sys.argv[1])
raw = gzip.open(src).read() if src.read_bytes()[:2] == b'\x1f\x8b' else src.read_bytes()
PULL = json.loads(raw)
dry = '--dry-run' in sys.argv

_plan_for = T.plan_for


def plan_for(L, prev, meta, mode, now, cfg):
    p = _plan_for(L, prev, meta, mode, now, cfg)
    got = PULL.get(L['id'])
    if not got:
        raise RuntimeError('not in this pull')
    p.update(full=got['plan']['full'], only_divs=got['plan']['only_divs'], only_cups=got['plan']['only_cups'])
    if not p['full'] and p['only_divs'] is None:
        p['only_divs'], p['only_cups'] = [], []
    return p


class FromPull:
    def __init__(self, cfg): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def scrape(self, L, plan):
        out = PULL[L['id']].get('out')
        if not out:
            raise RuntimeError('pull has no data for this league')
        return out['data'], out['meta'], PULL[L['id']]['summary']


T.plan_for = plan_for
T.FullTime = FromPull
socket.gethostname = lambda: 'claude-scheduled (Matt desktop browser)'
full = any(v.get('plan', {}).get('full') for v in PULL.values())
sys.exit(T.run(argparse.Namespace(mode='full' if full else 'matchday', league=None, dry_run=dry, force=False, no_pull=True, verbose=True)))
