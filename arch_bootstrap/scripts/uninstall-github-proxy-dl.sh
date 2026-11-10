#!/usr/bin/env bash
# Remove the GitHub download and Git proxies deployed by arch-bootstrap.
set -euo pipefail

remove_github_git_proxy() {
    local config="$1"
    [[ -f "$config" ]] || return 0

    local -a git_config=(git config --file "$config")
    if (( EUID == 0 )) && [[ ! -O "$config" ]]; then
        # Git replaces the config via a lock file; keep user files user-owned.
        git_config=(runuser -u "$(stat -Lc %U -- "$config")" -- "${git_config[@]}")
    fi

    # NUL-delimited records preserve spaces; deduplicate repeated config values.
    "${git_config[@]}" --null --list | sort -zu |
        while IFS= read -r -d '' entry; do
            local key="${entry%%$'\n'*}"
            local value="${entry#*$'\n'}"
            local target
            case "$key" in
                url.*.insteadof)
                    target="${key#url.}"
                    target="${target%.insteadof}"
                    if [[ "$value" == 'https://github.com/' ]] &&
                        [[ "$target" == https://*/https://github.com/ ||
                           "$target" == http://*/https://github.com/ ]]; then
                        "${git_config[@]}" --fixed-value --unset-all "$key" "$value"
                        printf 'Removed GitHub proxy rewrite from %s.\n' "$config"
                    fi
                    ;;
                remote.*.url|remote.*.pushurl)
                    case "$value" in
                        https://*/https://github.com/*|http://*/https://github.com/*)
                            target="https://github.com/${value#*/https://github.com/}"
                            "${git_config[@]}" --fixed-value --replace-all "$key" "$target" "$value"
                            printf 'Restored %s to %s in %s.\n' "$key" "$target" "$config"
                            ;;
                    esac
                    ;;
            esac
        done
}

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

    local git_config home git_dir
    for git_config in "$root/etc/gitconfig" "$root/etc/makepkg.d/gitconfig"; do
        remove_github_git_proxy "$git_config"
    done

    for home in "$root/root" "$root"/home/*; do
        [[ -d "$home/.oh-my-zsh" ]] || continue
        find "$home/.oh-my-zsh" -type d -name .git -prune -print0 |
            while IFS= read -r -d '' git_dir; do
                remove_github_git_proxy "$git_dir/config"
            done
    done
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
