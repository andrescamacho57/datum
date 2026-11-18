# Phase B rulings (decided Nov 18, 2026)

Andres delegated these calls on Nov 18: "make a recommendation for all of them using your best judgement and do it." They settle every open question in the three Phase A leg reports (`docs/legs/a1-federal-liens.md`, `a2-dbpr-licenses.md`, `a3-duval-recording-index.md`), and they refine decisions d19 and d21 in `docs/decisions.json`. Log them in the decision log at the next close-out.

Format: **decision · why · revisit**. Questions that stay open are in `docs/open_questions.md`.

The principle behind most of them: a wrong flag on a company is the expensive error, and a missing flag is the cheap one. When the data can't tell us, we don't show it.

## Evidence: which side of a Duval record is the debtor

Measured on Nov 18 from the 2,703 loaded files in `data/raw/duval/` (2025-01-01 to 2026-11-11). Counts are party rows. "Org-like" means the name contains a legal-entity or organisation word; it is a size estimate, not a classifier. Only institutions are named here.

| Type code | FRM side | TO side | Reading |
|---|---|---|---|
| `LN` lien | 82% org-like. Top: City of Jacksonville 27,573; IRS 3,558; Property Appraiser 973; Florida Department of Revenue 646 | 25% org-like: the businesses and people liened | FRM = lienholder, **TO = debtor** |
| `WRT` warrant | 100% Florida Department of Revenue | 73% org-like | A state tax warrant. **TO = taxpayer** |
| `JDG` judgment | 61% org-like. Top: State of Florida 4,596; debt buyers; City of Jacksonville 3,011 | 12% org-like; garnishees appear here | FRM = plaintiff or creditor, **TO = defendant** |
| `CCCJUDG` | 87% org-like: debt buyers and credit unions | 4% org-like | County civil judgments. Same sides as `JDG` |
| `JDGS` judgment/sentence | State of Florida on 41,693 of 41,745 rows | individuals | **Criminal. Excluded** |
| `RELEASE`, `SAT` | 83–87% org-like: the City, credit unions, IRS, mortgage registries | the party being released | FRM = the creditor letting go, TO = the debtor |
| `LP` lis pendens | lenders | defendants, including junior lienholders such as the City and the United States | TO side is noisy |
| `N/C` notice of commencement | owners and builders on both sides | | Not a risk record |

This is the opposite of the grantor/grantee guess most people start with, which is why it was measured and not assumed.

## Linking (every source)

| # | Decision | Why | Revisit |
|---|---|---|---|
| R1 | A link is **CONFIRMED** when the match key and the 5-digit ZIP code both agree. Without a ZIP code, it is CONFIRMED only when exactly one company **of any status** in Florida has that match key **and** the source name contains a legal-entity word (LLC, INC, CORP, CO, LTD, LP, LLP, PLLC, PA, PC and similar). Otherwise AMBIGUOUS or NO_MATCH. | Stripping "LLC" can make a person's name equal a company's. Counting only active companies hides a dissolved namesake and pins its old lien on the new one. | After the 20-link hand check |
| R2 | A record dated before the company's own filing date on Sunbiz is never CONFIRMED; it becomes AMBIGUOUS. | A company can't owe a lien from before it existed. This catches dissolved-then-reformed names. | When the corporate events file is loaded |
| R3 | Duval records have no address, so only the unique-name branch of R1 applies to them. | Nothing else to match on. | If the Clerk's layout turns out to carry an address |
| R4 | No person's name goes past staging. Link models carry the source record's identifier, the company's document number, the outcome and what it matched on. The source's raw name stays in staging. | Businesses only. A raw name without an entity word may be a person. | Never loosens without counsel |

## Federal tax liens

| # | Decision | Why | Revisit |
|---|---|---|---|
| R5 | Lien status comes from the filings file only. The status on debtor and secured-party rows is ignored. | All 20,486 filings say active, and 9 party rows disagree. One file has to be the authority. | If the state explains the party-row status |
| R6 | A lien is **open** if it is in the latest snapshot or a later daily filing, and no later `COR` (certificate of release) exists. A `COD` (certificate of discharge) does not close it; the flag shows "certificate of discharge recorded on <date>" as a fact. | 🟡 A discharge normally frees one piece of property and leaves the lien on the rest. Showing the event states the record without drawing a conclusion. | Counsel confirms what `COD` means |
| R7 | The one active lien with a cancellation date, and the party rows with status `C`, produce no flag. | Unknown meaning. Don't show what we can't explain. | When the Division of Corporations answers |
| R8 | Load every daily lien file published since the 2026-10-03 snapshot before computing "open". | One day of dailies can't tell us what was released in the other weeks. | Becomes a scheduled pull after launch |
| R9 | Citation for a federal lien: the Sunbiz federal lien search page, the filing number, the source file name and the fetch time. | No per-record link has been found. The filing number lets anyone look it up. | When a per-record URL is found |

## DBPR (Department of Business and Professional Regulation)

| # | Decision | Why | Revisit |
|---|---|---|---|
| R10 | Keep building on the DBPR files. Their terms are silent on automated download and reuse. | The state offers them "to the public through free download" under Chapter 119. | Counsel, before launch |
| R11 | A license reaches a company through the license's business name (`dba_name`), using R1. The report shows the license type, number, status and expiry, and never the license holder's name. | In Florida a person holds the license that qualifies the business. The business fact is "a license qualifies this company, and it is active or not". | After the hand check |
| R12 | Discipline is built and tested (discipline → license → company, no names), and **not displayed**: the flags mart marks it `is_shown = false` through a dbt variable `show_dbpr_discipline`, default false. | Every one of the 6,457 discipline rows is about an individual. That is near the FCRA (Fair Credit Reporting Act) line, which needs a lawyer. This is not a scope cut: the work ships, and the switch flips after review. | Counsel, before launch |
| R13 | `QB` business records link by R1 like any other name. When no license links to a company, the report says "No contractor license found under this name in DBPR's file", with the caveat that the file leaves out delinquent and involuntarily inactive licenses. That line is information, not a flag. | `QB` rows carry no number and mostly no status, and several hundred look like a person's name. | When we learn what `QB` records are for |
| R14 | The discipline files name the license kind in words; the license file uses codes. The map between them is a dbt seed, drafted from the distinct values. Kinds that don't map are listed in the leg report. | A seed is reviewable and tested. | When a new fiscal-year file appears |

## Duval County

| # | Decision | Why | Revisit |
|---|---|---|---|
| R15 | Repair the 13 rejected files **in a copy** and load them. Join each continuation line to its record with a space, drop the blank line in the links file, and require the repaired count to equal the `EOF` trailer. The file as sent stays in `rejected/`. | The cause is understood (a line break inside a legal description), the Clerk's counts are right, and 18,386 documents plus every orphan row come back. | If the Clerk re-issues the files |
| R16 | Past staging, only an **allowlist** of type codes exists. Flags: `LN` and `WRT`; `JDG` and `CCCJUDG` when no FRM party is "FLORIDA STATE OF". To decide open or closed: every code in the release and satisfaction families. Everything else stays in staging, including `JDGS`, `JDGR`, `DVJ`, `DVJMV`, `FJPD`, `RPOFJ`, `JVRL`, `WRTNF`, `LP`, `N/C`, marriage, death and military records. | An allowlist can't leak a type nobody thought of. The State of Florida as plaintiff is the mark of a criminal or fines matter. | After launch: `LP`, `N/C` and `WRTNF` are in the open-questions log |
| R17 | The company must be on the **TO** side to be flagged. | Measured above. | If the Clerk's layout says otherwise |
| R18 | A lien or judgment is **closed** when any document in the release or satisfaction families links to it, by instrument number, or by book and page when the link has no instrument number. A partial release (`PTL REL`) does not close it and shows as an event. | Closing on any release-family document errs toward not showing a lien that may be gone. 10,674 links carry only book and page. | When `CAN` and `WDL` are understood |
| R19 | Individuals' party rows stay in raw and staging and go no further. This follows the build brief, not the older wording of d21. | The business-share count needed every party in staging; nothing downstream needs people. | Never loosens without counsel |
| R20 | Duval flags are built and **not displayed**: dbt variable `show_duval`, default false. | The Clerk has not answered on terms of use. | When the Clerk answers |
| R21 | Citation for a Duval record: the Clerk's Official Records search page, the instrument number, and book and page. | No per-record link exists. | When one is found |
| R22 | A recording date before 1900 becomes NULL past staging. | 1775-01-01 is a placeholder. | Never |

## Housekeeping (rule 3 and repeatability)

| # | Decision | Why | Revisit |
|---|---|---|---|
| R23 | Every downloader writes a fetch manifest: file name, source URL, fetch time in UTC, size and checksum. It loads into one small raw table. For files already on disk, the file's modification time is used and marked approximate. | CLAUDE.md rule 3: every fact carries a source URL and a UTC fetch time. `loaded_at` is when Snowflake got it, not when we fetched it. | Never |
| R24 | Add `requirements.txt` with exact versions, including `paramiko` below 4. | The virtual environment broke when the folder moved, and nothing recorded what was in it. | When a package is added |
| R25 | The DBPR validator rejects a license file whose first row looks like a header. | It would load as one bad data row. | Never |
| R26 | The hardcoded snapshot date in staging gets replaced before the January 2027 snapshot. Target: Dec 15, 2026. | Five models now repeat it. | Dec 15, 2026 |
