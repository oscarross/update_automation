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

## TUI

Interactive terminal UI (Python 3, stdlib `curses`, no dependencies):

```bash
./update_tui.py          # manage real updates
./update_tui.py --demo   # try the UI with fake tasks
```

Keys: `↑/↓` move, `space` toggle, `a`/`n` select all/none, `Enter` run selected,
`c` list outdated for the highlighted task, `x` stop, `PgUp/PgDn` scroll log, `q` quit.
Tasks whose tool is not installed are shown as `missing` and cannot be selected.
