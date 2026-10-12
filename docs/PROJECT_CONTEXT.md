# Datum — Project Context

> **Read this first.** Single source of truth for what this project is, who I am, and where we are. Update it as decisions are made. Anyone (or any AI) joining this project reads this top-to-bottom before doing anything else.

**Last updated:** 2026-10-12
**Owner:** Andres
**Status:** Building version one (Florida, commercial clients). Outreach runs in parallel.
**Approved decisions live on the Agenda dashboard (Decisions tab). If this file disagrees with it, the dashboard wins.**
**Companion docs:** `research_log.md` (facts, sources, decisions), `Customer_Discovery_Outreach_Playbook.md`, `data_feasibility_spikes.md`, `interview_synthesis_onepager.md`

---

## 1. Mission

**Founding insight (from 5 years at Amex):** Contractors default on their own credit lines because their customers fail to pay *them*. They are absorbing someone else's credit risk without knowing it, and without any of the tools a lender would use.

**Mission statement:**

> Every time a contractor takes a net-30 job, they're lending money. Datum is the underwriting they never had.
>
> Datum pulls the public record on a commercial customer — business registry, court judgments, mechanic's liens, UCC filings — ties it to the correct legal entity, and lays it out in plain language *before the job is accepted*. Every fact carries a source and a date. When the evidence is thin, Datum says so instead of guessing.

**Plain-English version (say this to a contractor):**

> "Find out whether they pay their bills, before you take the job."

**Three commitments:**
1. Every fact carries a source link and a fetch date. No black-box score.
2. An honest "can't tell" beats a confident wrong answer. Abstention is a valid, expected output.
3. Analysis, not advice. The contractor decides.

**Datum is not:** a lender, a collections agency, a lien filer, or a credit bureau.

### Version one sources (decided 2026-10-12)

The mission names every source Datum will eventually cover. Version one ships a narrower set, in this order:

1. **Sunbiz bulk files**: company filings, fictitious names (DBAs, "doing business as" names), and federal tax liens. Free and complete, published by the state over SFTP (secure file transfer) as a quarterly full snapshot plus daily changes.
2. **DBPR (Department of Business and Professional Regulation) contractor licenses**: free download files. Delinquent and involuntarily inactive licenses are left out, so "not found" doesn't mean "never licensed."
3. **One county's recorded liens**, piloted with human review.

**Version 1.1:** county civil court records, UCC (Uniform Commercial Code) filings, federal bankruptcy.

**Why this order.** Entity resolution comes first, and the registry is its spine: a lien or judgment only means something once it's tied to the right legal entity, and Sunbiz is the official list of which companies exist. It's also the only source that is free, bulk and complete, so the 50-name test set can run offline and give the same answer every time. The fictitious-name file carries each DBA owner's document number, so linking "Donnie Riddle Plumbing & Htg" to its legal entity is a join, not a guess (✅ confirmed in `docs/access/sunbiz.md`). Liens come second because they're the most direct non-payment signal. Courts wait because access varies county by county and the clean path (Trellis) is paid and usage-based, against a ~$100/month budget.

### Why the mission says "underwriting" and not "a lookup tool"

Deliberate. Underwriting covers both halves of what a lender does: the decision at origination *and* ongoing review of accounts already on the books. That gives the mission room for the monitoring product (section 4) without committing to it before it's validated. Don't narrow this wording to a single feature.

### Parked: the guarantee / insurance layer

Long-term vision is coverage tied to the risk profile — better terms on low-risk jobs, no coverage plus a recommendation to walk on high-risk ones. A guarantee signals confidence in the assessment and is how you sell a number nobody asked for.

Deferred, deliberately. It converts Datum from an information business into a risk-bearing one, which triggers state insurance regulation and capital requirements. Revisit only after accuracy is measured.

Worth noting: 🟡 Allianz Trade designs trade credit insurance for businesses with sales of at least $5M/year, occasionally down to $1M. The persona below is structurally excluded from every major carrier. That gap is real and it is the strongest long-term argument for Datum becoming more than a lookup tool. (See `research_log.md` section 2.)

---

## 2. Who I Am

- **Background:** Mechanical engineering, University of Florida, 2019
- **Work history:** 1 year data engineer at Messer Americas; 5 years credit risk management for small business cards at American Express
- **Credentials:** Coursera certificates in Snowflake and dbt
- **Direction:** Data engineering and AI; builder/engineer/entrepreneur
- **Tools:** Claude Pro, ChatGPT Pro, Gemini, Copilot, VS Code
- **Location:** Jacksonville / Saint Johns, Florida
- **Budget reality:** ~$100/month short-term; can scale to $500–1000/month with proven traction. **No large short-term expense risk.**

### Positioning (important)

I am **a data engineer and builder** who happens to have credit risk domain experience from Amex. The Amex experience is *context that explains why my tools are credible*, not my identity. Never "former Amex credit risk officer." The noun is *engineer/builder*.

**Headline framing:** "Data engineer building tools for risk decisioning. Mech eng → data eng. 5 years inside Amex SMB risk."

---

## 3. The User

**Mike, 42, owns "Mike's HVAC" in Jacksonville**
- $800K annual revenue, 5 employees
- 60% residential / 40% light commercial
- QuickBooks Online; bookkeeper monthly, CPA annually
- Carries ~$35K on an Amex Business Platinum
- When a new commercial customer asks for net-30, Mike decides by gut

🔴 **Open persona question:** most published payment-risk data describes *subcontractors working under general contractors*, not HVAC/plumbing shops doing direct light-commercial work. These may be different risk profiles with different buying behavior. Test in interviews.

---

## 4. The Biggest Open Risk: Frequency

Severity of the pain is ✅ verified (see `research_log.md` section 1). Construction has the worst payment timing of any sector — 100% of invoices paid late. 9.1% of construction businesses write off more than 14% of annual revenue. At a 3.4% net margin, a $15K write-off requires over $200K in new revenue to recover.

**Frequency is not verified, and it is the most likely way this fails.** A pain that is severe but rare does not sustain a recurring product. If Mike takes on two new commercial customers a year, a tool that's brilliant twice a year gets cancelled in month three. That, not Levelset, is the real threat.

**The first question in every interview:**

> "How many new commercial customers did you take on in the last 90 days?"

Record the number. It determines the pricing model and possibly the whole product shape.

### Product concepts responding to the frequency risk

Not decisions. To be pressure-tested in interviews, not built.

1. **Monitoring, not just lookups.** Watch the customers Mike *already has* — new liens, new judgments, payment-timing drift — instead of only checking new ones. Converts a twice-a-year decision into weekly value. This may turn out to be the actual product, with the pre-job check as the demo.
2. **Be the credit application.** Contractors extending net-30 usually have customers fill out something. If Datum *is* that form and auto-enriches on submit, it lives inside an existing workflow instead of being another tool to remember.
3. **Sell to supply houses.** Ferguson, Johnstone, Winsupply extend credit to contractors daily. Same engine, buyer with far higher decision frequency. Overlaps an outreach channel already in the playbook.
4. **Contractor-reported payment experiences as a data flywheel.** Public records are a commodity; contractor-reported payment behavior compounds. BICA has done this since 1903 on old technology. ⚠️ Defamation and accuracy exposure — legal review before any contractor-submitted content is shown to another user.

---

## 5. Pricing: Open, Not Assumed

Previously assumed $29–49/month subscription. **That assumption is withdrawn until interviews produce a frequency number.**

- High decision frequency → subscription works
- Low frequency → per-report, or attach to something touched weekly

Per-report also fits the cost structure better: costs are per-lookup, so revenue probably should be too. A subscription asks me to eat variable cost against fixed income before I know the usage curve.

**Underlying goal:** build something genuinely useful. Reasonable profitability follows usefulness. But "useful" for a 5-person shop means *useful this week* — that's a usefulness constraint, not a monetization one.

---

## 6. The Technical Core: Entity Resolution

Every version of this product, at any price, for any trade, needs to match a loosely typed business name to the correct legal entity across messy public sources full of DBAs and name variants. Is "Riddle Plumbing LLC" the same entity as "Donnie Riddle Plumbing & Htg"?

**This is the viability question.** A risk report run on the wrong "John's Plumbing" is worse than no report — it's confidently wrong, which destroys trust instantly and is a lawsuit, not a bug.

**Design principles (settled):**
- **Workflow first (approved 2026-10-11).** Plain code for every predictable step: download, parse, normalize, score candidates, deterministic joins. A single model call only for close name matches the scorer can't separate. An agent only for long-tail lookups, always behind human review.
- **Move model judgment from runtime to build time** wherever the answer is stable. A model reads an unfamiliar county page layout *once*, in development, and emits a parser config that gets reviewed and committed. Production lookups then run deterministic code, and a layout change becomes a test failure instead of a silent wrong answer.
- **Three-state output, not two:** `CONFIRMED` / `AMBIGUOUS` / `NO_MATCH`. `AMBIGUOUS` is a first-class success — it's the human checkpoint, implemented in the type system rather than bolted on.
- **Accuracy is a measured number, not a vibe.** A 50-name hand-checked test set. Nothing is shown to a contractor as fact until matching scores 90% or better on it. `wrong_match` is the metric that matters most; a wrong confident match is the lawsuit, a wrong abstention is a mild annoyance.
- **Every report line links to its official record.**

**Deferred:** MCP (Model Context Protocol) wrappers — indirection with one consumer. Multi-agent orchestration — single well-built agent first. Both revisit when there's evidence they beat the simpler thing.

**Runtime vs. dev-time tooling:** use Claude Code / the Claude Agent SDK to *build* Datum. Use the Client SDK (direct API, own tool loop) for Datum's *runtime* agent — an entity-adjudication agent has no business holding a bash tool.

### Stack (approved 2026-10-11)

- **Pipeline:** Snowflake + dbt, layered raw → staging → marts. Raw keeps each source line exactly as downloaded; staging parses it into fields; marts serve lookups.
- **Cost guardrails:** X-Small warehouse, 60-second auto-suspend, and a resource monitor that caps monthly credits so a mistake can't run up a bill.
- **App:** Postgres behind a mobile-friendly web app. Native iPhone and Android apps later, when users need push notifications or offline use.

---

## 7. Strategy

**Phase 1 (now, ~$100/month plus capped Snowflake spend):** Contractor-facing checks on commercial clients. Florida and commercial clients only. Expand to more states after 10 paying users.

**Phase 2 (with traction, ~$500/month):** Whichever of the section 4 concepts interviews justify. Possibly cash flow integration (Plaid/QuickBooks), possibly monitoring, possibly supply houses.

**Phase 3 (12–24 months):** Sell the underlying engine (data + scoring API) to community banks and credit unions serving trade SMBs. Where larger revenue lives.

### Build-in-public engineering visibility

Open-source small components to build engineering reputation: a dbt package for credit risk feature engineering, an entity-resolution library for business registries, a Python tool for FL Sunbiz / county clerk records. LinkedIn framed as "builder shipping," not "expert sharing wisdom."

---

## 8. Where I Am Right Now

**Done:** wedge and persona identified; competitive landscape mapped; mission formalized; severity of the pain verified with sources; frequency named as the #1 risk; outreach scripts drafted; source recon for Sunbiz and Duval County (`docs/access/`); version-one scope, sources and stack approved (2026-10-11).

**In progress:** the version-one pipeline, starting with one Sunbiz daily file loaded end to end (raw → staging → mart → lookup). Outreach in parallel, leading with a free report and a $50 gift card for 15 minutes.

**Interviews logged:** zero. Nothing is validated yet. Building doesn't change that; only contractor conversations do.

### How build and outreach fit together

Build and outreach run in parallel. There is no interview gate on writing code.

---

## 9. Competitive Landscape (summary — full version in `research_log.md`)

- **Levelset** (Procore, 2021, ~$500M) — post-job lien rights. $149+/month. Already publishes contractor-facing "check the GC's credit before bidding" content, so the pre-job *framing* isn't novel ground.
- **D&B, Experian Business, Equifax Business, Cortera** — commercial credit bureaus. $40–200/report, enterprise audience.
- **Creditsafe, Worth.ai, Middesk, JUDI.AI** — modern fintech, lender-facing.
- **BICA** (since 1903) — regional trade association, shared credit info, old technology.
- **Allianz Trade, Atradius, Coface** — trade credit insurance, floor at ~$1–5M revenue.

**The gap:** small commercial contractor + pre-job + affordable + below the insurance floor. Real but not virgin.

**Standing caveat:** all of the above is what vendors *sell*, not what Mike *buys*. Supply-side evidence proves companies believe there's money here. It does not prove the user has heard of any of it.

---

## 10. Open Questions

- Frequency: how often does a contractor actually make this decision? (**#1**)
- Does the quarterly Sunbiz snapshot include inactive and dissolved companies? A dissolved client is one of the strongest signals; if bulk omits them, they need another path.
- Per-report vs. subscription vs. workflow-attached
- Is monitoring the real product, with pre-job as the demo?
- Sub-$1M trade credit insurance — does anyone write it?
- Legal exposure if an assessment is wrong (lawyer before launch; never frame as "advice")

**Closed:** Florida first (decided 2026-10-11). Trade first: not needed (decided 2026-10-12). The data describes the client, not the contractor's trade, so the build is the same for every trade. Record each interviewee's trade and watch for clusters.

---

## 11. Explicitly Not Doing

Not building a lending product. Not giving financial advice. Not competing head-on with Levelset's lien rights product. Not bearing insurance risk. Not selling to enterprise yet. Not raising money. Not hiring. Not incorporating until there's a paying user in sight.

---

## 12. Regulatory Posture

Datum stays on **business and public records only**. Public business records (state registries, court records, liens, UCC filings) are not consumer credit reporting and carry no FCRA (Fair Credit Reporting Act) permissible-purpose requirement. The moment personal credit on an owner is pulled, FCRA applies and consent or permissible purpose is required.

**That line is not crossed without legal review.** Related flags: a site's terms of use may restrict automated access even when the records are public ("it's public" ≠ "I can scrape it however I want"); surface public-record *facts*, never editorialized conclusions; frame every output as analysis or decision support, never advice.

**Personal data inside business records.** Officer, registered-agent and DBA-owner records name real people, often with home addresses. Use them only to confirm that two filings belong to the same company. No person search, no person-centric index, no gathering one individual's records across sources.
