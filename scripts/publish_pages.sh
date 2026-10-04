#!/bin/sh
# Push a built site to the gh-pages branch. Usage: publish_pages.sh <site-folder> "<message>" [eja|bcfa]
# EJA is the root of the branch; BCFA lives in bcfa/. Each publish leaves the other league alone.
set -e
SITE=$(cd "$1" && pwd); W=$(mktemp -d)
git clone -q --depth 1 -b gh-pages https://github.com/osbornmatthew-lgtm/Touchline.git "$W"
cd "$W"
if [ "${3:-eja}" = bcfa ]; then git rm -rq --ignore-unmatch bcfa; mkdir -p bcfa; cp -r "$SITE"/. bcfa/; rm -f bcfa/_headers bcfa/.nojekyll
else git rm -rq -- . ":(exclude)bcfa"; cp -r "$SITE"/. .; rm -f _headers; fi
git add -A
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -qm "$2" && git push -q origin gh-pages 2>&1 | grep -v "moved\|github.com/osborn\|^remote: *$" || true
rm -rf "$W"; echo published
