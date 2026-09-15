# Research Log: SMB Credit Risk Tool for Trade Contractors

**Last updated:** 2026-09-14
**Purpose:** Track verified facts, market data, competitors, customer insights, and open questions for the contractor credit decisioning product.

---

## ⚠️ How to Use This Log

Every claim is tagged:
- ✅ **VERIFIED** — sourced from a credible primary or secondary source, citation included
- 🟡 **NEEDS VERIFICATION** — heard or estimated, plausible, not yet sourced
- 🔴 **ASSUMED** — working hypothesis, no evidence yet

Never use a 🟡 or 🔴 stat in a pitch deck, investor email, or LinkedIn post without first promoting it to ✅.

---

## 0. Mission Statement (as of 2026-09-14)

**Founding insight (from Amex):** Contractors default on their own credit lines because their customers fail to pay *them*. They are absorbing someone else's credit risk without knowing it.

**Mission:**
> Every time a contractor takes a net-30 job, they are lending money. Datum is the underwriting they never had.
>
> Datum pulls the public record on a commercial customer — business registry, court judgments, mechanic's liens, UCC filings — ties it to the correct legal entity, and lays it out in plain language *before the job is accepted*. Every fact carries a source and a date. When the evidence is thin, Datum says so instead of guessing.

**Plain-English version (say this to a contractor):**
> "Find out whether they pay their bills, before you take the job."

**Three commitments:**
1. Every fact carries a source link and a fetch date. No black-box score.
2. An honest "can't tell" beats a confident wrong answer. Abstention is a valid output.
3. Analysis, not advice. The contractor decides. (See FCRA / legal notes, section 3.)

**Datum is not:** a lender, a collections agency, a lien filer, or a credit bureau.

**Parked (explicitly deferred):** an insurance or guarantee layer tied to the risk profile — better coverage on low-risk jobs, no coverage plus a recommendation to walk on high-risk ones. Attractive because a guarantee signals confidence in the assessment and is how you sell a number nobody asked for. Deferred because it converts Datum from an information business into a risk-bearing one, which triggers state insurance regulation. Revisit only after accuracy is measured. See section 2 for why the gap is real.

---

## 1. Pain Point Statistics

### ✅ VERIFIED — severity of the pain (added 2026-09-14)
- **Construction and engineering have the worst payment timing of any sector — 100% of invoices paid late, with the longest delays in the study.** (Source: Chaser, "Accounts receivable stats finance professionals need in 2026," Jun 2026 — https://www.chaserhq.com/blog/accounts-receivable-stats)
- **9.1% of construction businesses write off more than 14% of annual revenue as bad debt — the highest rate of any sector covered.** (Source: Chaser, Jun 2026)
- US businesses generally: 88% report bad-debt write-offs of 3% or higher; 38% lose between 6% and 8% of revenue annually. (Source: Chaser, Jun 2026)
- **Commercial contractors average 3.4% net profit margin. At that margin a $1M bad debt requires $29M in new revenue to recover; a $15K write-off requires over $200K.** (Source: Payra Resources, Apr 2026 — https://resources.payra.com/what-a-single-bad-debt-write-off-actually-costs-a-construction-distributor/; originally Levelset analysis. NOTE: Levelset is an interested party selling lien services — the margin figure is industry-standard and reusable, but attribute carefully.)
- US companies write off an average of 4% of accounts receivable annually. (Source: Payra, Apr 2026)

**Why this matters:** severity is now established. Bad debt in this sector is business-threatening, not annoying. **Frequency is not established** — see section 1b.

### 🟡 NEEDS VERIFICATION
- Commercial contractors write off 2–5% of revenue annually as bad debt *(partially superseded — sector data above is higher; find a figure specific to sub-$5M trade contractors rather than all construction)*
- On $800K revenue, that's $16K–$40K per year in losses
- "Slow/non-paying customers" is the #1 cash flow stressor for trade contractors
- Hundreds of thousands of mechanic's lien filings per year in Florida
- Approximately 25% of business failures are caused directly by customer non-payment (Source: Impello Global, Mar 2026 — cited as "industry data," no primary source given. Find the primary before using.)

### ✅ VERIFIED
- Levelset (Procore) reports users have collectively protected over $1B in payments from non-payment situations. (Source: levelset.com, 2024)
- Big banks' approval rate for small-dollar business loans fell to ~13% (Source: Experian / U.S. Census Bureau, cited in The Financial Brand, Sept 2025)
- New business formation in U.S.: 400,000–450,000 applications/month since 2020, up from ~300,000 pre-pandemic (Source: Experian, cited in The Financial Brand, Sept 2025)
- 50% of U.S. SMBs use business credit cards; 23% use personal cards for business expenses (Source: nCino, Jan 2026)
- 61% of small businesses carry revolving balances on credit cards; 63% use cards just to cover operating expenses (Source: nCino, Jan 2026)

### 1b. The frequency problem — the biggest open risk to the business (added 2026-09-14)

Severity is verified. **Frequency is the thing most likely to kill this product, and it is entirely unmeasured.**

The logic: a pain that is severe but *infrequent* does not sustain a subscription. If a contractor takes on two new commercial customers a year, a $40/month tool costs $480/year to prevent an event he experiences twice. That math — not competition from Levelset — is the most likely failure mode.

**Implication for interviews:** the highest-value question is no longer "would you pay for this?" It is:

> **"How many new commercial customers did you take on in the last 90 days?"**

- High number (weekly/monthly decisions) → subscription works; the tool sits in a recurring workflow.
- Low number (a few a year) → per-report pricing, or the product must attach to something the contractor touches weekly (see monitoring concept, section 2b).

Add this question to section 5 and record the number for every interview.

### 🔴 ASSUMED (validate via customer interviews)
- Contractors evaluate new commercial customers often enough for this to be a recurring-use product (**frequency assumption — now the #1 risk, see 1b**)
- A $30–50/month tool would feel like fair pricing to a trade contractor with $800K revenue
- Trade contractors do not currently use commercial credit reports for customer evaluation
- The biggest pain is "new commercial customer evaluation" specifically (vs. cash flow forecasting, vs. loan offer evaluation)
- Pre-job credit decisions are more valuable than post-job lien protection for this user

### Statistics to find and verify
- Average bad debt write-off rate for small commercial contractors (IBISWorld, ASA, NACM)
- Total mechanic's lien filings in Florida per year (FL Clerk of Court reports)
- Average size of unpaid invoice for HVAC/plumbing/electrical contractors
- Percentage of trade contractor failures attributed to bad debt
- Number of small commercial contractors (under $5M revenue) in Florida and U.S.

---

## 2. Competitive Landscape

### ✅ VERIFIED INCUMBENTS

**Levelset (acquired by Procore, 2021, ~$500M)**
- Founded 2007, New Orleans
- ~150 employees
- Pricing starts at $149/month; free tier available
- Core product: lien rights management — preliminary notices, lien waivers, mechanic's liens
- Has credit intelligence features, not the primary focus
- Strength: 800+ five-star reviews, deep construction industry expertise
- Weakness: reactive (post-job), expensive for small contractors, owned by mega-corp (innovation may slow)
- Source: levelset.com, saasworthy.com

**Dun & Bradstreet (D&B)**
- The OG business credit bureau
- Proprietary PAYDEX score, full business credit reports
- Reports cost $40–200+ each
- Sells to enterprise credit managers, not small contractors

**Experian Business, Equifax Business**
- Equivalent commercial credit bureaus
- Proprietary scoring (Experian Intelliscore Plus, Equifax Business Credit Score)
- Same pricing tier and audience as D&B

**Creditsafe**
- 430M businesses globally, updated up to 5M times/day
- Automated trade references from 16,000+ banks
- Enterprise / mid-market focused
- Source: creditsafe.com, Mar 2026

**Worth.ai**
- $30M Series A in March 2026 (Amex Ventures as investor)
- Real-time business identity verification + AI-powered credit decisioning
- B2B / lender-focused, not contractor-facing
- Source: fintech.global, Mar 2026

**JUDI.AI**
- Targets community banks and credit unions
- AI-powered SMB credit decisioning
- Source: The Financial Brand, Sept 2025

**BICA (Building Industry Credit Association)**
- Founded 1903, California-based
- Trade association for shared credit info on contractors
- Old technology, membership model

**iSoftpull, Soft Pull Solutions**
- FICO / personal credit checking software for loan brokers
- Different problem (personal credit, not business)

### 🟡 ADJACENT CATEGORY — Trade credit insurance (added 2026-09-14)

Insures a business's receivables against customer non-payment. Directly adjacent to the parked guarantee concept in section 0.

**Players:** Allianz Trade, Atradius, Coface, Euler Hermes. Brokered through firms like Insureon and Impello Global.

- **Allianz Trade states its product is designed for businesses with sales of at least $5 million per year, occasionally down to $1 million depending on the situation.** (Source: allianz-trade.com, May 2026)
- Policies typically pay 75–95% of the invoiced amount. (Source: ICISA, Jan 2026)
- Premiums: roughly $1,500–$5,000/year at $1M in annual credit sales; $7,500–$25,000 at $5M. (Source: Impello Global, Mar 2026 — broker, interested party)
- Trade credit insurance costs roughly 0.1%–0.3% of insured sales. (Source: Payra, Apr 2026)

**Why this matters: the persona is structurally excluded.** Mike at $800K revenue sits below the floor of every major carrier. The guarantee layer Andres wants to build is a real, century-old product category that *starts above his user*. That is a genuine unserved gap, not a hypothetical one — and it is the strongest long-term argument for why Datum could become more than a lookup tool.

**Caution:** underwriting below $1M means bearing risk, which means state insurance regulation and capital. Not a near-term move. Documented here so the gap isn't forgotten.

### ⚠️ Demand-side caveat on this entire section (added 2026-09-14)

Everything in section 2 describes what **vendors sell**, not what small contractors **buy**. Supply-side evidence proves companies believe there is money here; it does not prove Mike has ever heard of, used, or paid for any of it.

Specifically: Levelset publishes contractor-facing guidance telling subcontractors to check a general contractor's credit before bidding, naming D&B, Experian Commercial, and Cortera as sources. (Source: levelset.com/blog/how-to-check-general-contractor-credit/) Two readings, both important:
1. The "check them before the job" behavior is being *advocated* in the market — the framing is not novel, and Levelset already owns this content ground.
2. Advice being published is not evidence of behavior. 🔴 Whether any small contractor actually does this remains unvalidated.

Also note a possible persona mismatch: most published payment-risk data describes **subcontractors working under general contractors**, not HVAC/plumbing shops doing direct light-commercial work. Those may be different risk profiles and different buying behavior. Test in interviews.

### Where the gap remains
- Small contractors (sub-$5M revenue) — not core to any incumbent
- Pre-job decision (vs. Levelset's post-job lien protection)
- AI-native, modern UX
- Affordable ($20–50/month vs. $149+ or enterprise pricing)
- **Below the trade credit insurance floor** — no carrier serves sub-$1M revenue businesses

### 2b. Concepts to pressure-test in interviews (not decisions)

Recorded so they aren't lost. None are committed; all are responses to the frequency risk in section 1b.

1. **Monitoring, not lookups.** Watch customers the contractor *already has* — new liens filed, new judgments, payment-timing drift — instead of only checking new ones. Converts a twice-a-year decision into a weekly-value product. Supporting signal: "Bad debt rarely arrives without warning. The signals are usually there — buried in your AR data weeks or months before the write-off." (Source: Payra, Apr 2026)
2. **Attach to the credit application.** Contractors who extend net-30 often have customers fill out a credit application or W-9. If Datum *is* that form — customer fills it, Datum enriches it automatically — it lives inside an existing workflow instead of being another tool to remember.
3. **Sell to suppliers, not just contractors.** Distributors (Ferguson, Johnstone, Winsupply) extend credit to contractors constantly — a weekly decision, not a twice-yearly one. Same engine, higher-frequency buyer. Also overlaps the supply-house discovery channel already in the outreach playbook.
4. **Contractor-reported payment experiences as a data flywheel.** BICA has done this since 1903 with old technology. Public records are a commodity; contractor-reported payment behavior is proprietary and compounds. **Flag:** defamation and data-accuracy exposure; needs legal review before any contractor-submitted content is shown to another user.

---

## 3. Available Data Sources

### Free public data
- **Florida Sunbiz** (state business registry) — entities, agents, officers, formation dates
- **Florida Clerk of Court records** (county level) — lawsuits, judgments, mechanic's liens, UCC filings
  - Duval, Clay, Nassau, St. Johns counties for Jacksonville metro
- **SAM.gov** — federal contractor registry, debarments
- **OFAC** — sanctions list
- **PACER** — federal court records (low cost per query)
- **BBB** — business ratings, complaints
- **Google Business** — reviews, ratings, longevity signals

### Equivalents in other states (for future expansion)
- Georgia: Georgia Corporations Division (sos.ga.gov)
- Arizona: Arizona Corporation Commission (azcc.gov)
- North Carolina: NC Secretary of State Business Registration
- All states have analogous registries but schemas, access methods, and data quality vary significantly

### Paid APIs (for v2+)
- D&B Direct, Experian Business, Equifax Business APIs ($$$)
- Middesk — modern business verification
- Worth.ai
- People Data Labs — owner background

### Legal note
- **Pulling personal credit reports requires permissible purpose under FCRA** — either consumer consent or you must be a creditor making a credit decision
- Business data does NOT have this restriction — can build entirely on public + business APIs without consent

---

## 4. User Persona (Working Hypothesis)

**Mike, 42, owns "Mike's HVAC" in Jacksonville**
- $800K annual revenue, 5 employees
- 60% residential / 40% light commercial
- Books in QuickBooks Online
- $35K balance on Amex Business Platinum
- Bookkeeper monthly, CPA annually
- Decisions Mike makes:
  1. Should I take this commercial job at net-30/45/60?
  2. Should I extend net-30 terms to this new commercial customer?
  3. Will I make payroll in 2 weeks?
  4. Should I take this loan/MCA offer in my inbox?

---

## 5. Customer Interview Questions

### Frequency (ask first — highest-value question, see section 1b)
0. **"How many new commercial customers did you take on in the last 90 days?"** — record the number verbatim for every interview. This determines the pricing model and possibly the whole product shape.

### Pain validation
1. "How often does a commercial customer pay late or not at all?"
2. "What's the biggest unpaid invoice you've had in the last 2 years?"
3. "Walk me through your process when a new commercial customer calls you."
4. "How do you decide whether to extend net-30 terms?"
5. "Have you ever walked away from a job because you were worried about getting paid?"

### Current behavior
6. "What tools or services do you currently use to check out a new customer? (Google? Their website? Word of mouth?)"
7. "Do you know what a business credit report is? Have you ever pulled one?"
8. "Have you heard of Levelset?"

### Willingness to pay
9. "If a tool could check a new customer in 30 seconds and tell you their risk before you took the job — what would that be worth to you per month?"
10. "What would have to be true for you to actually use it?"

### Open
11. "What's the most painful part of running this business that nobody seems to be solving?"

---

## 6. Customer Interview Log

Format: one entry per interview. Update within an hour of the call.

### Template
**Date:** YYYY-MM-DD
**Interviewee:** [First name], [trade], [city]
**Business size:** $X revenue, Y employees
**Channel:** (cold LinkedIn / warm intro / network / supply house / etc.)

**Key quotes:**
- "..."

**Current process:**
- ...

**Pain signal (1–5):**
- ...

**Willingness to pay signal (1–5):**
- ...

**What I learned that I didn't know:**
- ...

**Follow-ups they suggested:**
- ...

---

(No interviews completed yet. Goal: 5 by end of June 2026.)

---

## 7. Open Questions / TODO

- [ ] Send first 20 outreach messages. See `outreach_leads.csv` for candidate list.
- [ ] Complete 5 customer interviews — **record the 90-day new-commercial-customer count in every one**
- [ ] Verify the 🟡 stats in section 1
- [ ] Find a bad-debt figure specific to sub-$5M trade contractors (not all of construction) — IBISWorld, ASA, NACM
- [ ] Find the primary source behind "25% of business failures caused by customer non-payment"
- [ ] Confirm whether any carrier or broker writes trade credit insurance below $1M revenue
- [ ] Map every free data source for Duval County and document the scraping/API approach
- [ ] Try Levelset's free tier; document what they do and don't offer
- [ ] Pull a sample D&B report on a real business to see what it contains
- [ ] Check FL Sunbiz API/scraping rules and terms of use
- [ ] After 5 interviews: decide vertical (HVAC only first? all trades?) and MVP launch state(s)
- [ ] Decide: legal entity (LLC) before first paying user

---

## 8. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-13 | Focus on Option A (data platform) with Option B (open-source) on the side | Best matches builder identity + has clearer monetization than pure OSS |
| 2026-05-13 | Target: small commercial contractors in Florida first | Plays to my domain (mech eng, industrial), geography, and underserved segment |
| 2026-05-13 | Frame: builder/engineer first, Amex is context | I don't want to be locked into "credit risk expert" identity |
| 2026-05-18 | No code before 5 customer interviews complete | Customer discovery is the bottleneck right now, not engineering |
| 2026-09-14 | Mission statement formalized (section 0); insurance/guarantee layer explicitly parked | Founding insight is the Amex observation that contractors default because their own customers default. Insurance is attractive but converts the business from information to risk-bearing, triggering state insurance regulation. Revisit only after accuracy is measured. |
| 2026-09-14 | Pricing model is open, not assumed subscription | Severity of bad debt is now ✅ verified; frequency of the decision is not. If contractors evaluate only a few new commercial customers a year, subscription math fails and per-report or workflow-attached pricing fits better. Decide from interview data, not preference. |
| 2026-09-14 | Frequency is the #1 business risk, ahead of competition | Severe-but-rare pain does not sustain recurring revenue. Adding the 90-day new-customer-count question as the first question in every interview. |
| 2026-05-19 | Customer discovery is national; MVP launch is single-state (FL likely) | The pain is national — nothing about contractor cash flow stress is geographically specific. But the data is jurisdiction-fragmented: state business registries, county courts, and state-specific mechanic's lien laws make a multi-state product expensive to build. Open the funnel for interviews (LinkedIn cold to any US metro), keep the product geographically focused until paying users tell us where to expand. Phone and supply house channels remain Jacksonville-local. |

---

## 9. Sources Referenced

- The Financial Brand, "Who Will Fill the SMB Lending Gap?" (Sept 2025) — https://thefinancialbrand.com
- nCino, "The 2026 Growth Engine: Small Business Banking" (Jan 2026) — https://ncino.com
- FintechLabs, "Top 34 Digital Lenders to U.S. Small Businesses" (Mar 2026) — https://fintechlabs.com
- Levelset.com (various pages)
- Fintech.global, "Worth bags $30m to redefine small business financial services" (Mar 2026)
- Fintech Takes, "The Ideal Small Business Lender" (Jul 2024)
- Saasworthy.com — Levelset pricing data
- Crestmont Capital, Small Business Lending Statistics 2026
- Chaser, "Accounts receivable stats finance professionals need in 2026" (Jun 2026) — https://www.chaserhq.com/blog/accounts-receivable-stats
- Payra Resources, "What a Single Bad Debt Write-Off Actually Costs a Construction Distributor" (Apr 2026) — https://resources.payra.com/what-a-single-bad-debt-write-off-actually-costs-a-construction-distributor/
- Allianz Trade US, "What is trade credit insurance" (May 2026) — https://www.allianz-trade.com/en_US/what-is-trade-credit-insurance.html
- Impello Global, "Trade Credit Insurance for Small Businesses" (Mar 2026) — broker, interested party
- ICISA, "What Is Trade Credit Insurance?" (Jan 2026) — https://icisa.org/trade-credit-insurance/
- Levelset, "How to check a GC's credit before starting a construction project" — https://www.levelset.com/blog/how-to-check-general-contractor-credit/
