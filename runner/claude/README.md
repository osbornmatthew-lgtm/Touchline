# Claude scheduled runs (stand-in for the home runner)

Used while the home runner is not installed on the desktop. Two Claude scheduled tasks on Matt's desktop:
Sundays hourly 12:05 to 17:05 plus 19:05 (match day), Monday 07:50 (full refresh).

Each run: open Full-Time in the desktop app's built-in browser, set `window.__tlmode`, run `pull.js`,
save `window.__tlres` gzipped to Downloads, stage it into the cloud session, then
`python3 runner/claude/publish.py <file>` which runs the normal runner code (same plans, checks, build and publish).

Turn these tasks off before installing the home runner, so two things don't publish at once.
