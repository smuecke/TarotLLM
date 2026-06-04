#!/usr/bin/env bash
set -euo pipefail

IMAGE_ARCHIVE_URL="https://cloud.smuecke.de/api/public/dl/3w2z50SQ"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_PATH="$(mktemp "${TMPDIR:-/tmp}/tarot-images.XXXXXX.zip")"

cleanup() {
  rm -f "$ARCHIVE_PATH"
}
trap cleanup EXIT

if command -v curl >/dev/null 2>&1; then
  curl --fail --location --output "$ARCHIVE_PATH" "$IMAGE_ARCHIVE_URL"
elif command -v wget >/dev/null 2>&1; then
  wget --output-document="$ARCHIVE_PATH" "$IMAGE_ARCHIVE_URL"
else
  echo "Neither curl nor wget is installed." >&2
  exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "unzip is not installed." >&2
  exit 1
fi

unzip -o "$ARCHIVE_PATH" -d "$SCRIPT_DIR"
