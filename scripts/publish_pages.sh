#!/bin/sh
# Push a built touchline-site folder to the gh-pages branch. Usage: publish_pages.sh <site-folder> "<message>" [repo, default Touchline]
set -e
SITE=$(cd "$1" && pwd); W=$(mktemp -d)
git clone -q --depth 1 -b gh-pages https://github.com/osbornmatthew-lgtm/${3:-Touchline}.git "$W"
cd "$W" && git rm -rq . && cp -r "$SITE"/. . && rm -f _headers && git add -A
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -qm "$2" && git push -q origin gh-pages 2>&1 | grep -v "moved\|github.com/osborn\|^remote: *$" || true
rm -rf "$W"; echo published
