#!/bin/bash
# Quick bootstrap script for arch-bootstrap (China mainland)
# Resolves the latest available GitHub proxy from https://ghproxy.link/
# Usage: curl -sL <short-url> | bash
set -euo pipefail

REPO="ParticleG/arch-bootstrap"
ARCHIVE="arch-bootstrap.sh"
GITHUB_URL="https://github.com/${REPO}/releases/latest/download/${ARCHIVE}"

# Hardcoded fallback proxy (update manually if it gets blocked)
FALLBACK_PROXY="https://ghfast.top"

# ─── Resolve latest available proxy from ghproxy.link ───
# The publish page (https://ghproxy.link/) is a Vue SPA. Domain status is
# embedded in a webpack JS chunk as static HTML inside createStaticVNode().
# Available domains use <a href="URL">, blocked ones use <del>URL</del>.
_resolve_ghproxy() {
  local chunk_url="https://ghproxy.link/js/src_views_home_HomeView_vue.js"
  local content proxy

  content=$(curl -sf --connect-timeout 5 --max-time 10 "$chunk_url") || return 1

  # In the bundle, href attributes are escaped as href=\\\"URL\\\".
  # Match href= followed by up to 5 chars of escaping, then a proxy URL.
  proxy=$(printf '%s' "$content" \
    | grep -oP 'href=.{0,5}https://gh[a-z0-9]+\.[a-z]+' \
    | grep -oP 'https://gh[a-z0-9]+\.[a-z]+' \
    | head -1)

  [[ -n "$proxy" ]] && echo "$proxy" && return 0
  return 1
}

# ─── Verify a proxy can actually reach GitHub releases ───
_test_proxy() {
  local proxy="$1"
  # HEAD request to the actual download URL; a 302 redirect means the proxy works.
  # Note: proxy services often block browsing pages (/releases) with 403,
  # so we must test the real download path instead.
  local http_code
  http_code=$(curl -sI --connect-timeout 5 --max-time 10 \
    "${proxy}/${GITHUB_URL}" \
    -o /dev/null -w "%{http_code}" 2>/dev/null) || return 1
  # 2xx or 3xx means the proxy is functional
  [[ "$http_code" =~ ^[23] ]]
}

# ─── Resolve proxy with fallback chain ───
echo "Resolving GitHub proxy..."

PROXY=""

# Step 1: Try to get the latest proxy from ghproxy.link
if resolved=$(_resolve_ghproxy 2>/dev/null); then
  echo "  Found proxy: ${resolved}"
  if _test_proxy "$resolved"; then
    PROXY="$resolved"
    echo "  Proxy is reachable."
  else
    echo "  Proxy resolved but unreachable, trying fallback..."
  fi
else
  echo "  Could not reach ghproxy.link, trying fallback..."
fi

# Step 2: Try hardcoded fallback
if [[ -z "$PROXY" ]]; then
  echo "  Trying fallback: ${FALLBACK_PROXY}"
  if _test_proxy "$FALLBACK_PROXY"; then
    PROXY="$FALLBACK_PROXY"
    echo "  Fallback proxy is reachable."
  else
    echo "  Fallback proxy also unreachable."
  fi
fi

# Step 3: Try direct GitHub access as last resort
if [[ -z "$PROXY" ]]; then
  echo "  All proxies failed. Attempting direct GitHub access..."
  if curl -sfI --connect-timeout 10 --max-time 15 \
       "https://github.com/${REPO}/releases" -o /dev/null 2>/dev/null; then
    echo "  Direct access available."
  else
    echo "Error: cannot reach GitHub through any proxy or directly." >&2
    echo "Visit https://ghproxy.link/ for the latest proxy address," >&2
    echo "or download manually from https://github.com/${REPO}/releases" >&2
    exit 1
  fi
fi

# Build final download URL
if [[ -n "$PROXY" ]]; then
  URL="${PROXY}/${GITHUB_URL}"
else
  URL="${GITHUB_URL}"
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

echo "Downloading arch-bootstrap..."
echo "  ${URL}"
if ! curl -fLo "${TMPDIR}/${ARCHIVE}" --connect-timeout 10 --max-time 120 \
     --progress-bar "${URL}"; then
  echo "Error: failed to download from ${URL}" >&2
  echo "Check your network connection or visit https://github.com/${REPO}/releases" >&2
  exit 1
fi

chmod +x "${TMPDIR}/${ARCHIVE}"
exec bash "${TMPDIR}/${ARCHIVE}"
