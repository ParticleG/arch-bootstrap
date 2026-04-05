#!/bin/bash
# Quick bootstrap script for arch-bootstrap
# Usage: curl -sL <short-url> | bash
set -euo pipefail

REPO="ParticleG/arch-bootstrap"
ARCHIVE="arch-bootstrap.sh"
URL="https://github.com/${REPO}/releases/latest/download/${ARCHIVE}"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

echo "Downloading arch-bootstrap..."
if ! curl -sfLo "${TMPDIR}/${ARCHIVE}" "${URL}"; then
  echo "Error: failed to download from ${URL}" >&2
  echo "Check your network connection or visit https://github.com/${REPO}/releases" >&2
  exit 1
fi

chmod +x "${TMPDIR}/${ARCHIVE}"
exec bash "${TMPDIR}/${ARCHIVE}"
