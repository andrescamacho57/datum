# Georgia master brief (ON HOLD as of Nov 11, 2026)

Don't run this yet. Florida goes first. Before using it, update section 3 with what the Florida legs taught us (read `docs/legs/`).

Kickoff line when it's time: `Read docs/prompts/georgia_master.md. Run the recon phase only.`

## 1. Goal

Find out whether Datum's Florida pipeline can be repeated for Georgia, and at what cost, before building anything. Approved scope says Florida only until 10 paying users, so this is a feasibility test of the method and of the model, not a product launch.

## 2. Keep it separate

- Work in its own folder and its own Snowflake schemas (`raw_ga`, staging and marts prefixed `ga_`). Never touch Florida tables, models, seeds or scripts.
- Same stack and rules as `docs/prompts/florida_master.md` section 3: a branch and pull request per leg, comment every line, secrets off limits, businesses only, warehouse `datum_wh` only, stop conditions, and the leg report format.

## 3. Recon phase (the only phase defined so far)

For each source, find the official bulk channel and write `docs/access/ga-<source>.md` with: where the data is, format and layout, update cadence, cost, terms of use and robots rules, and whether it carries a company identifier, address and amounts.

Sources to check, in order:
1. Georgia Secretary of State, Corporations Division: business entity records
2. Georgia state contractor licensing board: license and discipline records
3. Federal tax liens and county liens: who records them in Georgia and whether any index is available in bulk
4. One pilot county's recorded-document index

Rules for recon:
- Read public pages only. No logins, no purchases, no automated downloading of record pages.
- If a source charges for bulk data, report the price and stop; don't buy.
- Label every claim verified (with the link) or assumed.

Done when: one summary, `docs/legs/ga-recon.md`, compares each Georgia source to its Florida equivalent (available in bulk? free? identifiers? effort to load?) and recommends go, wait or skip for each.

## 4. Later phases

Not written. Andres decides after reading the recon summary.
