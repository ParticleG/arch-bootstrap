#!/usr/bin/env bash
# Remove the makepkg download proxy deployed by arch-bootstrap.
set -euo pipefail

uninstall_github_proxy_dl() {
    local root="${1%/}"
    local config="$root/etc/makepkg.conf"
    local wrapper="$root/usr/local/bin/github-proxy-dl"
    local proxy_agent="'https::/usr/local/bin/github-proxy-dl %u %o'"
    local curl_agent="'https::/usr/bin/curl -qgb \"\" -fLC - --retry 3 --retry-delay 3 -o %o %u'"

    if [[ -e "$config" ]]; then
        local content
        content=$(cat -- "$config")
        if [[ ${content//"$proxy_agent"/} == *'/usr/local/bin/github-proxy-dl'* ]]; then
            printf 'Cannot safely restore a modified github-proxy-dl reference in %s. No changes made.\n' "$config" >&2
            return 1
        fi
        if [[ "$content" == *"$proxy_agent"* ]]; then
            sed -i "s|$proxy_agent|$curl_agent|g" "$config"
            printf 'Restored the HTTPS download agent to curl in %s.\n' "$config"
        else
            printf 'No github-proxy-dl download agent found in %s.\n' "$config"
        fi
    else
        printf 'No makepkg configuration found at %s.\n' "$config"
    fi

    rm -f -- "$wrapper"
    printf 'Removed %s (if present).\n' "$wrapper"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    if (( $# != 0 )); then
        printf 'Usage: sudo bash %s\n' "$0" >&2
        exit 1
    fi
    if (( EUID != 0 )); then
        printf 'Run this script with sudo or as root.\n' >&2
        exit 1
    fi
    uninstall_github_proxy_dl /
fi
