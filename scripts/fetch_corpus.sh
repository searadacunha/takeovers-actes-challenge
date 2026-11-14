#!/bin/sh
# Fetch the challenge corpus at the commit the ledger was reviewed against.
set -eu
cd "$(dirname "$0")/.."
COMMIT=a705bcc86614c8552cc4270c762a6a6399c751ba
[ -d upstream/.git ] || git clone https://github.com/takeovers-ai/engineering-challenges.git upstream
git -C upstream fetch -q origin "$COMMIT"
git -C upstream checkout -q "$COMMIT"
echo "corpus ready in upstream/data at $COMMIT"
