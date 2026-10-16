#!/usr/bin/env bash
# Restore the recordings from this repository's GitHub Release.
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ "${1:-}" == "--verify" ]]; then
  sha256sum -c datasets/data-files.sha256
  exit 0
fi

for dependency in gh sha256sum tar cat; do
  command -v "$dependency" >/dev/null || { echo "Missing dependency: $dependency" >&2; exit 1; }
done
if [[ -e data ]]; then
  echo 'data/ already exists. Use scripts/download_data.sh --verify to check it.' >&2
  exit 1
fi

mkdir -p .download-assets
gh release download data-2026-10-16 --repo xfang8343/A2 \
  --pattern 'data.tar.gz.part*' --dir .download-assets --skip-existing
(
  cd .download-assets
  sha256sum -c ../datasets/archive-parts.sha256
)

parts=()
while read -r checksum filename; do
  parts+=(".download-assets/$filename")
done < datasets/archive-parts.sha256
cat -- "${parts[@]}" | tar -xz --no-same-owner -C "$project_root"
sha256sum -c datasets/data-files.sha256
echo 'All recordings restored and verified. Downloaded parts remain in .download-assets/.'
