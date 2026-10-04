"""Watchdog: fail (so GitHub emails Matt) if a league has had no successful update for too long on a Sunday.

Run by .github/workflows/watchdog.yml every 15 minutes on Sundays. Reads status.json from the 'status'
branch, which the home runner rewrites after every run. Catches a dead box, a dead broadband line, a
Full-Time block or a broken scraper alike, because it checks the result, not the machine.

    python runner/watchdog.py status.json
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LDN = ZoneInfo('Europe/London')
ROOT = Path(__file__).resolve().parent.parent


def main():
    cfg = json.loads((ROOT / 'config' / 'leagues.json').read_text(encoding='utf-8'))
    a = cfg.get('alerts', {})
    limit = timedelta(minutes=a.get('stale_minutes', 45))
    start, end = (datetime.strptime(x, '%H:%M').time() for x in a.get('window', ['10:00', '18:00']))
    fake = os.environ.get('TOUCHLINE_NOW')
    now = datetime.fromisoformat(fake).replace(tzinfo=LDN) if fake else datetime.now(LDN)
    # Only on Sundays, and only once the first runs of the day have had time to happen.
    first_due = (datetime.combine(now.date(), start, LDN) + limit)
    if now.weekday() != 6 or now < first_due or now.time() > end:
        print(f'{now:%a %H:%M}: outside the Sunday watch window, nothing to check')
        return 0
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not path or not path.exists():
        return alert(a, 'Touchline: no status.json found', 'The home runner has never reported, or the status branch is missing.')
    st = json.loads(path.read_text(encoding='utf-8'))
    late = []
    for L in cfg['leagues']:
        if not L.get('enabled', True):
            continue
        s = st.get('leagues', {}).get(L['id'], {})
        last = s.get('last_success')
        age = now - datetime.fromisoformat(last).astimezone(LDN) if last else None
        if age is None or age > limit:
            when = datetime.fromisoformat(last).astimezone(LDN).strftime('%a %H:%M') if last else 'never'
            late.append(f'{L["code"]}: last good update {when}' + (f' ({s["error"]})' if s.get('error') else ''))
        else:
            print(f'{L["code"]}: fine, last good update {int(age.total_seconds() // 60)} minutes ago')
    heard = datetime.fromisoformat(st['updated']).astimezone(LDN) if st.get('updated') else None
    if heard and now - heard > limit:
        late.append(f'the home machine last reported at {heard:%a %H:%M}; it may be off, asleep or offline')
    if late:
        return alert(a, 'Touchline results are not updating', '\n'.join(late))
    return 0


def alert(a, title, body):
    print(f'::error::{title}: ' + body.replace('\n', '; '))
    topic = os.environ.get('NTFY_TOPIC') or a.get('ntfy_topic')
    if topic:
        try:
            urllib.request.urlopen(urllib.request.Request(f'https://ntfy.sh/{topic}', data=body.encode(), method='POST',
                                                          headers={'Title': title, 'Priority': 'high', 'Tags': 'warning'}), timeout=15)
        except Exception as e:
            print(f'phone alert failed: {e}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
