# Data Feasibility Spikes

## Status as of 2026-10-12

| Spike | Status |
|---|---|
| 1. Sunbiz | ✅ Done. Free bulk files over SFTP (secure file transfer), quarterly full snapshot plus daily changes. DBA owners link to legal entities by document number. See `docs/access/sunbiz.md`. This is now the version-one pipeline, not a spike. |
| 2. County courts | Recon done for Duval (`docs/access/duval-civil.md`). Moved to version 1.1. |
| 3. Liens and UCC | Liens: version one, one county, with human review (`docs/access/duval-official-records.md`). UCC (Uniform Commercial Code): version 1.1, bulk access not verified. |
| 4. Google signals | Not started. Not in version one. |
| 5. Entity resolution | Becomes the 50-name hand-checked test set and the 90% bar (`PROJECT_CONTEXT.md` section 6). |
| New: DBPR contractor licenses | Version one. Free download files from the Department of Business and Professional Regulation. Delinquent and involuntarily inactive licenses are left out. |

The rules and the "What this is NOT" section below were written for throwaway spikes. Version one now includes a pipeline and a web app; see `PROJECT_CONTEXT.md`.

---

**What this is:** A "spike" is a quick, throwaway investigation to answer one technical feasibility question *before* committing to building. You're not building the product here — you're finding out whether the data backbone is even gettable and reliable. Throwaway code is fine and expected.

**Why these are safe to do now:** Every possible version of this product — no matter what trade, what price, what UX — needs to pull and match public business data. These questions are true regardless of what the interviews say. The interviews tell you *what to build*; these spikes tell you *whether the data makes it possible.* They run in parallel.

**Rules:**
- Time-box each. The goal is a yes/no/“it's complicated,” not a finished pipeline.
- Don't build UI, accounts, or scoring. Just answer the question.
- Write down what you learn — feeds into `research_log.md` section 3.
- **Verify everything yourself.** The notes below are my best understanding as of mid-2026, but access methods, APIs, and terms of use change constantly. The spike *is* the verification — don't take these notes as fact.

---

## Spike 1 — Florida business registry (Sunbiz)

**Question:** Can I retrieve entity data (legal name, officers/registered agent, status, formation date, principal address) for a given business, programmatically?

**How to test:** Check sunbiz.org (FL Division of Corporations). Look for: a bulk data download (FL has historically published downloadable data files), any API, or whether you must scrape the search UI. Pull one business you know.

**Pass:** You can retrieve a known business's full record by name or document number from a script.

**Time-box:** 2–3 hours

**Result (2026-09-15):** ✅ Bulk files exist and are the primary path. No official API; the live search sits behind a Cloudflare challenge. Full detail in `docs/access/sunbiz.md`.

---

## Spike 2 — County court records (Duval first)

**Question:** Can I search civil case records (lawsuits, money judgments) by business/party name for Duval County?

**How to test:** Find the Duval County Clerk of Courts public case search portal. Determine: searchable by party name? Programmatic access or scrape-only? CAPTCHA, login, or rate limits? What case data is exposed (judgments, amounts, dispositions)?

**Pass:** You can retrieve the civil case list for a known litigious business and see judgment outcomes.

**Time-box:** 3–4 hours

**Flag (highest-risk spike):** County clerk systems vary wildly in quality and access. Some are scrape-hostile or paper-only. This is the data source most likely to be a wall — which is exactly why you test it early, before building anything on the assumption it works. If Duval is hard, that's a finding, not a failure.

---

## Spike 3 — Mechanic's liens + UCC filings

**Question:** Where are these filed in FL, and can I search them repeatably?

**How to test:**
- **Liens** are recorded at the county level in Official Records. Check the Duval County Clerk's Official Records search — can you find a recorded claim of lien by party name?
- **UCC filings** are centralized in Florida (Florida Secured Transaction Registry / FLDOS). Check whether you can search by debtor name.

**Pass:** Repeatable retrieval (programmatic preferred, manual-but-consistent acceptable for now) of a known lien and a known UCC filing.

**Time-box:** 2–3 hours

**Flag:** FL mechanic's lien law is its own beast (notice-to-owner rules, deadlines). For the spike you only care about *retrieval*, not interpretation — but note that the *meaning* of a lien filing is jurisdiction-specific and will matter later.

---

## Spike 4 — Google Business / web signals

**Question:** What does the Google Places API cost per call, and what legitimacy/longevity signals does it return (rating, review count, years active, address verification)?

**How to test:** Get a Places API key, pull one business. Read the field list and the pricing page. Note the per-call cost at volume.

**Pass:** You understand cost-per-lookup and which fields are useful as risk signals.

**Time-box:** 1 hour

---

## Spike 5 — Entity resolution (the one that decides viability)

**Question:** Given a messy real-world input — "Mike's HVAC, 123 Main St" typed by a contractor — can I reliably match it to the *correct* Sunbiz entity and the *correct* court/lien records?

**How to test:** Take 10 real businesses (use your `outreach_leads.csv`). For each, manually attempt: name + address → the right registry entity → the right court records. Count how often it's unambiguous vs. how often you hit multiple matches, DBAs, name variants, or wrong-business collisions.

**Pass:** You know your match rate and your failure modes.

**Time-box:** 3–4 hours

**Why this is the most important spike:** A risk report run on the *wrong* "John's Plumbing" is worse than no report — it's confidently wrong, which destroys trust instantly. Entity resolution (reliably tying a typed name to the right legal entity across messy data) is the genuinely hard technical problem here. If it's unreliable, the product's core promise breaks no matter how good the rest is. Better to learn the difficulty now than after you've built everything around it.

---

## Regulatory flags — read before you touch personal data

These are flags, not legal advice. You'll need a lawyer before launch.

1. **FCRA / consumer credit.** Public *business* records (Sunbiz, court records, liens, UCC) are not consumer credit reporting and don't carry FCRA permissible-purpose requirements. The moment you pull *personal* credit on an owner, FCRA applies and you need permissible purpose or consent. Stay on business + public data and you sidestep this — which is the plan. Don't drift across that line without legal review.

2. **Terms of use / automated access.** Public records are public, but a site's ToS may still restrict automated scraping or set rate limits. "It's public" ≠ "I can scrape it however I want." Note each source's ToS during the spike. This affects build approach (official bulk data > API > scrape).

3. **Accuracy and how you present findings.** Surface public-record *facts* ("3 civil judgments since 2022, totaling $X"). Do not editorialize into conclusions ("this business is a deadbeat"). Present facts, let the user decide. This is also why the product is framed as **analysis / decision support, never "advice."** Carry that framing into every output from day one — it's much easier than retrofitting it.

---

## What this is NOT

No frontend. No user accounts. No scoring model. No "report" formatting. Those were out of scope for the spikes themselves. These five spikes answer exactly one thing: **is the data gettable, and can I match it to the right business reliably?** Answer that, and the eventual build is de-risked and probably fast.
