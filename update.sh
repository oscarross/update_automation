#!/usr/bin/env bash

# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

should_update_mas=false
should_update_brew=false
should_update_gem=false

mas_action() {
	echo -e "\033[31m MAS upgrade"
	mas upgrade
}

brew_action() {
	echo -e "\033[31m BREW update"
	brew update
	echo -e "\033[31m BREW upgrade"
	brew upgrade
	echo -e "\033[31m BREW cleanup"
	brew cleanup
	echo -e "\033[31m BREW cask cleanup"
	brew cask cleanup
}

gem_action() {
	echo -e "\033[31m GEM update system"
	gem update --system
	echo -e "\033[31m GEM update"
	gem update
	echo -e "\033[31m GEM cleanup"
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

while getopts "h?abgm" opt; 
do
    case "$opt" in
    h|\?)
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
