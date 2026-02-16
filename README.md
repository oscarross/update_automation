# update_automation

Bash script to automate updating system Mac OS, application from AppStore, RubyGems and Package in Homebrew

```bash
Usage: ./update.sh [options]

EXAMPLE:
    ./update.sh -a        # Update everything
    ./update.sh -b -g     # Update brew and gem only

OPTIONS:
   -a           Update all (Mac OS, Brew, Gem)
   -b           Brew update
   -g           Gem update
   -m           Mac OS and AppStore update
   -q           Quiet mode (less output)
   -h           Show this help
```
