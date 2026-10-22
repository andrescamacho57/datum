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

## Habits Worth Keeping

- Look before you load: count, peek, measure, checksum
- `unzip -l` before `unzip`; `df -h` before anything big
- Delete large local copies once they're safely in Snowflake
- When two tools disagree, look at the bytes (`od -c`)
