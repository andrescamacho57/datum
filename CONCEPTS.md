# Datum — Concepts Reference

Running glossary of what I've learned building Datum.
Terminal commands live separately in `UNIX_COMMANDS.md`; Snowflake and dbt syntax in
their own reference files. **Updated each session.**

How to study this: read a heading, close the file, and explain the concept out loud
in your own words. Then check. If you can't give the "why," you don't own it yet.

---

## The Product in One Breath

**Datum** checks a small trade contractor's commercial client before the job: is it
a real, active company, and what's on the public record against it?

**Why it exists:** contractors get stiffed because their customers default. They
take jobs from companies they can't verify. The public record (state filings,
licenses, liens, courts) already holds the warning signs — it's just scattered.

**What it is not:** a credit product. Businesses only, no consumer data, never an
owner's personal credit. That keeps Datum outside the **FCRA** (Fair Credit Reporting
Act), which governs reports about *people*. Outputs are **sourced facts**, framed as
analysis, never advice. Language matters: "risk and verification," not "credit."

---

## Ingestion Patterns: Bulk File vs API vs Scraping

Three ways to get data from someone else's system, in order of preference:

| Pattern | What it is | When |
|---|---|---|
| **Bulk file** | The publisher dumps the whole dataset as files (often SFTP). You download everything. | They offer it. Complete, cheap, stable. |
| **API** (application programming interface) | You send a request over HTTP, get back a small structured answer (usually JSON). | You need one record on demand, or the source only offers this. |
| **Scraping** | A program reads the human website. | Last resort. Fragile, slow, often against terms of use. |

**Sunbiz** offers bulk files over SFTP, so that's what Datum uses. The search website
sits behind a Cloudflare challenge and the fictitious-name site's `robots.txt`
disallows bots — the bulk file is the compliant route to the same data.

**REST API** (representational state transfer) — the common style of web API. Each
thing has a URL; you `GET` it to read, `POST` to create. A Python script usually
calls one with the `requests` library, pages through results, and handles rate
limits and retries.

**boto3** — the Python library for AWS (Amazon Web Services). It wraps AWS's REST
APIs, so `s3.upload_file(...)` is really an authenticated HTTP request underneath.
Fits credit-stream (which uses S3), not Datum (which doesn't).

**Where Datum will use an API:** CourtListener (federal court and bankruptcy records,
v1.1). Not forced in earlier — bulk files are the better tool where they exist.

---

## Fixed-Width Files

**What:** a text file where every field sits at fixed character positions. No commas,
no tabs. The company name is *always* characters 13–204; if it's shorter, the rest
is padded with spaces.

**Analogy:** a paper form with boxes. You know the zip code is in the 5 boxes at the
bottom right, so you never need a separator — you just read those boxes.

**Record layout** — the document that says which positions hold which field. For
Sunbiz: `cor.html` on the state's site, copied into `docs/access/sunbiz.md`.

**Position arithmetic:** a field's **end = start + length − 1**, and the next field
**starts at start + length**. Document number starts at 1, length 12 → ends at 12,
name starts at 13. Name is 192 long → ends at 204, status is at 205.

**Why it's fragile:** if one stray character slips in early, *every* field after it
shifts. That's why the `accepted_values` test on status (position 205) doubles as a
parsing guard: a shifted line puts junk there instead of A or I.

**Why we don't parse on load:** Snowflake has no fixed-width file type. Standard
approach: load each whole line as one column, cut it into fields later in dbt.

**The schema lives outside the file.** A CSV header row names its own columns. A
fixed-width file names nothing: the layout document *is* the schema, and the
character positions are the column definitions. Lose the layout and the file is
unreadable.

**The `fixed_width` file format** is our own name for a reusable object that holds
Snowflake's reading instructions. Its `TYPE` is CSV, because CSV is Snowflake's
plain-text reader. Each setting turns off a CSV behavior that would damage
positions:

| Setting | CSV default | What the default would break |
|---|---|---|
| `FIELD_DELIMITER = NONE` | `,` | "ACME, INC." splits at the comma and `$1` holds only "ACME". Every later position is lost |
| `ESCAPE_UNENCLOSED_FIELD = NONE` | `\` | A backslash in a name is treated as an escape and eats the next character, shifting the rest of the line left |
| `ENCODING = 'ISO-8859-1'` | UTF-8 | Accented bytes are read as multi-byte characters (or rejected), so character 205 stops being byte 205 |
| `TRIM_SPACE` (left at FALSE) | FALSE | Trimming would remove padding that holds positions |

**One sentence to say out loud:** the file format tells Snowflake to read each line
as one untouched string, so every character stays at the position the layout says
it's in.

---

## Bytes, Characters, and Encodings

**Byte** — 8 bits, a number 0–255. What disks and networks actually store.

**Character** — a letter or symbol a human reads. How many bytes one takes depends on
the **encoding** (the rulebook that maps numbers to characters).

| Encoding | Bytes per character |
|---|---|
| ASCII | 1 (only 128 characters) |
| ISO-8859-1 (Latin-1) | always 1 (256 characters, includes é, ñ) |
| UTF-8 | 1 to 4 |

**Why Datum's file format says `ENCODING = 'ISO-8859-1'`:** in Latin-1, one character
is always one byte. So character position 205 really is byte 205. With UTF-8, one
accented name earlier in a line could make a single character take two bytes and
throw positions off.

---

## Line Endings: LF vs CRLF

The invisible characters that end a line:

- **LF** (line feed, `\n`, byte 10) — Unix/macOS convention
- **CRLF** (carriage return + line feed, `\r\n`, bytes 13 10) — Windows convention

The names come from typewriters: carriage return slides the carriage back to the left,
line feed rolls the paper up one line.

**Datum finding:** the daily file ends lines with LF (1440 + 1 = **1441** bytes per
line on disk); the quarterly files end with CRLF (1440 + 2 = **1442**). I predicted
Snowflake would keep the `\r` and load 1441 characters. **The load proved me wrong:
every line came in at 1440.** Snowflake's default record delimiter treats `\r\n` as
one line ending and strips both. A prediction checked against data, and corrected. The
staging check `length(line) >= 1436` handles both — no code change.

**How I found it without opening an 18.7 GB file:** file size ÷ line count. If every
line is the same length (fixed width), the division is exact and tells you the line
length including its ending.

---

## NUL Padding

**NUL** — the byte with value 0. Not a space (32), not nothing — an actual zero byte,
usually invisible.

**Datum finding:** every Sunbiz record is **1440 bytes = 1436 bytes of content + 4 NUL
bytes**. The published layout only documents 1436. Found it with `od -c` (shows each
byte), where the NULs appear as `\0`.

**Why tools disagreed:** macOS `awk` counted 1436 (it stops at NUL — C strings end at
a zero byte). Snowflake counted 1440 (it keeps them). Same file, two "lengths."
Lesson: when tools disagree, look at the raw bytes.

---

## Units Ladder

Each step up is ÷ 1024 (computer convention):

```
bytes → KB (kilobytes) → MB (megabytes) → GB (gigabytes) → TB (terabytes)
          ÷1024            ÷1024             ÷1024             ÷1024
```

**Reading a big number fast:** group the digits in threes from the right. Each group
is roughly one step. `1,835,409,820` bytes = 4 groups → GB range ≈ 1.8 GB.

**Datum numbers:** quarterly zip 1.7 GB → unzips to 10 files ≈ 1.87 GB each = 18.7 GB.
12,987,601 records × 1442 bytes ≈ 18.7 GB. The arithmetic checks out — that's a
validation in itself.

---

## Checksums (md5)

**What:** a short fingerprint computed from every byte of a file. Change one byte
and the fingerprint changes completely.

**Use:** prove two files are identical (same checksum) or different (different
checksum) without comparing them by eye. Also proves a download wasn't corrupted.

**Datum story:** `cordata6.txt` and `cordata8.txt` had the same size and the same line
count. Looked like a duplicate. `md5` showed different checksums → different files.
**Why the coincidence wasn't two coincidences:** in a fixed-width file, size = lines
× line length. Same line count *forces* same size. One coincidence, not two.

---

## Compression and Archives

**zip** — an *archive* (many files in one) that's also compressed. **Snowflake cannot
read .zip**, so the quarterly `cordata.zip` gets unzipped on the laptop first.

**gzip (.gz)** — compresses one file. Snowflake reads it natively.
`PUT ... AUTO_COMPRESS=TRUE` gzips each file during upload: less to send, less to
store, and `COPY` decompresses on the fly.

**`unzip -l`** lists what's inside a zip without extracting — look before you unpack
18.7 GB onto a nearly full disk.

---

## SFTP and Trust on First Use

**SFTP** (SSH File Transfer Protocol) — file transfer over an encrypted SSH (Secure
Shell) connection. The state publishes a shared public login.

**Trust on first use:** the first time you connect, the server shows its **host key
fingerprint** and asks "are you sure?" Saying yes stores it in `~/.ssh/known_hosts`.
Every later connection checks the server still has the same key; if it changes, SSH
warns loudly (could be an impostor). You trust the first time, verify every time after.

---

## Stages, PUT, and COPY

**Stage** — a holding area for files inside (internal) or outside (external, e.g. S3)
Snowflake. Files sit there until loaded. Referenced with `@`: `@datum.raw.sunbiz_stage`.

**PUT** — uploads a file from your computer to an internal stage. **Only runs from a
client on your machine** (snow CLI, SnowSQL, a driver) — never from a web worksheet,
because the web page can't read your disk.

**COPY INTO** — reads staged files and inserts their rows into a table. Can transform
on the way in with a `SELECT` (that's how `METADATA$FILENAME` and the load time get
added).

**Analogy:** the stage is the loading dock, PUT is the truck delivering boxes, COPY is
unpacking boxes onto shelves.

**PUT runs where the file lives.** The program running PUT has to be able to open
the file. `snow` in the terminal can, because it runs on the Mac. A Snowsight
worksheet can't, because it runs in a browser tab connected to Snowflake's servers.
A `.sql` file containing a PUT works when `snow sql -f` runs it, but `$PWD` isn't
expanded inside a file, so the path has to be written out in full.

**"On the wire"** means the bytes that actually cross the network. With
`AUTO_COMPRESS=TRUE`, gzip runs on the Mac *before* sending, so ~18.7 GB on disk
becomes roughly 1.7 GB on the wire. Compressing first costs a bit of CPU (the
processor's time) and saves a lot of network time.

**`PARALLEL` = upload threads.** It isn't "files at once." Snowflake splits large
files into chunks, and each thread sends chunks. Default is 4; maximum is 99. More
threads help only until something else becomes the bottleneck, usually the home
internet **upload** speed. Analogy: more checkout lanes don't help when the parking
lot exit is one lane. 8 is a modest bump over the default, not a tuned number.

**One stage per file type** (Datum decision): keeps daily and quarterly files from
being swept into the same COPY. Simplest way to keep them separate.

---

## Idempotency and Load Metadata

**Idempotent** — running it twice has the same effect as running it once.

Snowflake remembers which files each table has loaded for **64 days** (load metadata).
Rerun the same `COPY` and it skips files it already loaded → no duplicate rows. That
makes the load script safe to rerun after an error.

**Gotcha:** after 64 days, or with `FORCE = TRUE`, it *will* reload. Don't rely on it
forever.

---

## Provenance

**Provenance** — where a fact came from and when. Datum's raw table carries
`source_file` (`METADATA$FILENAME`) and `loaded_at` from the very first layer, and
every later layer passes them through.

**Why it matters for Datum specifically:** the promise is "every report line links to
its official record." That's only possible if provenance survives every
transformation. It's a product feature, not just hygiene.

---

## Data Warehouse Layers (raw → staging → marts)

| Layer | Holds | Rule | Datum |
|---|---|---|---|
| **Raw** | Data exactly as received | Never edit | One line per row |
| **Staging** | Cleaned, renamed, typed | One model per source table, no business logic | Lines cut into columns |
| **Marts** | Business-ready | Shaped for a use | One row per company, searchable |

**Analogy:** raw is the grocery bag, staging is washed and chopped ingredients,
marts are the plated dish.

**Why raw stays untouched:** if staging has a bug (a wrong position), you fix one SQL
file and rebuild. Nothing has to be re-downloaded or reloaded.

---

## Grain

**Grain** — what exactly one row represents. Say it before writing any model.

- `raw.sunbiz_cor_daily`: one line of one state file
- `entity_lookup`: one company (`document_number`)

The `unique` test on `document_number` **is** the grain, written down and enforced.

---

## Deduplication with QUALIFY + ROW_NUMBER

The same company can appear in several files (it filed again, changed address). The
mart needs one row per company: the newest.

```sql
qualify row_number() over (partition by document_number order by loaded_at desc) = 1
```

- `partition by document_number` — split rows into groups, one group per company
- `order by loaded_at desc` — inside each group, newest first
- `row_number()` — number them 1, 2, 3 within the group
- `qualify ... = 1` — keep only row 1 per group

`QUALIFY` is to window functions what `WHERE` is to columns and `HAVING` is to
aggregates. Snowflake supports it; not every database does.

**Open issue:** `loaded_at` is when *I* loaded it, not when the state published it.
Loading the Oct 7 quarterly after the Oct 9 daily would wrongly make the older data
"newest." Fix: order by a date that comes from the state's file.

---

## Normalization and Regex

**Normalization** — transforming values so things that mean the same compare equal.
"Acme, Inc." and "ACME INC" are the same company to a human, not to `=`.

Datum's `name_key`:
```sql
trim(regexp_replace(upper(entity_name), '[^A-Z0-9]+', ' '))
```
1. `upper` — ACME, Acme, acme → ACME
2. `regexp_replace(..., '[^A-Z0-9]+', ' ')` — every run of characters that is *not* a
   capital letter or digit becomes one space
3. `trim` — drop leading and trailing spaces

**Regex** (regular expression) — a mini-language for text patterns.
`[A-Z0-9]` = one character in that set; `^` *inside* brackets = NOT; `+` = one or
more in a row.

**Why keep the original too:** reports show the legal name exactly as filed.
`name_key` is for matching only.

---

## Flag, Don't Drop

When a row is suspect, add a TRUE/FALSE column rather than deleting it in staging.
`is_well_formed = length(line) >= 1436`.

**Why:** a deleted row is invisible; you can't count it, investigate it, or notice the
problem growing. A flagged row can be counted, and the mart filters on the flag
(`where is_well_formed`). The decision about what to exclude happens in one visible
place.

---

## Testing and Evaluation

**dbt test** — a SQL query that looks for bad rows. Zero rows = pass.

**Known-answer test** — pick a record you verified by hand (DINATALE VENTURES LLC,
L26000514010) and confirm the pipeline returns it correctly. Proves the whole chain,
not just one step.

**Evaluation set (the 50-name test set)** — hand-checked companies with the correct
answer recorded. Matching must be right **≥ 90%** before results show as fact.
→ *Reading list: Chip Huyen on evaluation — build the eval before the system, and
measure on data that looks like real use.*

**A green pipeline is not correct data.** Tests prove what you thought to test.

---

## Workflow First, Agent Last

Datum's design rule, straight from *Building Effective Agents*:
- **Plain code** for predictable steps (parsing, joining, deduping)
- **A model call** only where judgment is needed (is "ACME BUILDERS LLC" the same as
  "Acme Builders, L.L.C."?)
- **An agent** (a model that decides its own next steps) only for the long tail, and
  behind human review

**Why:** predictable steps should be cheap, fast, and identical every run. Agents cost
more and can wander. Use the least autonomy that solves the problem.

---

## Cost Guardrails

- **X-Small warehouse** — the smallest compute size (1 credit/hour while running)
- **60-second auto-suspend** — stops billing a minute after the last query
- **Resource monitor** — notifies at 80% and suspends the warehouse at 100% of 10
  credits a month
- **Run as SYSADMIN on DATUM_WH** — `COMPUTE_WH` isn't under the monitor, so queries
  there bypass the cap

**Why:** a solo founder can't absorb a surprise bill. The cap is a hard stop, not a
dashboard to watch.

---

## Environments: DEV vs PROD

dbt writes to a **target schema** set in `profiles.yml` (`DEV`). Custom schemas are
appended: `+schema: staging` → `DEV_STAGING`. A later `prod` target would build
`PROD_STAGING` from the same code. Experiments never touch what the app reads.

---

## Key-Pair Authentication

A **private key** (secret, stays on your laptop in `~/.snowflake/`) and a **public key**
(registered on your Snowflake user). The client signs a login with the private key;
Snowflake verifies with the public key. No password is sent or stored. Same key as
credit-stream.

**Rule:** credential files (`profiles.yml`, `connections.toml`, the `.p8` key) live
outside the repo and are never pasted or committed.

---

## File Ownership and Permissions

Every file has an **owner**. `ls -l` shows it. `~/.config` was owned by `root` (from a
2024 `sudo` install), so the GitHub CLI — running as me — couldn't write its login
there. Fix: `sudo chown -R "$(whoami)" ~/.config` (give it back to me, recursively).
**Lesson:** "permission denied" in your own home folder usually means a past `sudo`.

---

## Python Versions, Wheels, and pipx

**Wheel** — a prebuilt Python package. Without one for your Python version, pip tries
to *compile* the package from source (which may need Rust or C tools).

**Datum story:** Homebrew installed Python 3.15. `pydantic-core` had no wheel for 3.15,
and its Rust build tool only supported up to 3.13, so installing the Snowflake CLI
failed. Fix: `pipx install snowflake-cli --python python3.12`.

**pipx** — installs a Python *command-line tool* in its own isolated environment, so
its dependencies can't clash with anything else. Use pipx for tools (snow), pip in a
virtual environment for libraries your code imports.

---

## Simplest Correct Solution

Choose the simplest thing that's correct now; add complexity only for a problem you
actually have, and say which problem.

**Datum story:** I first proposed one stage with folders and a `PATTERN` filter to
separate daily from quarterly files. Simpler and just as correct: one stage per file
type and a plain `COPY`. Complexity has to earn its place.

---

## Evaluation: Baselines, Similarity, and Confidence

**Baseline** — the score of the simplest reasonable approach, measured before any
improvement. Datum's: normalize the input, pick the single most similar name out of
13M. **60%** on the first 10 cases. Every change after this is judged against it.

**Jaro-Winkler similarity** (`JAROWINKLER_SIMILARITY` in Snowflake) — scores two strings
0–100 by shared characters in roughly the same order, with a bonus when the
**beginnings match**. That's why `sadler holdings inc jax` still found SADLER HOLDINGS:
extra words at the end cost little. It's also why `kromah properties` lost to KROM
PROPERTIES: strong shared start, small differences.

**Similarity is not confidence.** Right answers scored 91–96; a wrong one scored 91. A
score says "these strings look alike," not "this is the company." Confidence needs
more evidence: does the city/ZIP match, how far ahead is the top answer of the
runner-up, did the user confirm it.

**The worst failure is a confident wrong answer.** `the pool guy off race track rd`
returned THE POOL GUY OF CENTRAL FLORIDA, INC. at 91. A tool that always answers will
eventually show a contractor the wrong company as fact. That's why the test set has
`NEEDS_MORE_INFO` cases, and why the user confirms the match.

**Top-1 vs top-k (recall@k).** Top-1 asks "was the first answer right?" Recall@5 asks
"was the right answer anywhere in the first 5?" If the app shows 5 candidates for the
user to confirm, recall@5 is the honest measure of search.

**Small eval sets are noisy.** With 10 cases, one case = 10 percentage points. Treat
the number as direction, not precision, until the set reaches 50.
→ *Chip Huyen on evaluation.*

**dbt seed** — a CSV in the repo (`pipeline/seeds/`) that `dbt seed` loads as a table.
Small, version-controlled reference data: test sets, lookup lists.

**Evaluate each step, not just the end.** Search v1 is a chain: LLM extraction → name
match → ranking. When the end score moves, check the extraction output first. Prompt v1
turned "really good beer" into "Beer" — an LLM step made a case worse that plain string
math got right. Only the test set showed it.

**Teaching to the test.** Tuning a prompt while looking at the same cases you score on
inflates the score. Rules stay general (examples NOT from the test set), stop after a
couple of rounds, and the real check is new cases.

**Freeze model outputs, score the frozen copy.** The extraction is saved to a CSV and the
eval always scores that file. Re-running the model is a deliberate act, so scores stay
comparable over time even though a model can answer slightly differently each call.

**Deterministic tie-breaking.** `ROW_NUMBER()` picks arbitrarily among equal values, so a
query can return different winners on different runs. End every ranking with a unique
column (`document_number`) so reruns can't flip.

---

## Calling an LLM from Python

**SDK** (software development kit) — a library that wraps an API. `anthropic` turns
`client.messages.create(...)` into an authenticated HTTPS POST to Anthropic's REST API,
reads the key from the `ANTHROPIC_API_KEY` environment variable, retries, and parses the
JSON reply. Same idea as `boto3` for AWS.

**Structured output via a forced tool.** Give the model a tool with a JSON schema and
`tool_choice` that requires it. The reply comes back as fields, not prose to parse.

**Virtual environment** (`.venv`) — a private Python with its own packages, per project.
`source .venv/bin/activate` switches the current terminal to it (prompt shows `(.venv)`);
it's per terminal session, not per folder. Plain `python` exists only inside one —
macOS itself has `python3`.

---

## Choosing Between Search Versions

**Retrieve, then re-rank.** Do the expensive search once and keep a small candidate pool
(top 20 of 13M). Then try ranking and decision rules on the pool for almost nothing.
That's how real search engines are built, and it lets you test changes one at a time.

**Errors don't cost the same.** Count types, not just totals:
- *Unnecessary question* ("can you add the city?") → costs the contractor seconds
- *Miss* (right company not in the shortlist) → costs a retry
- *Confident wrong answer* (POOL LLC for "the pool guy") → costs trust, maybe money

v1 and v2a both scored 6/10, but v1's error was the cheap kind and v2a's the expensive
kind. Same idea as credit risk: a false approval costs more than a false decline, so you
don't judge a model by accuracy alone.

**Some cases are ambiguous by nature.** "hughes financial ponte vedra" fits two real
companies in the same city. No ranking fixes that; the right product answer is a
shortlist and a confirmation. That's why recall@5 matters more than top-1 here.

**Components interact.** The extractor's invented city ("Surfside") cost nothing while
city only broke ties, and broke a case once city got weight. A change downstream can
expose an error upstream — re-check the whole chain after any change.

**Know when the eval set is too small to decide.** At 10 cases, each rule change flipped
about one case each way. That's noise, not signal. Stop tuning; get more cases.

---

## The Claude Code Harness (Nov 6)

**In one line:** rules and safety rails for the robot that writes code, so it can work with less babysitting.

Think of Claude Code as a new hire:

| Piece | New-hire version | Datum file |
|---|---|---|
| Onboarding note | "Here's how to prove your work runs. Never touch the safe." | `CLAUDE.md` → Commands that prove work |
| Lock on the safe | Even if they forget the note, the door is locked | `.claude/settings.json` deny rules + `.claude/hooks/block-secrets.sh` |
| Inspector at the door | Before they say "done," someone checks the work | `.claude/hooks/offline-checks.sh` (the Stop hook) |

**Hook** = a script Claude Code runs automatically at a set moment.
- **PreToolUse** runs *before* a command. Exit code 2 = block it.
- **Stop** runs when Claude is about to *finish its turn*. Exit code 2 = "not done yet": Claude gets the
  error and must fix it. A loop guard (`stop_hook_active`) stops it from forcing Claude forever.

**Rules vs hooks:** CLAUDE.md is a *request* (usually followed). Hooks and deny rules are *code* (always run).
Anything that must never fail (secrets, checks) belongs in code. Building Effective Agents: give the agent
ground truth from its environment at each step instead of letting it grade its own work.

**Guardrail vs boundary:** the secrets hook matches text, so `cat .e*` slips through. It's a guardrail
(catches ordinary mistakes), not a boundary (stops a determined attacker). Real boundaries are OS-level
(sandboxing, file permissions). Both are worth having; know which one you have.

**Why the Stop hook runs `dbt parse`, not `dbt build`:** hooks run on every turn, so they must be cheap.
`parse` checks the project fits together without touching Snowflake ($0). `build` would wake the warehouse
and bill ~60 seconds of compute every time Claude stops.

**Proving a negative:** to show `dbt parse` never connects, run it against a fake account
(`invalid.invalid`). If it succeeds, it can't have connected: there was nothing to connect to.

---

## ruff and Pinning Tool Defaults

**ruff** = a spell-checker for Python. It reads code without running it and flags mistakes:
undefined names (F821), unused imports (F401), syntax errors (E9).

**`ruff.toml`** = its settings: "only flag real bugs." ruff 0.17 raised its built-in default from about 60
rules to 407, including import *order* (style). Without the file, the Stop hook would make Claude reshuffle
imports in the middle of unrelated tasks.

**Lesson:** don't depend on a tool's defaults; pin them in config. Defaults change between versions,
the same reason you pin package versions.

---

## Snapshot Files vs Event Files (federal liens)

- The **quarterly filings file is a snapshot of what's active**: all 20,444 rows are status A. Released
  liens simply disappear from it.
- The **events file is a log of changes**: releases (`COR`), discharges (`COD`), refilings.
- Current state between snapshots = latest snapshot + new daily filings − daily releases.
- Same pattern as the corporate files: snapshot (quarterly) + deltas (daily). Know which kind of file
  you hold before you model it.


---

## A Check That Can't Fail Proves Nothing (LEFT JOIN: ON vs WHERE)

- A `LEFT JOIN` keeps every row from the left table and fills the right side with NULL when nothing matches.
- A condition in `ON` decides **which right-side rows may match**. A condition in `WHERE` runs **after** the join.
- Put a right-side filter in `WHERE` and every unmatched row (right side NULL) is thrown away: the LEFT JOIN
  quietly becomes an inner join.
- In script 13's CHECK 2 that would make "missing from snapshot" always 0. Before trusting a check, ask what
  input would make it fail. (Chip Huyen: test the test.)

---

## Verify a Convention With the Data (Duval FRM / TO)

- County indexes usually say grantor / grantee. I expected FRM = debtor. The data said the opposite.
- Method: for each document type, count the most frequent names on each side. Institutions give it away: the City of
  Jacksonville and the IRS are on the **FRM** side of liens, so FRM = creditor and **TO = debtor**.
- Cheap (one pass with `awk` over files already on disk, no warehouse credits) and it changed the linking rule.
- Evidence table: `docs/phase_b_rulings.md`.

---

## Allowlist vs Blocklist

- **Blocklist:** name what's forbidden, allow the rest. A type nobody thought of slips through.
- **Allowlist:** name what's allowed, forbid the rest. A new type is excluded until someone approves it.
- Duval's index holds criminal sentences, domestic violence judgments, marriage and death records. Past staging,
  only an allowlist of type codes exists (`LN`, `WRT`, civil `JDG`/`CCCJUDG`, plus releases and satisfactions).
- Use an allowlist whenever the cost of a leak is much higher than the cost of a gap.

---

## Built But Not Displayed (a switch instead of a cut)

- Discipline flags and Duval flags are built and tested, and carry `is_shown = false` through two dbt variables.
- A dbt **variable** is a named setting in `dbt_project.yml` that models read with `{{ var('name') }}`.
- Why: both wait on an outside answer (counsel; the Clerk). The work ships now and one line flips it on later.
- This is how to honor "don't cut scope" and "don't show what isn't cleared" at the same time.

---

## Virtual Environments Aren't Relocatable; Symbolic Links

- A `.venv` writes its own absolute path into `activate` and into the first line (the "shebang") of scripts like
  `pytest` and `pip`. Move the folder and those lines point at nothing: `bad interpreter`.
- Fixes: rebuild the environment from `requirements.txt`, or leave a **symbolic link** at the old path.
- A symbolic link is a signpost: `~/datum` holds no files, it points at `~/Work Streams/datum`.
- It also removed the space from every command path. Spaces in paths need quotes everywhere, or the shell reads
  two words.

---

## Layered Code Review (Nov 18)

Source: Anthropic, "How the Claude Code team does code review" (Oct 2026). Full mapping: `docs/review_process.md`.

- **The idea:** no single check catches everything, so stack cheap ones. Each layer catches a different kind
  of mistake, and a person's attention goes only where a machine can't judge.
- **Datum's layers, in the order a change meets them:**
  1. The author proves it before opening the pull request (the leg's "done when" checks, `pytest`, `dbt build`).
  2. A reviewer with **fresh context** reads the diff. Fresh context means a new agent that never saw the
     author's reasoning, so it can't inherit the author's blind spots.
  3. A security pass when `src/` changed (secrets, injection, personal data).
  4. **Continuous integration (CI):** GitHub runs `ruff`, `pytest` and the secrets-hook test on every pull
     request (`.github/workflows/ci.yml`). A red X blocks the merge.
  5. A person approves, and how closely depends on the **risk tier**.
- **Risk tier is set by the change, not the author.** The highest-tier path a diff touches sets it
  (`REVIEW.md`). High = what a contractor sees or what could accuse the wrong company (marts, matching
  rules). Medium = loaders and staging. Low = docs and tests.
- **Findings are tagged** Important (fix or answer before merge), Nit (optional, at most 3) or Pre-existing
  (not caused by this change; log it, don't block). Three review rounds at most; after round 1 the reviewer
  reads only what changed.
- **What gets measured** (`docs/review_log.csv`, shown on the Datum Roadmap's Reviews tab): hours a pull
  request waits on a person, share with an AI review, findings per review, rounds to pass, reverts.
- **`REVIEW.md` vs `CLAUDE.md`:** `CLAUDE.md` tells the agent how to build. `REVIEW.md` tells the reviewer
  what "wrong" means here: the ways Datum fails (accuses, leaks, miscounts, reassures, asserts, exposes, bills).

---

## Decide on Whether a Record Exists, Not on One of Its Values (Nov 19)

- The lien bug: the code closed a lien `when r.released_on is not null`. `released_on` came from
  `try_to_date`, which returns NULL when the text is not a date. So a release with a damaged date looked
  exactly like no release at all, and the lien stayed open on a report.
- The fix asks a different question: does a release **event** exist? `count_if(condition) > 0` counts the rows
  where the condition is true and turns the count into TRUE or FALSE. The date is kept for wording only.
- The general rule: when a decision hangs on "did this happen", test for the row. A value inside the row can
  be missing for reasons that have nothing to do with whether it happened.
- Chip Huyen's "test the test" applies: the new unit test has a release with a NULL date, and it fails on the
  old code.

---

## A Test That Reads the Same Switch as the Code Agrees With Anything (Nov 19)

- `company_flags` hides Duval and discipline flags by reading two project variables (`show_duval`,
  `show_dbpr_discipline`). The old test read the same variables to decide what should be hidden.
- Flip a variable and both the model and the test change their minds together. The test stays green while
  14,000 hidden flags become visible. It could never fail, so it proved nothing.
- Ruling R28: the test compares `is_shown` with the word `false` written in the test itself. Now un-hiding a
  source takes two edits in one pull request, and a reviewer sees both.
- `is distinct from false` is `<> false` that also catches NULL. A plain `<>` comparison with NULL is neither
  true nor false, so a NULL would slip through.
- The same idea is behind the seed `search_page_sources`: the model reads its addresses from variables, and
  the test checks them against a separate list.

---

## The Builder-and-Critic Loop (Nov 19)

Source: Anthropic, "Building Effective Agents" (the evaluator-optimizer workflow).

- One agent builds. A second agent, with no memory of how the work was built, looks for what is wrong. The
  builder answers each finding, and the critic reads only what changed. `REVIEW.md` stops the loop at three rounds.
- On pull request 6 it ran twice: round 1 found 2 Important findings, round 2 found none.
- The builder ran its own small critic before pushing, and that pass caught three more nits. While a helper
  agent is reading, the main panel looks idle. The run is finished when the last message says it pushed.
- A full ordering matters for repeatable results: `row_number()` or `min_by` over rows that tie picks one
  arbitrarily, so add columns to the `order by` until two rows can only tie when they are identical.


---

## Where a Claude Code Session Runs: the Cloud or Your Mac (Nov 20)

- A **cloud session** runs on Anthropic's servers. The Mac can be off. It can reach the GitHub repo, and it
  cannot reach `.env`, `~/.snowflake/` or anything else that lives only on the Mac.
- A **local session** runs on the Mac. Remote Control (`/rc` inside the session) lets the phone steer it, and
  the Mac must stay awake, online and with the session's window open.
- The rule of thumb: work that needs credentials (dbt, Snowflake, Postgres) runs on the Mac. Work that needs
  only the repo (briefs, reviews, docs) can run in the cloud.
- One prompt never reaches the phone: the question about using usage credits when a model's cap is hit.

---

## API Keys: Static Secrets, Expiry, Rotation and Scope (Nov 20)

- An API (application programming interface) key is a **static secret**: a password that never changes on
  its own. Whoever holds it gets in.
- **Expiry** puts a ceiling on the damage from a leak nobody noticed. The lifetime is chosen when the key is
  made and cannot be changed afterward. An expired key cannot be revived.
- **Rotation** is replacing a secret on a schedule. For Datum the plan is a new key about every 90 days, in `.env`.
- **Blast radius** is how much one leaked secret can damage. **Least privilege** shrinks it: the key is scoped
  to one workspace (Default), not the whole organization. An organization-scoped key also has to name a
  workspace on every request, which Datum's code does not do.
- **Authentication** proves who is calling. **Authorization** decides what they may do.
- **Identity federation** replaces the stored key with a short-lived token. The platform the code runs on
  (a cloud provider, or GitHub Actions) vouches for it with a signed badge, a JWT (JSON Web Token), under the
  OIDC (OpenID Connect) standard. A laptop has nobody to vouch for it, so local work still uses a key.
  Revisit when the app is deployed.

---

## Environment Variables: `.env` and `.zshrc` (Nov 20)

- An environment variable is a named value a program can read while it runs, such as `ANTHROPIC_API_KEY`.
- `.env` is a plain file of `NAME=value` lines inside the project. Only a program that asks for it reads it
  (Datum calls `load_dotenv()`). It is in `.gitignore` and never goes to GitHub.
- `~/.zshrc` is a script the Mac's shell runs every time a terminal opens. A variable exported there reaches
  every command in every terminal.
- The trap: `load_dotenv()` does not overwrite a variable that is already set. An old key exported in the
  shell silently wins over the new key in `.env`.

---

## Two Copies of a Repo: Fetch, Pull and Push (Nov 20)

- Git is a distributed version control system. GitHub holds one complete copy and the Mac holds another, and
  nothing syncs them automatically. A merge on GitHub changes only GitHub.
- `git fetch` downloads the news and changes no files. `git pull` is a fetch followed by a merge into the
  branch you are on. `git push` sends your commits the other way.
- "Already up to date" describes only the current branch. A pull on an old branch does not update `main`.
- The habit: before any session on the Mac, `git switch main`, then `git pull`.
- A **commit** saves changes on a branch. A **merge** brings one branch's commits into another, and on GitHub
  that is what the green button on a pull request does.

---

## One Folder, One Checked-Out Branch (Nov 21)

- A folder can have only one branch checked out. Switching branches rewrites the files in it.
- During the Phase C run, something checked out `main` in `~/datum` while the agent was working, and four of
  its commits landed on local `main`. Nothing had been pushed, so the agent moved them back.
- While an agent runs in `~/datum`, reading is safe (`git status`, `git log`, `git diff`). Anything that
  changes what is checked out is not (`switch`, `pull`, `merge`, `commit`, `stash`).
- `git worktree add <folder> <branch>` makes a second folder with its own checked-out branch and the same
  history. Git refuses a branch that another folder already has checked out, so to look at `main` while
  `~/datum` is on it, use `git worktree add --detach <folder> origin/main`. That is isolation: two workers,
  two folders, one repo.

---

## Percentiles: p50, p95 and Why Not the Median (Nov 23)

- The p95 is the 95th percentile. Sort every measurement from fastest to slowest and go 95% of the way down.
  On 208 searches that is about search number 198: 197 were faster and about 10 were slower.
  That is where the p95 sits, which is not the same as the number of searches over the 1-second target.
- The p50 is the median. It answers "what is typical?" The p95 answers "how bad does it get?"
- Leg C2's search had a p50 of 181 milliseconds and a p95 of 1,229. The median looked perfect and hid 11
  searches that took over 1 second, one of them 4.4 seconds.
- It is the same idea as Value at Risk in credit risk: the median loss says little, and the tail is the risk.
- An average is worse than either. It mixes the few very slow searches in with the typical ones, so it
  describes neither the typical search nor how bad the worst ones get.
- Report both. The p50 is the typical experience and the p95 is the pass-or-fail bar.

---

## The Complement Rule: "At Least One" (Nov 23)

- For several things all to happen, multiply their chances. Ten searches all in the faster 95% is
  0.95 multiplied by itself ten times, which is about 0.60.
- "At least one slow search" can happen in many ways, and its opposite, "every search was fast", in one.
  So work out the opposite and subtract it from 1: 1 - 0.60 = 0.40.
- "1 in 20 searches is slow" therefore becomes "4 in 10 contractors who search ten times meet a slow one".
- It assumes each search's speed does not depend on the others, which is close enough for a rule of thumb.

---

## Trigram Index (Nov 23)

- A trigram is three characters in a row. `SMITH` breaks into `smi`, `mit`, `ith`, plus padded pieces for the
  start and the end of the word.
- A trigram index is like the index at the back of a book: for each trigram, the list of rows whose name
  contains it. Postgres provides it through the `pg_trgm` extension.
- A search breaks the typed name into trigrams, looks each one up, and keeps the names that share most of
  them. Small typos still match, and the table is never read from end to end.
- Common trigrams such as `ing` point at hundreds of thousands of rows, which is why names made of common
  words are the slow searches.

---

## OLAP and OLTP: Build in Snowflake, Serve from Postgres (Nov 23)

- OLAP (online analytical processing) is big questions over many rows, in batches. That is Snowflake and dbt.
- OLTP (online transaction processing) is many small, fast lookups. That is what an app needs, and Postgres,
  a free open-source database, is built for it.
- Decision d18: builds run in Snowflake, and lookups read a copy in Postgres. A suspended warehouse takes
  seconds to wake, and keeping one awake all month costs about 720 credits.
- The cost of the split is a copy step. The loader swaps all the tables in one transaction, so the app never
  reads half a load, and hidden records never leave Snowflake (rule W9).

---

## Vertical Partitioning: the Narrow Search Table (Nov 23)

- The slow searches spent their time fetching thousands of wide rows scattered through a 3 GB table that
  does not fit in memory.
- Vertical partitioning moves the columns a hot query needs (document number and name) into their own small
  table, about 0.9 GB. The search reads the small table and then fetches the 200 full rows it wants by key.
- It should change no answer, because the names, the index and the reranking are the same. That is checked,
  not assumed: every search must return the same five companies as before.
- The costs are more disk and two tables that must always agree.
- A miss on a target is information. The search missed by 0.23 seconds on the best machine it will ever run
  on, which says the design has no headroom.

---

## A Near-Namesake Withholds a Link (rulings R29 and R30, Nov 20)

- R29: a ZIP code that is present and unreadable can neither support a match nor contradict it, so the name
  alone is not enough. The link is AMBIGUOUS with the reason `zip_unreadable`.
- R30: a looser key removes a leading THE, treats AND and & as the same, and removes every trailing legal
  suffix. It is used to **count** near-namesakes, not to
  make more matches. When two companies share the looser key, the link is AMBIGUOUS.
- The mistake to avoid is reading R30 as a way to match more. The danger is a wrong match (a clerk typed LLC
  and meant the INC), and so the rule says less. That is precision over recall.
- The two rulings moved 625 links from CONFIRMED to AMBIGUOUS and none the other way.

---

## A Short Account for the Person, the Full Account for the Agent (Nov 23)

- A leg report is long on purpose, so that a later agent can see exactly what was done. That length is too
  much for a person to review well.
- Every pull request now starts with a Human review section of at most 250 words: what changed and why, what
  is proven, what was assumed, the decisions that are mine, and at most three places to look.
- The author writes its own summary, so the AI reviewer checks the summary against the diff.
- The summary treats a symptom. The cause is the size of the pull request, and smaller legs are the real fix.

---

## Where Instructions Live: `CLAUDE.md` and Project Instructions (Nov 24)

- `CLAUDE.md` is a file in the repo. Claude Code reads it at the start of every session that works in that
  folder, on the Mac or in the cloud. It holds the engineering rules, and it is public because the repo is.
- Project instructions are a text box on the Datum project in the Claude app. Every chat in that project
  reads them. They hold how I want to be taught and written to, and they are private.
- A brief (`docs/prompts/florida_master.md`) is read only when a prompt names it. It holds one job.
- The rule of thumb: a rule about the code goes in `CLAUDE.md`, a rule about working with me goes in the
  project instructions, and a rule about one build goes in its brief.
- Both are loaded before the first reply, and neither is enforced. A rule that must never be broken needs a
  hook or a test, because an instruction can be forgotten in a long session.

---

## Risk Tiers for the Files Agents Obey (Nov 24)

- Pull request 19 moved four paths to High: the `docs/prompts/` folder (the briefs), `docs/review_process.md`,
  `docs/phase_b_rulings.md` and `docs/mvp_plan_nov8.md`, plus any brief saved anywhere else. An unattended agent takes its instructions from
  them, so a wrong edit changes what every later run builds.
- `docs/open_questions.md`, `docs/access/` and `docs/legs/` also guide agents, through their working rules,
  the terms of use and earlier reports. They stay Low for a practical reason: most legs write to them, and
  raising them would make every leg High. A leg's own review covers what it wrote to `docs/open_questions.md`
  and `docs/access/`. Reviewers skip the text of `docs/legs/` reports, and the last review round checks the
  Human review section against the diff instead.
- The mistake to avoid is saying those three paths "do not instruct agents". They do. They stay Low because
  of the cost of raising them, and the review of each leg is what guards them.
- A brief saved outside `docs/prompts/` is still High, and the reviewer reports where it was saved.

---

## Where Context Lives: the Repo and Project Docs (Nov 24)

- Context engineering is deciding what information a model sees, and when. Anthropic's article on it
  ("Effective context engineering for AI agents") describes just-in-time retrieval: the agent holds light
  references, such as file paths, and loads a file only when it needs it. The article says the best agents
  often mix the two approaches, and Claude Code is its example: `CLAUDE.md` is loaded up front, and other
  files are read when needed.
- The repo is the source of truth. Claude Code reads its files from disk when it needs them, and a cloud
  session reads them from GitHub. Nothing is copied, so nothing goes stale.
- Project docs in the Claude app are copies. Every chat in the project can search them, but a copy drifts the
  moment the repo changes, and the project instructions already say that the repo wins.
- Being on GitHub and being readable by Claude are separate questions. A file that git ignores stays readable
  by Claude Code on the Mac, and it is invisible to cloud sessions and to the nightly Roadmap job, which read
  GitHub. That is the cost of making `INTERVIEW_ANSWERS.md` private, which is planned and not yet done.
- The rule of thumb: keep files in the repo, let Claude read them when needed, and use project docs only for
  material that has no home in the repo.

---

## A Search That Passes Its Tests Can Still Fail Its User (Nov 24)

- On Nov 24 I tried the web app on a restaurant I know. "v pizza orlando" put an inactive company in Winter Park
  first, and the one I meant, V PIZZA LAKE BUENA VISTA LLC at 8586 Palm Pkwy, Orlando, was not on the list.
  Searching its street address found nothing at all.
- The data was fine: that company is in the register, active, with exactly that address. The search was the problem.
- **Why it ranked 13th.** The search scores names by Jaro-Winkler similarity, and a short name scores higher than a
  long one against a short query. "V PIZZA" scores 90 against "V PIZZA WP LLC" and lower against "V PIZZA LAKE BUENA
  VISTA LLC". The city only breaks ties, so a company in the right city still loses to one with a shorter name.
  Active or inactive is not used at all.
- **Why the address found nothing.** The search reads only the name and the city. The street the contractor types is
  extracted and then ignored, even though every company's principal address is already in the table.
- **The lesson.** The 10-case test set was built from names, so it could not catch either problem. A test set has to
  come from the way real users search: here, a trade name plus a city, and an address with no name.
- **A legal name is not the name on the sign.** A contractor knows "V Pizza & Tap Room" and an address. The register
  holds "V PIZZA LAKE BUENA VISTA LLC". Fictitious names (DBAs) and address search close that gap.

---

## Two-Stage Retrieval: the First Step Sets the Ceiling (Nov 25)

- A search over millions of names runs in two steps. Step 1, retrieval, is cheap and rough: Postgres uses the
  trigram index to keep a short list of candidates, here the 200 names nearest to what was typed. Step 2,
  ranking, is careful and slower: Python scores only those 200 and puts the best first.
- The ranking can only reorder what step 1 hands it. If the right company is not among the 200, no ranking rule
  can put it first. This is called a recall ceiling: step 1's recall (the share of right answers it keeps) is the
  most step 2 can ever achieve.
- Phase D showed this on a real case. For "v pizza orlando", 10,062 names were similar enough to pass step 1's
  test, and V PIZZA LAKE BUENA VISTA LLC stood 2,861st among them, so it was dropped before the ranking ever saw it.
  The Phase D brief had put the fix in step 2, and the agent measured where the company was lost before changing
  anything, which is how the real cause was found.
- **How to diagnose it.** Ask two questions in order: did step 1 keep the right answer, and if it did, where did
  step 2 put it? Fixing the ranking when step 1 lost the answer changes nothing.
- **The proposed fix (question Q46).** Step 1 brings back first the names that contain every word that was typed,
  and fills the rest of the 200 by similarity. Measured alone, it lifts the right company from not listed to 17th,
  and with the new ranking (rule S2) switched on, to 1st.
- The same pattern appears in search engines and in RAG (retrieval-augmented generation), where a model can only
  use the passages the retriever found.

---

## Normalizing Data Can Widen What It Exposes (Nov 26)

- Normalizing means rewriting values into one standard form so that different spellings compare as equal: PKWY and
  PARKWAY become the same word, and "1551 ATLANTIC BLVD STE 200" can be read as "1551 ATLANTIC BLVD". It is usually
  treated as plain cleaning, with no risk attached.
- On Nov 26 I agreed that the address search should ignore the unit on a record (question Q47), so that a contractor
  who types a building's address still finds a company in Suite 200. A reviewer on the brief pointed out what that
  does to APT, UNIT and LOT: those usually mark a home, and ignoring them would let one typed address list the
  companies registered in every apartment or mobile-home lot there.
- So the rule was narrowed. Office units (STE, SUITE, BLDG, FL, FLOOR, RM, ROOM) are ignored, and home units are still
  compared exactly, until a lawyer answers whether a home address should be searchable at all (question Q54).
- **The lesson.** A matching rule decides who can be found, not only what counts as equal. Every widening of a match
  ("treat these as the same") is also a widening of what one search reveals, so a privacy check belongs next to
  every normalization rule, not only next to new data sources.
- **The tradeoff.** A company registered at "APT 4" is still found only when the note has APT 4. That is a missed
  match, which Datum accepts, because a missed match is the cheap error and exposing a home is the expensive one.

---

## Environment Variables Are Copied at Start, and .env Never Overwrites Them (Nov 26)

- An environment variable is a NAME=value pair that a program receives when it starts. Every program gets a
  copy of its parent's variables at that moment: VS Code passes its copy to the terminal, the terminal to
  Claude Code, and Claude Code to the app it starts. Editing `.env` or `.zshrc` later changes no program that is
  already running.
- `load_dotenv()` reads `.env` and adds its names to the program's environment, but by default
  (`override=False` in python-dotenv 1.2.4) it skips any name that is already set. So when the environment
  already holds an `ANTHROPIC_API_KEY`, the key in `.env` is never used.
- On Nov 26 that is exactly what happened. I had put a new key in `.env`, and the old key was deleted in the
  Console, but an old copy of `ANTHROPIC_API_KEY` was still in the terminal's environment. It won, the Claude
  service rejected it, and every search answered "unavailable". The new key was fine the whole time: Claude Code
  removed the old variable for one command (`env -u ANTHROPIC_API_KEY ...`) and its live checks worked.
- **The lesson.** A secret should live in exactly one place. A second copy does not fail loudly; it silently
  wins, depending on which program started first.
- **The tradeoff.** `load_dotenv(override=True)` would let `.env` always win, but it hides the duplicate instead
  of removing it, and a shell value set on purpose for one test would then be ignored without a word. Removing
  the stale copy is simpler and fixes Claude Code too, because Claude Code can bill the API instead of the plan
  when it finds an API key in its environment.
