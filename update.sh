#!/usr/bin/env bash

CYAN='\033[1;36m'
NC='\033[0m' # No Color

OPTIND=1

should_update_mas=false
should_update_brew=false
should_update_gem=false

mas_action() {
	echo -e "${CYAN}🖥  MAS upgrade 🖥${NC}"
	mas upgrade
}

brew_action() {
	echo -e "${CYAN}🍺 BREW update 🍺${NC}"
	brew update
	echo -e "${CYAN}🍺 BREW upgrade 🍺${NC}"
	brew upgrade
	echo -e "${CYAN}🍺 BREW cleanup 🍺${NC}"
	brew cleanup
	echo -e "${CYAN}🍺 BREW cask cleanup 🍺${NC}"
	brew cask cleanup
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
cat << EOF
Usage: $0 [options]
EXAMPLE:
    $0 -a
OPTIONS:
   -a           Update all
   -b           Brew update
   -g           Gem update
   -h           Help
   -m           Mas update
EOF
}

if [[ ! $@ =~ ^\-.+ ]]
then
	show_help
    exit 0
fi

while getopts "habgm:" opt; 
do
    case "$opt" in
    h)
        show_help
        exit 0
        ;;
    a)  
		should_update_mas=true
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
		should_update_mas=true
        ;;
    esac
done

if $should_update_mas; then
    mas_action
fi

if $should_update_brew; then
    brew_action
fi

if $should_update_gem; then
    gem_action
fi
