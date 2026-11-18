# Open questions log

Questions we chose not to answer before the MVP (minimum viable product) launch. Each one has a working rule in `docs/phase_b_rulings.md`, so none of them blocks the build. Add to this file; don't delete a row, mark it answered with the date and the answer.

Started Nov 18, 2026.

## Needs a lawyer before launch

| # | Question | Working rule until answered | Why it matters |
|---|---|---|---|
| Q1 | May a business report show DBPR (Department of Business and Professional Regulation) discipline, when every discipline record names an individual license holder? | Built, not displayed (R12) | Nearest thing we have to the FCRA (Fair Credit Reporting Act) line |
| Q2 | DBPR's terms are silent on automated download, redistribution and commercial use. Is silence enough? | Keep building (R10) | Terms-of-use exposure |
| Q3 | Does a federal lien `COD` (certificate of discharge) clear the lien, or free one piece of property? | Lien stays open; the discharge shows as a fact (R6) | Wording on the most serious flag |
| Q4 | Duval: do any terms of use apply to the bulk recording index? | Duval flags not displayed (R20) | Asked of the Clerk on Nov 5; no answer yet |
| Q5 | Florida construction liens are said to expire one year after recording unless a suit is filed. True, and should the report say so? | Not stated on the report | Caveat wording |
| Q6 | The repo is public and holds redacted fixtures cut from real Duval and DBPR rows, plus Andres's cell number in `docs/mvp_plan_nov8.md`. Anything to change before paying customers? | Left as is: business names and public record only, people redacted | Andres chose public for interviews |

## Needs the source to answer

| # | Question | Who can answer | Working rule |
|---|---|---|---|
| Q7 | What does status `C` mean on federal lien party rows? | Division of Corporations | No flag (R7) |
| Q8 | One active federal lien has a cancellation date. Is it active? | Division of Corporations | No flag (R7) |
| Q9 | Is there a per-record URL for a federal lien, and for a company (the site needs an ID that isn't in the bulk file)? | Division of Corporations | Cite the search page and the number (R9) |
| Q10 | Duval: the official layout, the update schedule, and whether the server's ssh-dss key fingerprint in `docs/access/duval-recording-index.md` is theirs | Duval Clerk | Trust on first use, key pinned |
| Q11 | Duval: is there a per-record URL? | Duval Clerk | Cite the search page, instrument, book and page (R21) |
| Q12 | Duval: what do `WRTNF`, `SATNF`, `CAN` and `WDL` mean? | Duval Clerk | `WRTNF` not flagged; the others count as closing documents (R16, R18) |
| Q13 | Duval: what kinds of case sit under `JDG`? Is excluding "FLORIDA STATE OF" as plaintiff enough to keep criminal matters out? | Duval Clerk, plus a 30-row hand read | R16 |
| Q14 | DBPR: what is a `QB` record for, and why do most have no status? | DBPR | R13 |
| Q15 | DBPR: discipline data ends 2026-07-17 and there is no fiscal year 26/27 file. How far behind does it run? | DBPR | Caveat on the report line |

## Product and data questions for after launch

| # | Question | Why it's parked |
|---|---|---|
| Q16 | Should a lis pendens (`LP`) be a flag? The TO side mixes the party being sued with junior lienholders. | Too noisy to show without more work |
| Q17 | Are notices of commencement (`N/C`) useful as an activity signal (who is building, for whom)? | Not a risk record; possibly a feature |
| Q18 | `LN` is one code for every kind of lien. City code-enforcement and utility liens (27,573 rows) differ from a contractor's claim of lien. Can the lienholder's name sort them into kinds? | Contractors may care about some kinds far more than others; ask in interviews |
| Q19 | IRS liens appear in both the Sunbiz files and Duval's index. Do any overlap, and would a company be flagged twice for one lien? | Needs CONFIRMED links from both to compare |
| Q20 | Fuzzy linking for typos in lien and license names | Precision first; measure CONFIRMED coverage before adding it |
| Q21 | DBPR unlicensed-activity and recovery-fund files | Exist; not in scope yet |
| Q22 | 206 Duval documents use a type code missing from the lookup; one party name contains a pipe; three files start with a byte-order mark | Tiny counts; noted in the access doc |
| Q23 | Corporate events file, to catch dissolutions between quarterly snapshots | Already listed as "before launch" in PROGRESS.md |
| Q24 | Hook test gap: nothing proves unsorted imports pass `ruff` under `ruff.toml` | Parked Nov 6 |
