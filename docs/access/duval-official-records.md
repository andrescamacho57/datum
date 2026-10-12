# Access Report: Duval County Official Records (Clerk of Courts)

**Source:** Duval County Public Records Search — "Official Records" (Acclaim Web, by Aptitude Solutions / Harris Recording Solutions), operated by the Clerk of the Circuit and County Courts, Duval County, Florida
**Jurisdiction:** Duval County (Jacksonville), Florida
**Record types:** Recorded instruments — deeds, mortgages, judgments, **claims of lien, notices of commencement, satisfactions and releases of lien**, marriage licenses, and all other instruments Florida law authorizes to be recorded. **This is the recorded-instruments system, not the civil case docket.** See "Boundary with the civil case index" below.
**Investigated:** 2026-09-15T08:56Z – 2026-09-15T09:04Z (all fetch timestamps below are UTC)
**Verdict:** Usable, but scrape-only and **legally unresolved**. No bulk download, no API. The entire search UI sits behind a server-side click-through disclaimer that this recon deliberately did not accept. Construction liens are present and are the right record type, but the index is name-string only — no entity identifier — which pushes the whole entity-resolution burden onto Datum.

## Summary

Duval County's official records index is online, free, and covers 1988 forward, and it is the correct home for Florida construction liens (claim of lien, notice of commencement, satisfaction/release). But there is no bulk extract, no API, and no documented rate limit — retrieval means HTTP against an ASP.NET MVC search UI whose every search view redirects to a disclaimer page until a session accepts it. I did not accept that disclaimer on the owner's behalf, so I could not observe Duval's document-type code list, its party-type vocabulary, or its result-grid field layout; those are the three biggest gaps in this report and they are gaps of principle, not of effort. The decisive product finding is one I could establish without passing the gate: Florida statute caps what the index may contain at *"grantor and grantee names, party names, date, book and page number, comments, and type of record"* — there is no field in which a legal entity identifier could live, so a Duval lien can only ever be tied to a loosely typed name string.

## Bulk download

**Does not exist as a published product.** No data portal, no FTP or S3 drop, no purchasable index extract, no documented subscription feed.

What I checked:

- `https://or.duvalclerk.com/robots.txt` — HTTP 200, **zero-byte body** (fetched 2026-09-15T08:57:07Z). No sitemap, no data-file directory, no directives at all.
- `https://www.duvalclerk.com/robots.txt` — HTTP 200, single line `Sitemap: https://www.duvalclerk.com/site-map` (fetched 2026-09-15T08:56:52Z). Nothing else.
- The Official Records and Research department page (fetched 2026-09-15T08:58:00Z) describes only per-document retrieval: uncertified copies free to download online, $1/page from the office, eCertified copies at $2.00 certification + $6 processing + 3.5% card fee. No bulk offering is mentioned anywhere on it.
- The Public Information / public-records-request page (fetched 2026-09-15T09:01:11Z) is the only plausible bulk route. It states requests "may be submitted in person, via phone, via email, via facsimile, or through the mail," and that "If a records request requires extensive use of departmental resources or requires material costs, the Public Records Department will provide the requestor with an estimate of charges." Contact: (904) 255-1828, 501 W. Adams St., Room 2338, Jacksonville FL 32202.

**Open route worth pursuing before writing any scraper:** a Chapter 119 public records request asking the Clerk for a delimited export of the official records index (document type, recording date, instrument number, book/page, party names, party role) for a date range. Florida clerks commonly can produce this because F.S. 28.2221(2)(a) requires the index to be electronically exportable to a statewide search site — the statute says the website "has the capability of electronically providing the index data to a central statewide search site." That is an existing export capability the Clerk already maintains. Cost unknown; F.S. 119.07(4) special-service charges would apply. **This is one phone call and is almost certainly cheaper and safer than scraping.**

## API

**No official API.** Nothing on `duvalclerk.com` or `or.duvalclerk.com` advertises a developer API, key issuance, or machine-readable endpoint. There is no `/api` surface — `https://or.duvalclerk.com/api/DocTypes` 302s to `/api/Error/ViewNotFound` (probed 2026-09-15T08:58:00Z).

**Unofficial endpoints behind the site's own UI (label: unofficial, undocumented, liable to change without notice).** The app is ASP.NET MVC 5 on .NET Framework 4.8.4805.0. Confirmed by observation on 2026-09-15T09:03:18Z–09:03:59Z:

| Endpoint | Method | Observed behavior |
|---|---|---|
| `/search/SearchTypeName` | POST | Returns `ShowError('…')` JS fragments on validation failure. Accepts `PartyType` (confirmed — supplying it cleared the "Party type is required." error). |
| `/search/SearchTypeDocType` | POST | `ShowError( 'The doctype is invalid, please enter the correct doctype and try again.')` |
| `/search/SearchTypeRecordDate` | POST | `ShowError( 'The Record Date cannot be before 1/1/1753.')` |
| `/search/SearchTypeConsideration` | POST | `ShowError( 'Invalid Lower Bound Format.<br />Upper Bound is required.<br />From Record Date is incorrect.<br />To Record Date is incorrect.<br />')` |
| `/search/SearchTypeCaseNumber` | POST | `ShowError( 'The doctype is invalid…')` — i.e. case-number search is itself scoped by document type |
| `/search/SearchTypeInstrumentNumber`, `/search/SearchTypeBookPage` | POST | Unhandled `NullReferenceException` on an empty model; verbose ASP.NET stack trace returned (`customErrors mode="Off"`) |
| `/Search/ClearSession` | POST | Referenced in `/Scripts/AcclaimCommon.js` (fetched 2026-09-15T09:00:48Z) — resets the server-side search session |

Two things the stack traces gave away, both material:

1. The controller signatures are `SearchController.SearchTypeInstrumentNumber(SearchTypeInstrumentNumberModel model, Boolean captchaValid)` and `SearchController.SearchTypeBookPage(SearchTypeBookPageModel model, Boolean captchaValid)`. **A `captchaValid` flag is wired into the search actions in this build.** I did not observe a CAPTCHA render on any page I could reach, so I cannot say whether Duval has it enabled, enabled only above a request-rate threshold, or disabled. Treat "a CAPTCHA may appear on search submission" as a live risk, not a resolved one.
2. `customErrors` is off in production, so failures leak full stack traces. Useful for reverse-engineering; also a sign this deployment is not hardened, which argues for conservative request rates.

## Scrape-only access

**Search entry points** (all confirmed present in the nav markup of `https://or.duvalclerk.com/`, fetched 2026-09-15T08:57:07Z):

```
/search/SearchTypeName              Party Name (Grantor and/or Grantee)
/search/SearchTypeInstrumentNumber  Instrument Number
/search/SearchTypeDocType           Document Type(s)
/search/SearchTypeRecordDate        Single day of Official Records
/search/SearchTypeConsideration     Consideration range (upper & lower bound)
/search/SearchTypeBookPage          Book Type + Number + Page
/search/SearchTypeCaseNumber        Case Number
```

Notably **absent** from Duval's menu, though present in the vendor's generic Acclaim product (seen in the vendor screenshots inside `UsingAcclaimWebSearchFeatures.pdf`, fetched 2026-09-15T08:58:51Z): **Related Documents**, **Reference Number**, **Parcel (APN)**, **Remarks**, **Legal Description**, **Simple Search**. The first two matter — they are the vendor's cross-reference search types, and Duval does not expose them. See "Linking releases to the original lien."

**Request shape, as far as I could establish without passing the gate:**

- GET on any `/search/SearchType*` route → **302 to `/Search/Disclaimer?st=<original path and query>`** until the session has accepted the disclaimer. Query strings are preserved in the `st` parameter, so search URLs *are* expressible as GETs once a session exists.
- POST to the same routes is **not** redirected to the disclaimer — it reaches the controller and returns validation output. This is a gap in the gate, not a feature; see Access barriers.
- Name search requires, at minimum: a party type, a name, and **both ends of a record-date range**. Observed error on an empty POST: `Party type is required. Name is required. From Record Date is incorrect. To Record Date is incorrect.` Supplying `PartyType=Grantor` cleared the first error, confirming that parameter name.
- **The name parameter name was not determined.** I tried 15 candidates (`Name`, `PartyName`, `SearchName`, `LastName`, `Name1`, `FullName`, `SearchValue`, `NameValue`, `PartyName1`, `Party`, `SearchText`, `Names`, `PartyNames`, `LastNameFirstName`, `txtName`, `SearchNameValue`) and every one still returned "Name is required." It lives in the gated form markup. Deliberate method note: I kept the date fields set to `INVALID` on every probe so that no probe could ever return actual records.
- Date parameters are `RecordDateFrom` / `RecordDateTo` — these exact identifiers appear in `/Scripts/AcclaimCustom.js` (fetched 2026-09-15T09:00:48Z).

**Pagination and result addressing: could not determine.** The result grid is a Kendo UI grid (`/Scripts/kendo/2023.1.117/kendo.aspnetmvc.min.js`), which normally pages via a POST of `sort`/`page`/`pageSize`/`filter` to a server action, but I could not observe the actual grid data call. The vendor guide does document a **"Export to CSV"** button on the results grid and a print-report function — if that CSV export is enabled in Duval's build, it is by far the cleanest extraction path and should be the first thing tested once the disclaimer question is settled.

**Stable identifiers: partially.** Instrument number and Book/Page are stable, permanent identifiers and both have dedicated search routes, so a document *should* be re-addressable. But every attempt to hit a document-detail route directly failed: `/Document/DocumentDetails`, `/search/DocumentDetails`, `/Search/Results`, `/Search/GridData`, `/Image/Viewer` all 302 to `/Error/ViewNotFound` (probed 2026-09-15T09:02:43Z). The real detail route is reachable only from inside an accepted session, and the vendor guide shows document details opening in a **pop-up window**, which typically means a session-scoped URL rather than a permalink. **Assume for planning that a Duval official record is not linkable by a public permalink** — that is a direct problem for CLAUDE.md rule 3, which requires every fact to carry a URL pointing at the specific record. If no permalink exists, the citable URL for a Duval lien fact is the instrument number plus a reconstructable search, not a link, and that needs a product decision.

**Known index defect worth encoding in any parser** (verbatim from the site banner, fetched 2026-09-15T08:58:26Z): *"Documents that were recorded during the period January 1, 2004 through January 20, 2004 were recorded containing an extra zero with the Document #. This number has since been removed within our system. Example: 2004000555 now reads 200400555. It is recommended that when searching for documents that were recorded during these dates the user search using Grantor/Grantee or Book/Page."*

## Access barriers

Confirmed by observation:

- **Click-through disclaimer, server-enforced.** Every `/search/SearchType*` GET 302s to `/Search/Disclaimer?st=…`. Acceptance is `POST /search/Disclaimer` with `Disclaimer=true`, stored against the `ASP.NET_SessionId` cookie. **I did not send this POST.** Accepting a conditions-of-use gate on the owner's behalf is outside this recon's mandate, and it is exactly the decision that needs a human.
- **The disclaimer gate does not cover POST.** `POST /search/SearchTypeName` on a session that has never accepted the disclaimer returns controller validation output rather than a redirect (observed 2026-09-15T09:02:59Z). A retriever could therefore reach the search actions without ever accepting — which is *worse*, not better, than accepting. Routing around a gate is a materially different legal posture from clicking through it. Flag this explicitly for counsel.
- **Session state required.** `ASP.NET_SessionId` (HttpOnly) plus `ARRAffinity` (load-balancer stickiness). Anti-CSRF `__RequestVerificationToken` is issued as a cookie and embedded as a hidden field on the login form; whether the search forms also carry it is unobserved but likely.
- **JavaScript and cookies asserted as required.** The page renders a `<noscript>` banner reading "You must enable Javascript to continue" and a hidden `#cookiesDisabled` banner. In practice the HTML is server-rendered and the validation responses are plain text, so full JS rendering is probably *not* required for the index — but the results grid is Kendo-driven and may be.
- **CAPTCHA capability present in the build** (`Boolean captchaValid` in the search controller signature). Enablement in Duval unconfirmed. **Not attempted, and must never be solved.**
- **No login required for search.** A login exists at `/Login` for registered "agents" ("County registered users (agents) must use their agent key to login"), and `/Account/Register` 302s away, so self-registration appears closed. Agent accounts unlock saving and printing of images ("Saving a document requires an account that allows this action" — vendor guide). Basic index search and free uncertified image viewing do not require an account. **No account was created and no credential was used.**

Claimed but not confirmed:

- **No rate limit, per-day cap, or user-agent block is documented anywhere**, and I did not encounter one across roughly 35 requests over eight minutes from a single IP with a browser user-agent. That is far too small a sample to conclude none exists. Assume an undocumented throttle until proven otherwise; an unhardened ASP.NET app with verbose errors is not a system to hammer.

**Date-range limits — direct answer to the brief:**

- Name search: **a record-date range is mandatory**, both ends. You cannot ask "every lien ever filed against ACME LLC" in one call; you must window it. The maximum permitted span is unknown (the form's own limit is behind the gate) — this is the single most important unknown for cost modelling, because it determines whether one entity lookup is 1 request or 40.
- Record Date search: **explicitly a single day** — "Perform a Date search on a single day of Official Records." Backstop validation rejects dates before 1/1/1753.
- Consideration search: requires a record-date range *and* both bounds.
- **Index coverage begins 1988** (marriage licenses 1981). Pre-1988 records require staff assistance in person or by mail. For construction liens this is a non-issue — Florida claims of lien expire one year from recording absent a foreclosure suit (F.S. 713.08(5)), so anything actionable is recent.

## Terms of use

There is **no terms-of-use document, acceptable-use policy, or automated-access clause** governing `or.duvalclerk.com`. I looked at: the portal root, `/Search/Disclaimer`, `/Support`, both robots.txt files, the Clerk's site-policies page, and the Official Records and Public Information department pages. The three governing texts I found are quoted below in full, verbatim.

**1. The click-through gate on the records portal** — this is the only thing a user is asked to accept, and it is a liability disclaimer, not a use restriction:

> "The County presents the information on this web site as a service to the public. We have tried to ensure that the information contained in this electronic search system is accurate. County makes no warranty or guarantee concerning the accuracy or reliability of the content at this site or at other sites to which we link. Assessing accuracy and reliability of information is the responsibility of the user. The user is advised to search on all possible spelling variations of proper names, in order to maximize search results.
>
> The County shall not be liable for errors contained herein or for any damages in connection with the use of the information contained herein.
>
> If you choose not to accept the conditions stated above please exit this search application."
>
> — https://or.duvalclerk.com/Search/Disclaimer (identical text on https://or.duvalclerk.com/), retrieved 2026-09-15T08:58:26Z

**2. The Clerk's site-wide disclaimer**, which asserts copyright and browsewrap assent:

> "Copyright in the Material on this Web Site is owned by the Duval County Clerk of Court. You acknowledge and accept that your use of the Duval County Clerk of Court's Internet site indicates your acceptance of this disclaimer and the following Privacy Statement."
>
> — https://www.duvalclerk.com/site-policies, retrieved 2026-09-15T08:59:10Z

**3. The statutory basis for public online access**, which is the strongest thing in Datum's favour:

> "The county recorder in each county must provide a current index of documents recorded in the official records of the county for the period beginning no later than January 1, 1990, on a publicly available Internet website which must also contain a document requisition point for obtaining images or copies of the documents reflected in the index and which has the capability of electronically providing the index data to a central statewide search site. The index must be limited to grantor and grantee names, party names, date, book and page number, comments, and type of record."
>
> — Fla. Stat. § 28.2221(2)(a), http://www.leg.state.fl.us/Statutes/index.cfm?App_mode=Display_Statute&URL=0000-0099/0028/Sections/0028.2221.html, retrieved 2026-09-15T09:01:50Z

**Robots:** `https://or.duvalclerk.com/robots.txt` returns HTTP 200 with a **zero-byte body** (2026-09-15T08:57:07Z) — no `Disallow`, no `Crawl-delay`. `https://www.duvalclerk.com/robots.txt` contains only a `Sitemap:` line (2026-09-15T08:56:52Z). Under the standard, an empty robots.txt permits everything. Note that an empty file is at least as likely to be an oversight as a decision.

**Reading: restricted, and it needs legal review — but the restriction is narrow and specific.**

Automated access is **unaddressed** in the operative language. Nothing prohibits it, nothing rate-limits it, nothing distinguishes commercial from personal use, and robots.txt permits everything. The records are statutorily required to be public and online. That is a genuinely favourable baseline.

The problem is not what the terms say — it is the gate. Three distinct postures, and counsel should pick one before any code is written:

1. **Accept the disclaimer programmatically** (`POST /search/Disclaimer` with `Disclaimer=true` each session). Forms a click-wrap assent on Datum's behalf. The accepted text contains no use restriction, so there is little to breach — but it is still machine-formed assent, repeated per session, and the site-policies page separately asserts Clerk copyright in "the Material on this Web Site."
2. **Route around the gate via POST**, which demonstrably works. Do not do this. Deliberately circumventing an access control that the operator built is the fact pattern that turns a terms dispute into a CFAA-adjacent one, and it would be indefensible if the gate is ever tightened.
3. **Request the index under Chapter 119** and skip the website entirely. Slowest to start, cleanest to defend, and — given that F.S. 28.2221(2)(a) already obliges the Clerk to maintain an electronic index export — plausibly the shortest path to the data Datum actually needs.

CLAUDE.md rule 2 requires the clause quoted before a retriever is written. It is quoted. The clause does not resolve the question, so **this source goes to legal review**, and the question for counsel is narrow: may an automated retriever accept that per-session disclaimer, and does the Clerk's copyright assertion reach an index of public records?

**Consumer-data boundary:** clean. Official records are property and business instruments. Claims of lien against individually owned residential property will appear and will name natural persons — that is a public property record, not consumer credit data, and no FCRA permissible purpose is implicated. Per CLAUDE.md rule 2, Datum should still **not** build owner-level profiles from residential liens; the target is the commercial customer entity. Note separately that F.S. 28.2221(5)(a) bars the Clerk from publishing images of military discharges, death certificates, and family/juvenile/probate court files, and § 28.2221(2)(b) requires home street addresses exempt under § 119.071 to be stripped from the index — so a small, legally-mandated set of holes exists in the data. Do not treat index absence as evidence of non-existence.

## Fields available

**In the index (the searchable layer).** Capped by statute at: grantor and grantee names, party names, date, book and page number, comments, and type of record (F.S. 28.2221(2)(a), quoted above). The Clerk's own description of the register it maintains, from the Recording department page (fetched 2026-09-15T09:01:11Z): *"a registry that contains the names of the parties to the recorded instruments, the type of instrument, the filing number of the instrument, and the date and time of filing."* Instrument number and consideration amount are additionally searchable in this build, so they are indexed too.

**In the document image (the PDF, free to view and download uncertified).** For a construction lien this is rich, and it is defined by statute. F.S. 713.08(1) requires every claim of lien to state (retrieved 2026-09-15T09:04:20Z):

- (a) name of the lienor and service address
- (b) name of the person the lienor contracted with or was employed by
- (c) the labor, services, or materials furnished and the contract price or value
- (d) a description of the real property sufficient for identification
- (e) **the name of the owner**
- (f) dates of first and last item of labor/service/materials furnished
- (g) **the amount unpaid**, including unpaid finance charges
- (h) if not in privity with the owner, the date and method of service of the notice to owner

That is the payment-behaviour signal Datum wants — claimant, obligor, amount, dates, and the trade relationship — but **it is in the image, not the index**, so extracting it means OCR or PDF text extraction per document, not index parsing.

### Document types carrying construction-lien information

**Duval's document-type codes could not be observed** — the Doc Type search form is behind the disclaimer, and `POST /search/SearchTypeDocType` with no body returns only `ShowError( 'The doctype is invalid, please enter the correct doctype and try again.')`. That error proves Duval uses short coded doctype values validated server-side, but not what they are. Getting the list is one gated page view.

What is confirmed present, from the Clerk's own Recording and Official Records pages (fetched 2026-09-15T09:01:11Z and 08:58:00Z), which list *"claims of lien, satisfactions"* among recorded instruments and publish a downloadable Notice of Commencement form:

| Florida instrument | Statute | Role in the signal |
|---|---|---|
| Notice of Commencement | F.S. 713.13 | Recorded before work over $5,000 begins. Names owner, contractor, lender, surety. **Confirms a project exists and who the GC is** — the earliest signal, before any dispute. |
| Claim of Lien | F.S. 713.08 | **The core negative signal.** Contractor was not paid. Names claimant and owner, states amount unpaid. |
| Notice to Owner | F.S. 713.06 | Served, not generally recorded. Mostly absent from this system. |
| Satisfaction / Release of Lien | F.S. 713.21 | **Resolves the signal.** Without it, the lien stands. |
| Notice of Contest of Lien | F.S. 713.22 | Owner shortens the lienor's window to 60 days — an active dispute marker. |
| Notice of Termination | F.S. 713.132 | Closes out a notice of commencement. |

**Critical interpretive rule for any retriever:** under F.S. 713.08(5) a Florida claim of lien expires one year from recording unless a foreclosure action is commenced. So an unreleased two-year-old lien with no satisfaction is *not* necessarily an outstanding debt — it may simply have lapsed. Distinguishing "lapsed" from "foreclosed and still live" requires the **civil case docket**, which is a different system (see boundary note). Do not let a naive retriever report a stale lien as an open one; that is exactly the confidently-wrong output CLAUDE.md rule 3 and PROJECT_CONTEXT §6 exist to prevent.

### Are both claimant and owner searchable as parties?

**Almost certainly yes, and this is the good news.** F.S. 713.08(1)(a) and (e) require the claim of lien to name both the lienor and the owner; F.S. 28.222(2) requires the register to contain "the names of the parties"; F.S. 28.2221(2)(a) puts "grantor and grantee names, party names" in the public index; and the Clerk charges *"$1.00 for each name after the fourth"* for indexing, which only makes sense if every party name is indexed. Duval's Name search is explicitly described in its own UI as *"a Party Name (Grantor and/or Grantee) search"* and `PartyType` is a confirmed request parameter.

**What I could not confirm:** Duval's party-role vocabulary — whether a claim of lien indexes the claimant as Grantor and the owner as Grantee, the reverse, or as a neutral "party." Acclaim installs vary, and the convention is often counter-intuitive for liens. **Verify this against real records before building a directional query.** Searching the wrong role silently returns nothing, which a retriever will happily report as "no liens found." That failure mode is worse than an error.

### Can a lien be tied to a legal entity, or only to a name string?

**Only to a name string. This is the finding that matters most for Datum.**

The statutory index is capped at names, dates, book/page, comments, and record type. There is no field for a Sunbiz document number, no FEI/EIN, no state registration ID, no normalized entity key. A claim of lien is filed by whoever files it, spelling the debtor's name however they spell it — "ACME Construction LLC," "Acme Const. L.L.C.," "ACME CONSTRUCTION," or the DBA the contractor actually knew them by. The Clerk indexes that string and nothing else.

Concretely: Duval official records give Datum **no join key to Sunbiz whatsoever**. The bridge from "a lien exists against this name string" to "this lien belongs to the legal entity the contractor is about to extend net-30 to" is entirely Datum's problem, and it must be solved on name and property address alone. This is PROJECT_CONTEXT §6's viability question arriving in its hardest form, and it is the reason `AMBIGUOUS` has to be a first-class output rather than a nicety.

Two partial mitigants, both unverified here:

- **Property address / legal description.** F.S. 713.08(1)(d) requires a property description in the lien. If Duval's index exposes a legal-description or parcel field, it is a second axis for matching. Duval's search menu shows **no** Legal Description or Parcel search, unlike the vendor's generic product — so this may be document-image-only, reachable by OCR but not by query.
- **Notice of Commencement chaining.** An NOC names the owner *and* the contractor for a specific property. NOC → property → later claims of lien on the same property is a way to corroborate an identity that name matching alone leaves ambiguous. Worth prototyping.

### Linking releases to satisfactions — can an unreleased lien be told from a satisfied one?

**Mechanically yes; through Duval's exposed search types, not reliably.**

The vendor's own documentation confirms the data model supports it. `UsingAcclaimWebSearchFeatures.pdf` (fetched 2026-09-15T08:58:51Z) documents a **"Release Through"** column in the search results grid, with the note *"If you do not see the Release Through information, it may be due to a browser compatibility issue."* That is Acclaim's cross-reference field — the pointer from a lien to the instrument that released it. The vendor product also ships **"Related Documents"** and **"Reference Number"** search types.

**Duval exposes neither Related Documents nor Reference Number in its menu.** Its seven search types are Name, Instrument #, Doc Type, Record Date, Consideration, Book/Page, Case #. So the practical options are:

1. Read the **Release Through** column off the results grid, if Duval's grid renders it. Unverified — it is behind the gate. **Test this first;** if it is populated, the whole problem collapses into one extra column.
2. Fall back to correlation: search the party name for satisfactions/releases and match them to claims of lien by claimant + owner + property. Lossy and ambiguous.
3. Read the satisfaction's document image. F.S. 713.21 satisfactions conventionally recite the OR book and page of the lien being released, which is an exact link — but it costs an OCR pass per document.

Until option 1 is verified, **assume linkage is not free**, and treat "no satisfaction found" as `AMBIGUOUS` rather than "lien is outstanding." An unreleased lien and a satisfied one mean opposite things about a customer, and a false "unpaid" is precisely the wrong-and-confident output that PROJECT_CONTEXT §6 identifies as a lawsuit rather than a bug.

### Boundary with the civil case index

This report covers **recorded instruments only**. Duval's civil case docket is a separate system with separate access — the agent covering it should own it. Two places the two systems touch, both of which need a joint decision:

- **`/search/SearchTypeCaseNumber`** exists *in this system*. It searches recorded instruments that carry a court case number — recorded judgments, lis pendens, certified copies of orders. It is not a docket search and will not show pending cases. Its validation error mentions doctype, so it is doctype-scoped.
- **Lien foreclosure is the real overlap.** Whether a claim of lien is still live after one year depends on whether a foreclosure suit was filed (F.S. 713.08(5)) — which lives in the civil docket, not here. **Neither system alone can tell you whether a lien is enforceable.** Any product claim about lien status needs both, and that should be stated explicitly rather than discovered during implementation.

## Example URLs

Both fetched and verified in this run. Both load in a browser with no account.

1. **`https://or.duvalclerk.com/Search/Disclaimer`** — the gate itself. Returns HTTP 200, 9,857 bytes, containing the full disclaimer text quoted above and the acceptance form. Fetched 2026-09-15T08:58:26Z.
2. **`https://or.duvalclerk.com/Documents/Support/UsingAcclaimWebSearchFeatures.pdf`** — the vendor's search guide, served ungated. HTTP 200, `application/pdf`, 1,922,201 bytes, 20 pages. Source of the "Release Through" and CSV-export findings. Fetched 2026-09-15T08:58:51Z.

**Neither is entity-specific, and that is the point.** A URL for a real lien against a real company would have required accepting the disclaimer, which this recon did not do. Once that decision is made by a human, the first entity-specific URL to capture is a Doc Type search restricted to the claim-of-lien code over a recent date window.

**Generalized patterns** (unofficial; derived from observation, not documentation):

```
Gate (server-enforced on every search GET):
  GET  https://or.duvalclerk.com/search/SearchType{Name|InstrumentNumber|DocType|RecordDate|Consideration|BookPage|CaseNumber}
    -> 302 https://or.duvalclerk.com/Search/Disclaimer?st=<urlencoded original path+query>

Acceptance (NOT performed in this recon):
  POST https://or.duvalclerk.com/search/Disclaimer
  Body: Disclaimer=true
  Binds to: ASP.NET_SessionId cookie (+ ARRAffinity for LB stickiness)

Name search (parameter names partially determined):
  POST https://or.duvalclerk.com/search/SearchTypeName
  Body: PartyType=<confirmed param; value vocabulary UNKNOWN>
      & <name param UNKNOWN — 15 candidates rejected>
      & RecordDateFrom=<M/D/YYYY>
      & RecordDateTo=<M/D/YYYY>          # both mandatory
      [& __RequestVerificationToken=<likely required>]

Document type search:
  POST https://or.duvalclerk.com/search/SearchTypeDocType
  Body: <doctype code(s)> — codes validated server-side, VOCABULARY UNKNOWN

Session reset:
  POST https://or.duvalclerk.com/Search/ClearSession

Detail pages: no public permalink found. /Document/DocumentDetails, /search/DocumentDetails,
/Search/Results, /Search/GridData, /Image/Viewer all 302 -> /Error/ViewNotFound.
```

## Raw response excerpt

Three captures, actual returned bytes, trimmed as noted.

**(a) The disclaimer gate.** Full response headers plus the first bytes of the redirect body from `GET https://or.duvalclerk.com/search/SearchTypeName` on a fresh session, 2026-09-15T08:57:40Z. Untrimmed except that the trailing HTML boilerplate of the ASP.NET "Object moved" stub is cut after the first line:

```http
HTTP/2 302
cache-control: no-cache
pragma: no-cache
content-length: 2955
content-type: text/html; charset=utf-8
expires: -1
location: /Search/Disclaimer?st=/search/SearchTypeName
x-frame-options: SAMEORIGIN
x-powered-by: ASP.NET
access-control-allow-origin: *
x-powered-by: ARR/3.0
date: Tue, 15 Sep 2026 08:57:40 GMT

<html><head><title>Object moved</title></head><body>
```

**(b) The acceptance form**, exact bytes from the body of `GET https://or.duvalclerk.com/` (18,377 bytes total), 2026-09-15T08:57:07Z. This is the entire `<form>` element; surrounding disclaimer prose is trimmed because it is quoted verbatim in Terms of use above:

```html
    <form action="/search/Disclaimer" method="post">
        <input type="hidden" name="Disclaimer" value="true" />
        <div style="text-align:right; display:block;">
            <input type="submit" id="btnButton" value="I accept the conditions above." class="t-button" />
        </div>
    </form>
```

**(c) Search-action validation output.** Complete response bodies (they are this short) from POSTs made 2026-09-15T09:02:59Z–09:03:34Z. These are the only responses the search actions gave up without an accepted disclaimer, and they are what established the parameter names and the mandatory date range. Nothing is trimmed:

```
$ curl -X POST -d "PartyName=SMITH" https://or.duvalclerk.com/search/SearchTypeName
ShowError( 'Party type is required.
Name is required.
From Record Date is incorrect.
To Record Date is incorrect.
')

$ curl -X POST -d "PartyType=Grantor" -d "PartyName=ACME" \
       -d "RecordDateFrom=INVALID" -d "RecordDateTo=INVALID" \
       https://or.duvalclerk.com/search/SearchTypeName
ShowError( 'Name is required.<br />From Record Date is incorrect.<br />To Record Date is incorrect.<br />')

$ curl -X POST -d "" https://or.duvalclerk.com/search/SearchTypeDocType
ShowError( 'The doctype is invalid, please enter the correct doctype and try again.')

$ curl -X POST -d "" https://or.duvalclerk.com/search/SearchTypeRecordDate
ShowError( 'The Record Date cannot be before 1/1/1753.<br />')

$ curl -X POST -d "" https://or.duvalclerk.com/search/SearchTypeConsideration
ShowError( 'Invalid Lower Bound Format.<br />Upper Bound is required.<br />From Record Date is incorrect.<br />To Record Date is incorrect.<br />')
```

And the line from the verbose stack trace that revealed the CAPTCHA parameter, from `POST /search/SearchTypeInstrumentNumber` with an empty body, 2026-09-15T09:03:34Z (one line extracted from a ~7KB ASP.NET error page):

```
[NullReferenceException: Object reference not set to an instance of an object.]
   AptitudeSolutions.AcclaimWeb.View.Controllers.SearchController.SearchTypeInstrumentNumber(SearchTypeInstrumentNumberModel model, Boolean captchaValid) +440
```

## Open questions

Everything below is unresolved because it sits behind the disclaimer, which this recon did not accept. **Each item is one gated page view away** — a person accepting the disclaimer in a browser and reading the form markup would close the entire list in about twenty minutes. That is the single highest-value next action for this source.

1. **Duval's document-type codes for construction liens.** What code is a claim of lien, a notice of commencement, a satisfaction? Server-side validated, vocabulary unknown. Blocks the most efficient query path (Doc Type + date range).
2. **`PartyType` values, and the name parameter's actual field name.** 15 candidates rejected. Both are in the gated form markup.
3. **Party-role convention for liens.** Is the claimant Grantor and the owner Grantee, or reversed? Guessing wrong returns silent empty results.
4. **Is the "Release Through" column populated in Duval's grid?** If yes, lien-to-satisfaction linkage is free and this source becomes substantially more valuable. If no, every lien status needs a document-image read.
5. **Is CSV export enabled?** The vendor ships it. If Duval enables it, extraction is dramatically simpler and gentler on the server.
6. **Maximum date-range span on a name search.** Determines whether one entity lookup costs 1 request or 40, and therefore whether per-lookup pricing works.
7. **Is a CAPTCHA enabled, and at what threshold?** `captchaValid` is in the controller signature. If it fires on volume, automated retrieval is dead and the Chapter 119 route becomes the only option. **Must never be solved — if it appears, stop.**
8. **Is there a document permalink?** If not, CLAUDE.md rule 3's "URL points at the specific record" needs a product answer for this source.
9. **Will the Clerk sell or produce an index extract?** One phone call to (904) 255-1828. Would moot items 1–8 entirely and is the cleanest legal posture available. **Do this before writing a scraper.**
10. **Actual rate limits.** ~35 requests over 8 minutes drew no throttle. Meaningless as evidence.

---

*Investigated 2026-09-15, 08:56Z–09:04Z. No disclaimer was accepted, no account was created, no credential was used, no CAPTCHA was encountered or attempted, and no record data was retrieved. Probes against search actions were deliberately constructed with invalid date values so that no probe could return records. Implementation of a retriever is a separate job for a different agent, and per CLAUDE.md rule 2 it should not begin until the legal question in Terms of use is answered.*
