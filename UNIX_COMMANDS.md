# Unix / Terminal Command Reference — Datum

Everything I've actually used on Datum, with what it does and why.
Run in the **VS Code terminal** (zsh on macOS). The basics (`cd`, `ls`, pipes) are
in credit-stream's `UNIX_COMMANDS.md`; this file adds what Datum needed.

**Reading a command:** the first word is the program; words starting with `-` are
**flags** (options); the rest are **arguments** (what to act on). `~` = my home folder
(`/Users/anfelca2`). `$( )` = run the command inside and paste its output here.
`|` = pipe: send the output of the left command into the right one. `>` = write
output to a file (overwrites). Quotes keep spaces and special characters together.

---

## Downloading: SFTP

| Command | Does |
|---|---|
| `sftp Public@sftp.floridados.gov` | Open an SFTP session as user `Public` on the state's server |
| `ls -l` (inside sftp) | List remote files with sizes |
| `cd doc/quarterly/cor` | Move to a remote folder |
| `lcd ~/datum/data/raw/sunbiz/quarterly` | **L**ocal `cd`: where downloads land on my laptop |
| `get cordata.zip` | Download one file |
| `bye` | Close the session |

First connection asks to trust the server's host key → `yes` stores it in
`~/.ssh/known_hosts` (trust on first use). **No `#` comments on sftp lines** — sftp
reads them as part of the command.

---

## Inspecting a File Before Loading

| Command | Does | Datum result |
|---|---|---|
| `ls -lh file` | Size, **h**uman-readable | daily 1.1M |
| `wc -l file` | **W**ord **c**ount, `-l` = lines only | 834 |
| `head -c 300 file` | First 300 bytes (`-c` = bytes, not lines) | First record visible |
| `awk '{print length($0)}' file \| sort -n \| uniq -c` | Length of every line → sorted → counted | 834 lines of 1436 (awk stops at NUL) |
| `head -c 1440 file \| od -c \| tail -5` | Show raw bytes, `-c` = as characters | `\0 \0 \0 \0` padding |
| `unzip -l cordata.zip` | List a zip's contents without extracting | 10 files ≈ 1.87 GB each |
| `unzip cordata.zip` | Extract | 18.7 GB |
| `wc -l cordata*.txt` | Lines in each file + total | 12,987,601 |
| `md5 cordata6.txt cordata8.txt` | Checksum each file | Different → not duplicates |
| `df -h ~` | **D**isk **f**ree space, human-readable | 94% used |

**Size ÷ lines = line length** for a fixed-width file. That's how CRLF (1442) was
found without opening an 18.7 GB file.

**Don't** run `cut | sort | uniq -c` or `awk` across 18.7 GB on a laptop — it stalls.
Count in Snowflake after loading instead. Right tool for the size.

---

## Installing Tools

| Command | Does |
|---|---|
| `brew install pipx` | Homebrew installs pipx |
| `pipx install snowflake-cli --python python3.12` | Install `snow` in its own environment, built on Python 3.12 |
| `pipx ensurepath` | Add pipx's bin folder to PATH so `snow` is found |
| `which -a snow` | Every place on PATH where `snow` exists |
| `snow --version` | Confirm it runs |

**PATH** — the list of folders the shell searches for a command name. "command not
found" usually means the program's folder isn't on PATH.

---

## Snowflake CLI

| Command | Does |
|---|---|
| `snow connection add` | Interactive: save a named connection to `~/.snowflake/connections.toml` |
| `snow connection test -c datum` | Prove the `datum` connection works |
| `snow sql -c datum -q "..."` | Run one statement (`-q` = query) |
| `snow sql -c datum -f file.sql` | Run a script (`-f` = file) |

`$PWD` inside the double quotes is replaced by the current folder's path before
`snow` sees it — that's why PUT gets an absolute `file://` path.

---

## Permissions & Ownership

| Command | Does |
|---|---|
| `ls -ld ~/.config` | Show the folder *itself* (`-d`), not its contents, long format (`-l`) |
| `whoami` | Print my username — literally "who am I" |
| `sudo chown -R "$(whoami)" ~/.config` | Change owner to me, **R**ecursively, as superuser |

Reading `ls -l`: `drwxr-xr-x  5 root  staff  160 Jul  4  2024 .config`
→ type+permissions · link count · **owner** · group · size · modified date · name.

---

## Git & GitHub CLI

| Command | Does |
|---|---|
| `git status` | What changed since the last commit |
| `git add <files>` | Stage files for the next commit |
| `git commit -m "msg"` | Save a snapshot |
| `git push` | Send commits to GitHub (`origin`) |
| `git remote -v` | Show where `origin` points |
| `gh auth login` | Log the GitHub CLI in |
| `gh auth status` | Confirm the login persisted |

`data/` is in `.gitignore` — **raw data never goes to git.**

---

## Added Nov 4–6

| Command | What it does |
|---|---|
| `sftp> ls 202611*` | On the SFTP server: list only November 2026 files (`*` = anything after) |
| `sftp> pwd` | Show which folder you're in *on the server* |
| `for z in *.zip; do unzip -l "$z"; done` | List what's inside every zip without extracting; the date column is the snapshot date |
| `awk '{print length($0)}' FILE \| sort -n \| uniq -c` | Count lines by length: one length = clean fixed-width file |
| `grep -c "LLC" FILE` | Count lines containing text (`-c` = count) |
| `git check-ignore -v .env` | Ask git whether a file is ignored, and by which rule |
| `printf '\n.env\n' >> .gitignore` | Append a line safely (`>>` appends; `>` would erase the file) |
| `unset NAME` / `echo "${NAME:-not set}"` | Remove a variable from this shell / print it or a fallback |
| `git log --oneline -5` | Last 5 commits, one line each |
| `git status` | Also says "ahead of origin/main by N" (N unpushed commits) or "up to date" |
| `curl -fsSL https://claude.ai/install.sh \| bash` | Install the Claude Code CLI (native installer) |
| `claude --version` / `claude doctor` | Check the install / read-only health check |
| `ruff check src` | Lint the Python in `src/` with the rules in `ruff.toml` |
| `bash tests/hooks/test_block_secrets.sh` | Run a shell-script test |

**Gotcha:** zsh globs are case-sensitive. `*.txt` does not match `FLRF.TXT`; use `*.(txt|TXT)` or list both.

---

## Symbolic Links and Moved Folders (Nov 18)

```bash
ln -s "$HOME/Work Streams/datum" "$HOME/datum"   # make ~/datum a signpost to the repo's new home
ls -l ~/datum                                    # shows: datum -> /Users/anfelca2/Work Streams/datum
```

- `ln` makes a link; `-s` makes it **symbolic** (a pointer by path, not a second copy of the data)
- First argument = what it points to; second = where the signpost goes
- Quotes keep `Work Streams` together; unquoted, the shell sees two arguments
- `rm ~/datum` removes only the signpost, never the folder it points to

## Counting Without a Warehouse (Nov 18)

```bash
LC_ALL=C awk -F'|' '$1=="DPA" { n[$5]++ } END { for (k in n) print k, n[k] }' p*.16
```

- `awk -F'|'` splits each line on the pipe character; `$1`, `$5` are the 1st and 5th fields
- `n[$5]++` is a tally keyed by the field's value (here FRM / TO); `END { ... }` runs after the last line
- `LC_ALL=C` treats the file as plain bytes, so odd characters can't stop it

## Added Nov 20–23: keys, branches and long runs

```bash
[ -n "$ANTHROPIC_API_KEY" ] && echo "SET somewhere" || echo "not set - good"
grep -l ANTHROPIC_API_KEY ~/.zshrc ~/.zprofile ~/.zshenv 2>/dev/null
grep -c "W10" docs/prompts/florida_master.md
env -u ANTHROPIC_API_KEY claude rc
caffeinate -is
git switch main
git fetch && git status
git worktree add --detach ~/datum-review origin/main
```

- `[ -n "$VAR" ]` tests whether a variable is not empty. `&&` runs the next part if the test passed, and
  `||` runs it if the test failed. It prints a label and never the secret
- `grep -l` prints only the names of the files that match, so a key never appears on screen. `grep -c`
  prints how many lines matched. `2>/dev/null` hides "no such file" errors
- `env -u NAME command` runs one command with that variable removed
- `claude rc` is a hidden short name for `claude remote-control`, the server mode: the terminal only waits for
  your phone or a browser to connect, and you can't type in it. `claude --remote-control` (or `--rc`) instead
  starts a normal session that you can type in and also reach from your phone, and `/rc` turns that on inside
  a session already running. The docs list only the long names
  ([Claude Code docs, Remote Control](https://code.claude.com/docs/en/remote-control))
- `caffeinate -is` keeps the Mac awake while it runs: `-i` stops idle sleep, and `-s` stops system sleep, but
  only while the Mac is plugged in. Neither keeps it awake with the lid closed. Stop it with Ctrl+C
- `git switch <branch>` changes the checked-out branch. Never run it in a folder an agent is working in
- `git fetch && git status` says how far behind the branch is, without changing a file
- `git worktree add --detach <folder> origin/main` makes a second working folder for the same repo, at `main`
  as of your last `git fetch`. It doesn't contact GitHub itself, so run `git fetch` first. Git refuses a
  branch that another folder already has checked out, and
  `--detach` avoids that by checking out the commit without a branch

## Added Nov 26: where an environment variable comes from

```bash
echo ${ANTHROPIC_API_KEY:+set}
grep -rl ANTHROPIC_API_KEY ~/.zshrc ~/.zprofile ~/.zshenv ~/.oh-my-zsh/custom 2>/dev/null
```

- `${NAME:+set}` prints the word `set` when the variable has a value and prints nothing when it does not,
  so you can check a secret without ever showing it
- `grep -r` searches inside folders as well as files, and with `-l` it prints only the names of the files
  that match, never the matching line
- Run the same `echo` check in two places to find where a value comes from: the VS Code terminal and the
  macOS Terminal app. If only VS Code has it, VS Code is carrying an environment it copied when it started.
  If both have it, a startup file sets it
- Closing a VS Code window does not stop VS Code. Cmd+Q quits it, and only a fresh start copies a fresh
  environment

## Habits Worth Keeping

- Look before you load: count, peek, measure, checksum
- `unzip -l` before `unzip`; `df -h` before anything big
- Delete large local copies once they're safely in Snowflake
- When two tools disagree, look at the bytes (`od -c`)
- Globs are case-sensitive: check that a loop actually covered every file
- Long prompts go in a file (`docs/prompts/`), not the terminal paste buffer
- A check that can't fail proves nothing: ask what input would make it fail
- Don't move a folder that holds a `.venv`; if you must, leave a symbolic link at the old path
- Before a session on the Mac: `git switch main`, then `git pull`
- While an agent works in a folder, only read with git there (`status`, `log`, `diff`)
- A program's environment is a copy made when it started: after changing a startup file, restart the program
