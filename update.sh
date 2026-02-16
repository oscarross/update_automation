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

# Helper functions
log_info() {
    [[ "$quiet" == false ]] && echo -e "${CYAN}$1${NC}"
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
    log_info "🖥  Mac OS upgrade 🖥"
    softwareupdate --install --all
}

brew_action() {
    check_command brew || return 0
    log_info "🍺 BREW update 🍺"
    brew update
    log_info "🍺 BREW upgrade 🍺"
    brew upgrade
    log_info "🍺 BREW CASK upgrade 🍺"
    brew upgrade --cask --greedy
    log_info "🍺 BREW cleanup 🍺"
    brew cleanup
}

gem_action() {
    check_command gem || return 0
    log_info "💎 GEM update system 💎"
    gem update --system
    log_info "💎 GEM update 💎"
    gem update
    log_info "💎 GEM cleanup 💎"
    gem cleanup
}

show_summary() {
    local END_TIME=$(date +%s)
    local DURATION=$((END_TIME - START_TIME))
    local MINUTES=$((DURATION / 60))
    local SECONDS=$((DURATION % 60))
    
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✨ Update completed in ${MINUTES}m ${SECONDS}s${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

if [[ $# -eq 0 ]] || [[ ! $@ =~ ^\-.+ ]]; then
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
