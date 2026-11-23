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

### Error handling

`update.sh` tries to finish as much as possible instead of stopping at the first error:

- **Brew formulae** - `brew upgrade --formula` errors are logged as a warning and the
  script continues.
- **Brew casks** - outdated casks (`brew outdated --cask --greedy`) are upgraded one by
  one, so a single broken cask doesn't block the rest. If an upgrade fails (common with
  self-updating apps that leave stale Caskroom staging dirs), it is retried with
  `brew install --cask --force`. Casks that still fail are listed at the end.
- **Gem with macOS system Ruby** - if `gem` points at the system Ruby (`/Library/Ruby`
  or `/System/Library`), the gem step is skipped, because it can't be written to without
  `sudo`. Install Ruby with `brew install ruby` instead.
- **Gem with Homebrew Ruby** - errors from `gem update --system` are logged as a warning
  (the plugin regeneration step often fails with `EACCES` on the read-only Cellar after
  the update itself worked). Broken or non-writable plugin symlinks in the gem `plugins`
  dir are removed before `gem update`.

Problems are collected and listed after the summary. In that case the script exits with
code `1`, which helps when it runs from cron or another script.

These fallbacks only apply to `update.sh`. The TUI below still runs the plain commands
and stops a group at its first failing step.

## TUI

Interactive terminal UI (Python 3, stdlib `curses`, no dependencies):

```bash
./update_tui.py          # manage real updates
./update_tui.py --demo   # try the UI with fake tasks
```

One entry per group - **Mac** (App Store + softwareupdate), **Brew** (update, upgrade,
cask upgrade, cleanup) and **Gem** (update --system, update, cleanup). Each group runs
its steps in order and stops at the first failure. The UI shows per-step progress, an
overall progress bar and a live log.

Keys: `↑/↓` move, `space` toggle group, `a`/`n` select all/none, `Enter` run selected,
`c` list outdated for the highlighted group, `x` stop, `PgUp/PgDn` scroll log, `q` quit.
Groups whose tools are not installed are shown as `missing` and cannot be selected;
individual missing steps (e.g. `mas`) are skipped.
