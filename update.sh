#!/usr/bin/env bash

CYAN='\033[1;36m'
NC='\033[0m' # No Color

OPTIND=1

should_update_mac=false
should_update_brew=false
should_update_gem=false

mac_action() {
    echo -e "${CYAN}🖥  AppStrone - MAS upgrade 🖥${NC}"
    mas upgrade
    echo -e "${CYAN}🖥  Mac OS upgrade 🖥${NC}"
    softwareupdate --install --all
}

brew_action() {
    echo -e "${CYAN}🍺 BREW update 🍺${NC}"
    brew update
    echo -e "${CYAN}🍺 BREW upgrade 🍺${NC}"
    brew upgrade
    echo -e "${CYAN}🍺 BREW CASK upgrade 🍺${NC}"
    brew upgrade --cask --greedy
    echo -e "${CYAN}🍺 BREW cleanup 🍺${NC}"
    brew cleanup
}

gem_action() {
    echo -e "${CYAN}💎 GEM update system 💎${NC}"
    gem update --system
    echo -e "${CYAN}💎 GEM update 💎${NC}"
    gem update
    echo -e "${CYAN}💎 GEM cleanup 💎${NC}"
    gem cleanup
}

show_help() {
    cat <<EOF
Usage: $0 [options]
EXAMPLE:
    $0 -a
OPTIONS:
   -a           Update all
   -b           Brew update
   -g           Gem update
   -h           Help
   -m           Mac OS and AppStore update
EOF
}

if [[ ! $@ =~ ^\-.+ ]]; then
    show_help
    exit 0
fi

while getopts "habgm:" opt; do
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
