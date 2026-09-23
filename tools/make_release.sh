#!/usr/bin/env sh
# Build the submission archive of the committed version with a SHA-256 checksum.
# Usage: sh tools/make_release.sh   ->  release/marshrut-<commit>.zip + .sha256
set -eu
cd "$(dirname "$0")/.."
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree has uncommitted changes; commit them first." >&2
  exit 1
fi
commit=$(git rev-parse --short HEAD)
mkdir -p release
archive="release/marshrut-${commit}.zip"
git archive --format=zip --prefix="marshrut-${commit}/" -o "$archive" HEAD
if command -v sha256sum >/dev/null 2>&1; then
  (cd release && sha256sum "$(basename "$archive")" > "$(basename "$archive").sha256")
else
  (cd release && shasum -a 256 "$(basename "$archive")" > "$(basename "$archive").sha256")
fi
echo "Commit:   $(git rev-parse HEAD)"
echo "Archive:  $archive"
echo "SHA-256:  $(cut -d' ' -f1 "$archive.sha256")"
