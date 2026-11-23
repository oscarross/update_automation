#!/usr/bin/env bash
set -euo pipefail

# Auto-disable colors when piped
if [[ -t 1 ]]; then
    CYAN='\033[1;36m'
    GREEN='\033[1;32m'
    YELLOW='\033[1;33m'
    RED='\033[1;31m'
    NC='\033[0m'
else
    CYAN=""
    GREEN=""
    YELLOW=""
    RED=""
    NC=""
fi

OPTIND=1
START_TIME=$(date +%s)

should_update_mac=false
should_update_brew=false
should_update_gem=false
quiet=false
problems=()

# Helper functions
log_info() {
    if [[ "$quiet" == false ]]; then
        echo -e "${CYAN}$1${NC}"
    fi
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

add_problem() {
    problems+=("$1")
    log_warning "$1"
}

# Two copies of a default gem (e.g. rdoc bundled with Homebrew Ruby and a newer one
# from `gem update`) both get loaded and Ruby prints harmless constant redefinition
# warnings on every gem command. Hide only those lines.
GEM_NOISE='/gems/.*: warning: (already initialized constant|previous definition of) '

gem_run() {
    gem "$@" 2> >(grep -vE "$GEM_NOISE" >&2 || true)
}

check_command() {
    if ! command -v "$1" &>/dev/null; then
        log_warning "$1 not installed, skipping..."
        return 1
    fi
    return 0
}

mac_action() {
    if check_command mas; then
        log_info "🖥  MAS upgrade applications from AppStore 🖥"
        mas upgrade
    fi
    check_command softwareupdate || return 0
    log_info "🖥  Mac OS upgrade 🖥"
    # softwareupdate needs root; skip (instead of aborting) when sudo is unavailable
    if sudo -v; then
        sudo softwareupdate --install --all
    else
        log_warning "No sudo access, skipping macOS system update"
    fi
}

cask_upgrade_all() {
    local cask outdated
    local casks=()
    local failed=()

    if ! outdated=$(brew outdated --cask --greedy --quiet); then
        add_problem "brew outdated --cask failed, skipping cask upgrade"
        return 0
    fi
    # Read the list up front so brew/installers can't consume it from stdin.
    while IFS= read -r cask; do
        [[ -n "$cask" ]] && casks+=("$cask")
    done <<< "$outdated"

    # Upgrade casks one by one so a single failing cask doesn't stop the rest.
    # Self-updating apps (auto_updates) can leave stale Caskroom staging dirs,
    # which makes the normal upgrade fail; fall back to a forced install.
    for cask in ${casks[@]+"${casks[@]}"}; do
        if brew upgrade --cask "$cask"; then
            continue
        fi
        log_warning "Upgrade of $cask failed, retrying with forced install..."
        if ! brew install --cask --force "$cask"; then
            failed+=("$cask")
        fi
    done

    if (( ${#failed[@]} > 0 )); then
        log_error "Cask upgrade failed for: ${failed[*]}"
        problems+=("Cask upgrade failed for: ${failed[*]}")
    fi
}

brew_action() {
    check_command brew || return 0
    log_info "🍺 BREW update 🍺"
    brew update
    log_info "🍺 BREW upgrade 🍺"
    brew upgrade --formula || add_problem "brew upgrade --formula reported errors"
    log_info "🍺 BREW CASK upgrade 🍺"
    cask_upgrade_all
    log_info "🍺 BREW cleanup 🍺"
    brew cleanup
}

gem_action() {
    check_command gem || return 0

    local gem_dir
    gem_dir=$(gem env gemdir 2>/dev/null || true)
    if [[ "$gem_dir" == /Library/Ruby/* || "$gem_dir" == /System/Library/* ]]; then
        log_warning "gem is using macOS system Ruby ($gem_dir), which is not writable without sudo."
        log_warning "Install Ruby via Homebrew instead: brew install ruby"
        return 0
    fi

    # Homebrew Ruby: RubyGems is updated by `brew upgrade ruby`, and
    # `gem update --system` fails on the read-only Cellar files.
    local ruby_exe brew_prefix=""
    ruby_exe=$(gem env 2>/dev/null | sed -n 's/^ *- RUBY EXECUTABLE: //p' || true)
    command -v brew &>/dev/null && brew_prefix=$(brew --prefix 2>/dev/null || true)
    if [[ -n "$brew_prefix" && ( "$ruby_exe" == "$brew_prefix/"* || "$gem_dir" == "$brew_prefix/"* ) ]]; then
        log_info "💎 GEM update system skipped (Homebrew Ruby, updated by brew upgrade ruby) 💎"
    else
        log_info "💎 GEM update system 💎"
        gem_run update --system || add_problem "gem update --system failed"
    fi

    # Stale plugin symlinks can point into the read-only Cellar and block reinstalls.
    # -w follows the link, so this removes broken links and links to read-only files.
    local link
    if [[ -n "$gem_dir" && -d "$gem_dir/plugins" ]]; then
        while IFS= read -r link; do
            [[ -w "$link" ]] || rm -f "$link" || true
        done < <(find "$gem_dir/plugins" -type l)
    fi

    log_info "💎 GEM update 💎"
    gem_run update
    log_info "💎 GEM cleanup 💎"
    gem_run cleanup
}

show_summary() {
    local END_TIME
    END_TIME=$(date +%s)
    local DURATION=$((END_TIME - START_TIME))
    local MINUTES=$((DURATION / 60))
    local SECS=$((DURATION % 60))
    
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✨ Update completed in ${MINUTES}m ${SECS}s${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if (( ${#problems[@]} > 0 )); then
        echo ""
        log_warning "Finished with ${#problems[@]} problem(s):"
        local p
        for p in "${problems[@]}"; do
            echo "   - $p"
        done
        return 1
    fi
}

show_help() {
    cat <<EOF
Usage: $0 [options]

EXAMPLE:
    $0 -a        # Update everything
    $0 -b -g     # Update brew and gem only

OPTIONS:
   -a           Update all (Mac OS, Brew, Gem)
   -b           Brew update
   -g           Gem update
   -m           Mac OS and AppStore update
   -q           Quiet mode (less output)
   -h           Show this help
EOF
}

if [[ $# -eq 0 ]]; then
    show_help
    exit 0
fi

while getopts "habgmq" opt; do
    case "$opt" in
    h)
        show_help
        exit 0
        ;;
    a)
        should_update_mac=true
        should_update_brew=true
        should_update_gem=true
        ;;
    b)
        should_update_brew=true
        ;;
    g)
        should_update_gem=true
        ;;
    m)
        should_update_mac=true
        ;;
    q)
        quiet=true
        ;;
    *)
        show_help
        exit 1
        ;;
    esac
done

if ! $should_update_mac && ! $should_update_brew && ! $should_update_gem; then
    show_help
    exit 0
fi

if $should_update_mac; then
    mac_action
fi

if $should_update_brew; then
    brew_action
fi

if $should_update_gem; then
    gem_action
fi

show_summary
