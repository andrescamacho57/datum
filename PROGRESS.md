# Datum — Progress Tracker

**Owner:** Andres Camacho
**Build started:** 2026-10-12
**Current milestone:** look up any Florida company (full Sunbiz register loaded)
**Status:** First slice proven end to end on one daily file; loading the quarterly snapshot

Approved decisions live on the Agenda dashboard (Decisions tab). This file is the
build log: what got done, what I learned, what's next.

---

## The rules for this project

- **Workflow first.** Plain code for predictable steps, a model call only for close
  name matches, an agent only for long-tail lookups behind human review.
- **Simplest correct solution.** Add complexity only for a problem we actually have.
- **Inspect before loading.** Look at every new file on the laptop before spending
  warehouse credits on it.
- **Nothing shows to a contractor as fact below 90%** on the 50-name test set, and
  every report line links to its official record.

---

## Done

### Day 0 — 2026-10-12: Decisions synced, Snowflake set up, first file staged

**Docs**
- Project docs synced to the Oct 11 decisions: no interview gate on code, v1 source
  order (Sunbiz + DBPR, then one county's liens), stack, 90% accuracy bar, outreach
  = free report + $50 gift card, no trade-first choice

**Snowflake**
- Resource monitor `datum_monthly`: 10 credits/month, notify at 80%, suspend at 100%
- Warehouse `datum_wh`: X-Small, 60-second auto-suspend, owned by SYSADMIN
- Database `datum`, schema `raw`, file format `fixed_width`, stage `sunbiz_stage`,
  table `sunbiz_cor_daily (line, source_file, loaded_at)`

**Data**
- Downloaded `doc/cor/20261009c.txt` from the state's SFTP server: 1.1 MB, 834 records
- Inspected before loading: `wc -l` (834), `head -c 300`, line lengths with `awk`,
  raw bytes with `od -c` → every record is **1440 bytes = 1436 content + 4 NUL padding**
- Spot-checked field positions on 5 records (document number, status, filing type,
  officer title) against the state's published layout
- Uploaded to the stage through Snowsight (the `snow` CLI wasn't installed yet)

**Decision:** one Snowflake stage per Sunbiz file type

**Concepts learned:** fixed-width files and record layouts, SSH trust-on-first-use,
bytes vs characters, NUL padding, why tools disagree about a file's length

### Day 1 — 2026-10-13: Raw table loaded, repo on GitHub

- `COPY INTO` raw: **834 rows, every line 1440 characters** (Snowflake kept the NUL
  padding that macOS `awk` hid)
- Found `~/.config` owned by `root` (from a 2024 `sudo` install) — the reason the
  GitHub CLI could never save a login. Fixed with `chown`; login now persists
- Repo pushed to GitHub (private): `andrescamacho57/datum`

**Concepts learned:** file ownership and permissions, reading `ls -l`, `sudo`/`chown`,
git remotes, COPY idempotency

### Day 2 — 2026-10-20/21: dbt end to end — first slice done

- dbt project in `pipeline/` (dbt 2.0.8, Fusion engine), `datum` profile with
  key-pair auth (same key as credit-stream)
- `stg_sunbiz__cor` (view): cuts each line into named columns by position
- `entity_lookup` (table): well-formed rows only, one row per company, `name_key`
- 3 tests: `not_null` + `unique` on document_number, `accepted_values` on status
- First build failed twice — both my file errors: Jinja braces inside a SQL comment,
  and dbt 2.0 requiring test settings under `arguments:`. Fixed; **5/5 passed**
- Known-answer test: **DINATALE VENTURES LLC (L26000514010)** returned from the mart

**Concepts learned:** sources vs refs, the DAG, materializations (view vs table),
Jinja renders before SQL runs, QUALIFY + ROW_NUMBER for dedupe, normalization and
regex, boolean flag columns, DEV vs PROD environments

### Day 3 — 2026-10-22: Full Florida register loaded and verified

- Installed the Snowflake CLI (`snow`) with pipx. First attempt failed: Homebrew had
  just installed Python 3.15, too new for `pydantic-core` (no prebuilt wheel, and its
  Rust build tool supports ≤3.13). Fixed with `--python python3.12`
- `snow` connection `datum` (key-pair, SYSADMIN, DATUM_WH): test **OK**
- Downloaded `doc/quarterly/cor/cordata.zip`: 1.7 GB → 10 files, **18.7 GB**,
  **12,987,601 records**
- Inspected before loading: quarterly lines are **1442 bytes** (1440 + CRLF), vs 1441
  in the daily file (1440 + LF). No code change needed (`length(line) >= 1436` holds)
- Suspected a duplicate (`cordata6` and `cordata8`: same size, same line count) —
  **disproved with `md5`**. In a fixed-width file, same line count ⇒ same size, so
  it was one coincidence, not two
- Created stage `sunbiz_cor_quarterly_stage`
- Snowflake SQL reorganized into numbered scripts in `snowflake/`; study guide created
- `PUT` all 10 files: 18.7 GB → **1.80 GB gzipped** (~10:1). `cordata6`/`cordata8`:
  same raw size, different compressed size — a second proof they differ
- `COPY` into new table `raw.sunbiz_cor_quarterly`: **12,987,601 rows**, every
  per-file count matched size ÷ 1442 exactly
- Line length **1440**, not the 1441 I predicted — Snowflake strips `\r\n` as one line
  ending. Prediction disproved by the data; docs corrected
- **Status: I = 9,168,902 (71%), A = 3,818,699 (29%).** The "active data" snapshot
  includes inactive companies — the dissolved-client signal is there

**Decision:** separate raw table for the quarterly snapshot (raw = one table per source
kind; staging combines them)

- Deleted the 18.7 GB of `.txt` files (zip kept). Snapshot date from `unzip -l`: **2026-10-07**
- dbt: staging combines daily + quarterly (`union all`) with `source_kind` and
  `published_on`; mart orders "newest" by `published_on`, then `loaded_at` (fixes the
  load-time ordering bug). New `not_null` test on `published_on`
- `dbt build`: **6/6 passed** in 44s; `entity_lookup` = **13.0M companies**, `unique` holds
- Known-answer checks by exact document number (not name):
  - L26000514010 DINATALE VENTURES LLC → A, daily, 2026-10-09 ✅
  - P98000033661 FERGUSON AIR CONDITIONING & REFRIGERATION, INC. → A, DOMP,
    Boynton Beach, filed 1998-04-13, quarterly, 2026-10-07 ✅ (matches search.sunbiz.org)
- Mart mix: daily A 834 · quarterly A 3,818,699 · quarterly I 9,168,902

**Decisions:** separate raw table per Sunbiz file kind; combine in staging; "newest" =
the state's publish date. Snapshot date hardcoded until the January 2027 snapshot.

**Concepts learned:** union all vs union, known-answer tests by identity (ID, not name),
APFS disk percentages, compression ratios, predictions checked against data

---

## Next

1. Start the 50-name hand-checked test set (`evals/`): input as a contractor would
   type it → expected document number, verified on search.sunbiz.org
2. Name matching against `entity_lookup`, measured on that set (target ≥ 90%)
3. Fictitious names (DBAs) and federal tax liens from Sunbiz
4. Move the snapshot date into raw at COPY time before the January 2027 snapshot

---

## Parking Lot (deliberately not doing yet)

- **Automate the daily pull in Python** (SFTP with `paramiko`, load with the Snowflake
  connector) instead of manual `sftp` + upload
- **REST API ingestion where a source actually offers one:** CourtListener (federal
  bankruptcy, v1.1), Trellis (courts, v1.1, paid). Interview feedback asked for API
  ingestion; don't force it where bulk files are the better path
- Fictitious names (DBAs), federal tax liens, DBPR contractor licenses
- Name normalization beyond `name_key` (strip LLC/INC, expand abbreviations)
- PROD environment (when the web app reads data)
- Installing `snow` scripted loads / scheduling

---

## Open Questions

- What does the date at positions 473–480 mean? (Some values are future dates —
  likely an effective date, not the filing date)
- ~~Does the quarterly snapshot include inactive companies?~~ **Yes:** 9.17M inactive vs
  3.82M active (2026-10-22)
- How does each report line link to the official record? (Sunbiz detail URLs need a
  GUID that isn't in the bulk file)
- Snowflake trial ends ~Nov 15 — upgrade decision
- The website shows statuses beyond A/I (`NAME HS`, `CROSS RF`, `INACT`, `InActive`).
  What do they mean, and where do they live in the bulk files?
- City casing is inconsistent (`Boynton Beach` vs `PALM BEACH GARDENS`) — normalize
  before matching on address
