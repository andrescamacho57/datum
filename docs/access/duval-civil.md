# Access Report: Duval County Clerk of Courts — Civil Case Index (CORE)

**Source:** CORE — Clerk Online Resource ePortal, Duval County Clerk of the Circuit and County Court (`core.duvalclerk.com`)
**Jurisdiction:** Duval County (Jacksonville), Florida — 4th Judicial Circuit
**Record types:** Court **case index and docket** for Circuit Civil (`CA`), County Civil (`CC`), Small Claims (`SC`), and Appeals (`AO`), plus every other division the Clerk maintains. Party names and roles, case type, division, status, judge, attorneys, party addresses, court events, court fees assessed/paid, full docket text, and links to released document images.
**Investigated:** 2026-09-15, 08:56Z – 09:03Z (all fetch times below are UTC on 2026-09-15)
**Verdict:** Technically wide open and very high value — an undocumented JSON endpoint serves full civil party-name search and case dockets to anonymous users with no login, no captcha on the requests I made, and no user-agent filtering. **But automated querying is not ours to take: the Florida Supreme Court order that governs this system requires the court and clerk to authorize any automated search program, and limits authorized programs to the indices only.** Usable only after written authorization. Legal review required before a retriever is written.

## Summary

CORE exposes exactly what Datum needs: a business entity can be searched as a named party across civil case types, and the result set carries case number, all parties with role codes, case type, division and status. Retrieval is trivially automatable — the site's own UI is a thin JavaScript shell over an ASP.NET `.asmx` JSON web service that answers anonymous `PublicLogin` with a null-GUID token good for search and case retrieval. I ran three real searches and three real case retrievals in under three minutes without tripping a captcha.

The blocker is not technical. It is AOSC24-65, the Florida Supreme Court's *Standards for Access to Electronic Court Records*, which states that only **authorized** automated search programs may be used, only on the indices, and that the court and clerk determine and may revoke that authorization. The same order directs clerks to "[m]onitor bulk data transfers to identify and mitigate abuses of the system by utilizing access programs using automated methods," which is almost certainly what the server-side adaptive captcha in CORE implements.

Second material finding: **judgment amounts are not in the index.** The docket records that a final judgment was entered and where it was recorded, but the dollar figure lives only inside the PDF. What the index does give you, free and structurally, is the *claim band* from the case-type code (e.g. "COMPLAINT ON CONTRACT OR OTHER DEBT - $15000 - $30000"). Documents are free to view once the Clerk has released them; only *certified* copies cost money.

Boundary with the parallel recon: this report covers the **court case index only**. When a Duval money judgment becomes a lien it is recorded into Official Records (`or.duvalclerk.com`, HTTP 200 at 09:03Z) and the CORE docket line literally hands you the crosswalk — `DEFAULT FINAL JUDGMENT BOOK 21759 PAGE 1110-1112`. That book/page is the other agent's system, not mine.

---

## Bulk download

**No self-service bulk download, no data portal, no FTP or S3 drop.** There is, however, a formally defined bulk route that the Clerk can grant.

AOSC24-65 defines **User Role 11 — "Commercial purchasers of bulk records"** as a first-class access role:

> "All records except those that are expunged or sealed, automatically confidential under rule 2.420(d)(1), Fla. R. Gen. Prac. & Jud. Admin., or made confidential by court order.
>
> No remote access to images of records in cases governed by the Florida Family Law Rules of Procedure, Florida Rules of Juvenile Procedure, or Florida Probate Rules, pursuant to §28.2221(5)(a), F.S."
>
> User security requirements: "Secure access through username and password by written notarized agreement. The commercial purchaser gatekeeper is responsible for maintaining an authorized user list."
> — *Standards for Access to Electronic Court Records*, Sept. 2024, User Role 11 table, in AOSC24-65, https://flcourts-media.flcourts.gov/content/download/2440532/file/AOSC24-65.pdf, retrieved 2026-09-15 ~09:04Z

I did **not** pursue this — it requires creating an account and signing an agreement, which is outside my constraints. This is the single most promising legitimate path and someone with signing authority should price it with the Clerk directly.

The generic public-records-request route exists at https://www.duvalclerk.com/services/public-information (requests accepted "in person, via phone, via email, via facsimile, or through the mail"), with fees described only as: "If a records request requires extensive use of departmental resources or requires material costs, the Public Records Department will provide the requestor with an estimate of charges." No format, cadence, or price for a data extract is published. Whether they will produce a civil-index extract at all is unanswered.

**Cadence, format, cost: could not determine.** Nothing published. It takes a phone call or written request to the Clerk's Public Records Department to find out.

## API

**No official, documented public API.** Nothing on `duvalclerk.com` advertises one, there is no developer page, and no key issuance process exists.

**Unofficial JSON endpoint behind the site's own UI — confirmed working, and liable to change without notice.** Everything below was observed directly, not inferred.

Base: `https://core.duvalclerk.com/internal/CoreWebSvc.asmx`
The ASP.NET service description page enumerates all 28 operations and is publicly readable (HTTP 200, 8,412 bytes, fetched 08:59Z). All calls are `POST` with `Content-Type: application/json; charset=utf-8`; responses are JSON with the payload under a `"d"` key.

The operations that matter:

| Operation | Arguments | What it does |
|---|---|---|
| `PublicLogin` | `{}` | Returns an anonymous session. Token is the literal null GUID `00000000-0000-0000-0000-000000000000`. |
| `GetNewSearchTab` | `token`, `returnTabId` | Returns the search form as an HTML fragment — this is where the full case-type and court-type code lists come from. |
| `CaseSearchBegin` | `token`, `returnTabId`, `inputs`, `captcha` | Runs the search. Returns page 1 (25 rows) as server-rendered HTML inside the JSON envelope. |
| `CaseSearchUpdate` | `token`, `returnTabId`, `operation`, `requestState`, `captcha` | Pagination. `operation` ∈ `NextPage`, `LastPage`, etc.; `requestState` is the base64 blob from the previous response. |
| `GetCaseById` | `token`, `returnTabId`, `caseID`, `simCtrl` | Full case detail page. `simCtrl` **must be `0`** — passing `null` returns HTTP 500 (observed at 09:00:56Z, corrected at 09:01:33Z). |
| `GetCaseByUcn` | `token`, `returnTabId`, `ucn`, `simCtrl` | Same, addressed by uniform case number. |
| `BeginImageLoad` / `GetImageLoadStatus` | request object / `requestKey` | Two-step async job that materializes a document PDF. |
| `RequestDocumentReview` | `token`, `returnTabId`, `caseId`, `docketId` | Asks a clerk to review + redact an unreleased document. **Registered accounts only.** |

**Free.** No key. **No documented rate limit anywhere.** Response format is JSON-wrapped HTML, not structured data — every field has to be parsed out of markup, so a layout change is a silent breakage unless it is fixtured and tested (CLAUDE.md §4 applies hard here).

## Scrape-only access

There is no "scrape the search UI" path distinct from the JSON service — the UI *is* the JSON service. Documenting the request shape as it actually is:

**Search — `POST /internal/CoreWebSvc.asmx/CaseSearchBegin`**

The `inputs` object is built client-side by `getUserSearchInput()` in `https://core.duvalclerk.com/Scripts/CoreCms.js`. Accepted keys (from the guard clause in `getCaseSearch()`): `CaseYear`, `CaseType`, `CaseNumber`, `Division`, `LastName`, `FirstName`, `MiddleName`, `DateOfBirth`, `SaNumber`, `CountyId`, `IncidentNumber`, `OffenderNumber`, `DlNumber`, `CitationNumber`, `CaseTypeList`, `NcicGroup`, `ePortalFilingNumber`, `FileDate`, `ArrestDate`, `CaseAge`, `LastActivity`, `Agency`, `BarNumber`, `BadgeNumber`, `CaseMemberFilter`, `WarrantTypeID`, `WarrantClosed`, `WarrantNumber`. Plus `CaseParty`, `SortBy`, `UseNamePhoneticMatchOption`, `UseNameBeginsWithOption`.

**A business entity goes in `LastName`.** There is no separate organization-name field; CORE stores a corporate party as a single surname-position string.

Name-matching modes, which matter a great deal for entity resolution:

| Mode | `UseNamePhoneticMatchOption` | `UseNameBeginsWithOption` |
|---|---|---|
| Phonetic/full-text (**site default**) | `true` | `false` |
| Basic/full-text | `false` | `false` |
| Basic/begins-with | `false` | `true` |

The site default is *phonetic*. For Datum that is the wrong default — phonetic matching on business names will pull in noise and inflate `wrong_match`. Use `BasicBeginsWith` for candidate generation and do the fuzzy scoring in our own code where it is testable.

Court type codes (`CaseType`): `CA` Circuit Civil, `CC` County Civil, `SC` Small Claims, `AO` Circuit Civil other. `CaseTypeList` takes the comma-joined numeric IDs from the case-type dropdown. The business-debt-relevant ones:

| Case type | IDs |
|---|---|
| Complaint On Contract Or Other Debt | `327,328,329,330,331,593,594,595,596,682,683,684,710` |
| Contract And Indebtedness | `461` |
| Construction Lien | `361,558` |
| Mechanic's Lien | `362,363,561` |
| Foreign Judgment | `277,278,279,280,422,423,425,641,642,643,671,672,673,674,688,689,690,693,702` |
| Notice Of Impending Judgment | `282,283` |
| Business Transactions | `454` |
| Replevin | `339,340,341,441,442,530,572,573,623,624,625,626,679,680,681` |
| Eviction | `357,358,359,360,409,685,686,687,694,695,696,697,698,699,711,712` |
| Small Claims | `640` |
| Commercial Foreclosure | `488,489,490` |

**Pagination.** 25 rows per page, fixed. The response HTML carries a hidden field `c_RequestStateHiddenField_<guid>` whose value is base64-encoded XML — the complete `CaseSearchRequest`, including `<PageNumber>`, `<PageSize>25</PageSize>`, `<PreviousRecordCount>` (the total hit count), and the echoed `<CaptchaResponse>`. To page, decode nothing: hand the blob back verbatim as `requestState` to `CaseSearchUpdate` with `operation: "NextPage"`.

**Detail addressing.** Each result row carries an inline `onclick="getCaseTabByCaseId(<int>);"`. That integer is a stable internal case ID (e.g. `14217260`). It is the join key, and it is the only compact one — but it is **not addressable by URL**.

**There is no stable, linkable URL for any case or document.** `https://core.duvalclerk.com/CoreCms.aspx?ucn=...` is accepted and ignored (`startupMode = ''`, verified 08:59Z). This is deliberate, and the order says so:

> "Online links shall be encrypted to prevent return access to a URL via 'cutting and pasting.' Link refresh times shall appropriately time out as determined by each individual clerk, but links shall refresh no less than once every 30 minutes."
> — AOSC24-65, *Standards*, "INTEGRITY OF THE COURT RECORD"

This is a direct problem for CLAUDE.md §3, which requires every fact to carry a URL pointing at the specific record. **CORE cannot satisfy that as written.** The best available citation is the uniform case number (`16-2025-CC-017137-AXXX-MA`) plus the portal URL plus the fetch timestamp, and a human has to re-run the search to verify. That is a schema decision someone needs to make deliberately, not paper over.

**Documents.** `beginImageJob(caseId, docketId, simCtrl)` → `BeginImageLoad` returns a `RequestKey`; poll `GetImageLoadStatus` until `IsDone`; then `GET /courtDocuments/<FancyFilename>?key=<RequestKey>`. Confirmed working for anonymous public access at 09:02:56Z — a three-page default final judgment resolved to `[25-CC-17137]_DEFAULT_FINAL_JUDGMENT___BOOK_21759_PAGE_1110-1112.pdf`. I did not download it. **Free — no purchase, no paywall.** The key is single-use and time-limited.

## Access barriers

**Confirmed by observation:**

- **No login required.** `PublicLogin` returns `LoginSuccess: true` and, critically, `UserAgreementAcceptanceRequired: false` with `UserAgreementToAccept: null`. The CORE user agreement binds *registered* accounts; anonymous public users are asked to accept nothing. (08:59:44Z)
- **No user-agent filtering.** Identical request with curl's default UA and no `Referer` returned the same 3,316-byte success. (09:03Z)
- **No robots.txt on the portal.** `core.duvalclerk.com/robots.txt` → HTTP 404 (08:56Z). The parent site `www.duvalclerk.com/robots.txt` → HTTP 200 containing exactly one line, `Sitemap: https://www.duvalclerk.com/site-map`, and **no `Disallow` directives at all**.
- **No JavaScript rendering needed.** The JSON service can be driven directly.
- **Adaptive, server-triggered CAPTCHA.** Every `CoreWebTabPackage` response carries a `CaptchaChallenge` field. When the server populates it, the client renders a Google reCAPTCHA (site key `6LeK8AcTAAAAAC3lXyvXKjgORKekPQKB0eaCimFC`) in a tab titled "Bot Check" and replays the search with the token substituted for the `captchaPH` placeholder. **The server decides when.** Across 3 searches and 3 case retrievals in ~2 minutes it stayed `null`. That is not evidence there is no threshold — it is evidence I did not reach it. Any real retriever will hit it, and **solving it is off-limits.**
- **Session affinity.** `ASP.NET_SessionId` + `CoreAffinity` cookies; IIS 10.0 behind ARR.
- **Two family/probate walls.** Anonymous public users cannot see Family Law or Probate cases at all. Irrelevant to Datum's scope, and a good thing.

**Claimed but not confirmed:** no per-day cap is documented anywhere on the site, in the order, or in the service. AOSC24-65 directs clerks to "[m]onitor bulk data transfers to identify and mitigate abuses of the system" — so a cap or ban very likely exists as an operational control rather than a published number. Treat the absence of a published limit as unknown risk, not as permission.

**Not attempted, by constraint:** account creation, the registered-user "Registration Agreement to View Records Online," any captcha solve, and any volume probing designed to find the throttle.

## Terms of use

There is **no terms-of-use, acceptable-use, or scraping policy page on `duvalclerk.com`.** `/terms-of-use`, `/disclaimer`, and `/privacy-policy` all redirect to `/Page-Not-Found` (checked 08:58Z), and the site map lists no legal/terms page. `core.duvalclerk.com` serves no `robots.txt`. The anonymous public session is explicitly granted with `UserAgreementAcceptanceRequired: false`.

**The operative language is not a website TOS. It is a Florida Supreme Court administrative order, incorporated by reference from the Clerk's own court-records page.** This is the passage that decides the question:

> "Only authorized automated search programs, to be used solely on the indices, shall be used with the court's electronic public access system. Automated search programs may not be used on any other component of the court's electronic public access system. The court and clerk will determine the criteria for authorization of any automated search programs. Such authorization may be revoked or modified at the discretion of the court and clerk."
> — *Standards for Access to Electronic Court Records* (Sept. 2024), section "PERFORMANCE", in Fla. Admin. Order No. AOSC24-65, https://flcourts-media.flcourts.gov/content/download/2440532/file/AOSC24-65.pdf, retrieved 2026-09-15 ~09:04Z

Immediately preceding it, on document-level search:

> "Online access to documents stored as images may be provided. Documents stored as images are 'view only.' If a requested document is maintained by the clerk in a searchable format, the document may be provided to the public in that format, but only in response to a specific request. Search capability, if available, will be limited to such requested document and must not support automated bulk searches."
> — same source, same section

And the clerk-side obligation, under "Minimum Technical Requirements":

> "Monitor bulk data transfers to identify and mitigate abuses of the system by utilizing access programs using automated methods."
> — same source, section "CLERK SECURITY"

Search fields available to us are also capped by the order, which matches exactly what CORE exposes:

> "Search parameters for web-based access to electronic records will be limited to the following:
>
> A. User Role 7 (General Public)
> 1. Case type;
> 2. Case number;
> 3. Party name;
> 4. Citation number; and
> 5. Date range."
> — same source, section "PERFORMANCE"

The Clerk's own page pointing at that order:

> "Beginning in 2014, the Florida Supreme Court has issued a series of administrative orders allowing the public to view non-confidential court records via the internet, while simultaneously protecting confidential and sensitive information."
>
> "...an individual's viewing permissions are governed by the role of the particular user, the type of case, the nature of the specific court document, and the nature of the information contained within that court document."
> — https://www.duvalclerk.com/online-option/court-records, retrieved 2026-09-15 ~08:58Z

And on the public access tier:

> "This basic level of access allows the public to view non-confidential court records in non-confidential case types, but does not allow them to request access to documents that have not already been reviewed and published to CORE for viewing. Those utilizing the basic public access level are also not permitted to view records in cases governed by the Florida Rules of Family Law or the Florida Probate Rules per the Supreme Court's order."
> — same URL, same retrieval

**My reading.** Automated access is **restricted, not prohibited, and not permitted by default.** Three things follow, and none of them are comfortable:

1. An automated search program against the CORE **index** is contemplated by the order but requires authorization from the court and the clerk. We do not have it. Running one without it is not "public records are public" — it is using the system in a way the governing order conditions on a permission we have not asked for.
2. Automated access to **anything other than the index** — case detail pages, docket retrieval, document PDFs — is not covered by that authorization even if we obtained it ("may not be used on any other component"). A retriever that opens case detail pages in bulk is outside the carve-out on its face. This is the harder half, and it is precisely where the useful fields live.
3. Authorization "may be revoked or modified at the discretion of the court and clerk" — so even a granted permission is not a durable asset to build a product on without a fallback.

There is also a plain reputational point that no lawyer is needed for: the Clerk publishes an email address (`CORE@duvalclerk.com`) and a phone number. Asking is cheap, and asking first is the difference between a partner and a nuisance.

**Flag for legal review — yes, unambiguously.** This is not a close call and it should not be softened. The right sequence is: contact the Clerk about User Role 11 (bulk purchaser) and/or automated-search authorization *before* any retriever is written, not after.

## Fields available

**Search result row** (25 per page): case number (formatted `2025-CC-017137-AXXX`), citation number, **every party with a role code** — `(P)` plaintiff, `(D)` defendant, `(G)` guardian ad litem — case type label, division, case status (`OPEN` / `CLOSED` / `RE`), next court date, and a **relevance score** (integers observed: 950, 450). Plus the internal `caseId` in the row's `onclick`.

**Case detail:**

- Uniform case number, e.g. `16-2025-CC-017137-AXXX-MA` — county 16 = Duval, year, type, sequence, branch
- Department (`County Civil`), Division (`CC-I`), Case Status, File Date (with time to the second)
- Judge name, assigned officer
- **Parties table**: name, party type, address (street/city/state/zip as a `<address>` block) — column header is `Name / DOB / DL / ID #` and `Race / Sex`
- **Attorneys**: name, Florida Bar number, firm address, which parties represented
- **Fees**: date, description, assessed, paid, balance — *court* fees only
- **Court Events**: date, time, type, location, courtroom, cancelled flag
- **Dockets**: line number, document number (`D17`), count, effective date, entered date, free-text description, page count, image availability status

**For entity resolution**, the genuinely valuable fields are the **party address** and the **raw party-name string**, which preserves the full DBA chain as filed. The real record I pulled:

> `J. WILLIAMS INDUSTRIAL GROUP, INC. DBA J. WILLIAMS INDUSTRIAL ELECTRICAL AND MECHANICAL, INC DBA J. WILLIAMS INDUSTRIAL DBA JWI DOCK AND DOOR DBA JWI FIR PROTECTION` — `16114 N MAIN STREET, JACKSONVILLE, FL 32218`

That is four DBAs and a typo (`FIR` for `FIRE`) in one field. It is exactly the messy input CLAUDE.md §6 is about, and it is also a gift: a single CORE record can seed several name variants for the same legal entity. The **address is the strongest disambiguator available** — CORE gives it for free where Sunbiz gives a registered-agent address that is often a lawyer's office.

The internal `caseId` is stable within CORE but is not a public identifier and appears nowhere else. The **UCN is the portable identifier** and should be the join key.

### Judgment amounts and dispositions — the important negative

**Judgment amounts are not exposed anywhere in the index.** Verified on a case that ended in a money judgment against a Jacksonville contractor:

- The docket says `DEFAULT FINAL JUDGMENT BOOK 21759 PAGE 1110-1112`. No dollar figure.
- The structured `Fees` table holds *court* fees (`$10.00` summons, `$400.00` filing) — never the judgment.
- The amount exists only inside the PDF, which is free to view but must be parsed from a scanned image.

What you *do* get structurally is a **claim band**, in two places: the docket line `COMPLAINT ON CONTRACT OR OTHER DEBT - $15000 - $30000` and the fee description `CLAIMS >15k <=30k NON FORECLOSURE ACT 1/1/2023`. Case-type labels encode bands too (`Mortgage/Lien Foreclosure - Up To $15,000`, `Non-Homestead Residential Foreclosure $250,000 Or More`, `Insurance Claim $501.00 - $2,500.00`). For Datum's purpose a band plus a confirmed default judgment may well be enough — "a supply house sued them for $15–30K and took a default final judgment" is a usable fact that needs no PDF.

**Dispositions are exposed, as free text in the docket, not as a structured field.** Real examples pulled today: `DEFAULT ISSUED AGAINST <party>`, `MOTION FOR DEFAULT AND DEFAULT`, `DEFAULT FINAL JUDGMENT BOOK ... PAGE ...`, `CANCEL REASON - FJ ENTERED`, `NOTICE OF VOLUNTARY DISMISSAL WITH PREJUDICE - PLTFS TO DEFT`, `CANCEL REASON - NOTICE OF DISMISSAL FILED`. Classifying these is deterministic string work against a fixtured vocabulary — plain Python per CLAUDE.md §1, not a model call.

### Confidentiality, redaction, and the consumer-data boundary

This needs flagging hard, because CORE will hand you personal data whether you asked for it or not.

**The parties table column header is literally `Name / DOB / DL / ID #` and `Race / Sex`.** For corporate parties those subfields come back blank — but for individual parties they are populated, and CORE mixes both in the same result set. I observed a stray race code (`B`) attached to a *corporate* defendant in case `16-2024-CA-005914-AXXX-MA`, so the fields are not even reliably empty for businesses.

The search criteria themselves include `DateOfBirth`, `LicenseNumber`, `OffenderNumber`, `PartyGender`, `PartyRace`, `SheriffNumber`, `StateAttorneyNumber` — visible in the decoded request state below. **Datum must never populate any of them, and any parser must drop DOB, DL, race and sex at ingest rather than storing and filtering later.** These are court records, so FCRA does not attach by merely reading them — but ingesting an individual's DOB and driver's licence number is squarely across the line CLAUDE.md §2 and PROJECT_CONTEXT §12 draw, and it is a line drawn for good reasons that have nothing to do with FCAA technicalities.

A concrete trap for a party-name search: the second hit on my Winn-Dixie search was a residential foreclosure with **twenty-six** defendants, nearly all named individuals, returned because a corporate lienholder was among them. **A business-name search routinely returns bulk personal data as collateral.** Filtering to business-relevant case types is not optional hygiene, it is the control that keeps this source inside scope.

What the system already protects:
- Cases expunged, sealed, automatically confidential under Fla. R. Gen. Prac. & Jud. Admin. 2.420(d)(1), or made confidential by court order are excluded from public access entirely.
- No anonymous remote access to Family Law, Juvenile, or Probate images, per §28.2221(5)(a), Fla. Stat.
- Documents are marked `Public access`, `VOR, Ready to view` (viewable on request, already clerk-reviewed and released), or `Unavailable`. The Clerk's description of VOR:

  > "Documents marked as 'View on Request' are available for public viewing. However, once the document has been requested, it must first be processed by a Clerk employee to ensure that the document is properly redacted. This process must be performed manually on each document requested the first time it is released to the public."
  > — https://www.duvalclerk.com/online-option/court-records, retrieved 2026-09-15 ~08:58Z

  Note the consequence: **requesting an unreleased document creates manual work for a human clerk.** Automating that request path would impose real cost on the Clerk's office and is exactly the kind of "abuse of the system" the order tells clerks to mitigate. It also requires a registered account, so it is out of reach anyway. Do not build it.

- Redaction is a clerk obligation, not ours: "Clerks must employ redaction processes through human review, the use of redaction software, or a combination of both." (AOSC24-65, "QUALITY ASSURANCE"). We should not assume it is perfect — a released PDF may still contain a bank account or SSN that slipped through, which is one more argument for not bulk-downloading images.

## Example URLs

CORE has **no per-record URLs** — see "Scrape-only access". These two are real, were fetched today, and a person can paste either into a browser and see it work:

1. **https://core.duvalclerk.com/CoreCms.aspx** — the live civil case search application. HTTP 200, 31,727 bytes, fetched 2026-09-15 08:59Z. Click "Public Access" (no credentials) and search Last Name `FERGUSON ENTERPRISES`, Court Type `CC` to reproduce the records below.
2. **https://core.duvalclerk.com/internal/CoreWebSvc.asmx** — the ASP.NET service description page, which lists all 28 operations by name. HTTP 200, 8,412 bytes, fetched 2026-09-15 08:59Z. This is the undocumented API's self-description, served to anyone.

Supporting, also fetched and verified today:
- https://www.duvalclerk.com/online-option/court-records — HTTP 200, 130,914 bytes, ~08:58Z (access tiers, VOR policy, fees)
- https://www.duvalclerk.com/robots.txt — HTTP 200, 08:56Z (one `Sitemap:` line, zero `Disallow`)
- https://flcourts-media.flcourts.gov/content/download/2440532/file/AOSC24-65.pdf — 18 pages, ~09:04Z (the governing order; note the 307 redirect from `supremecourt.flcourts.gov`)

**Real records retrieved** (addressable only by the search that finds them, not by URL):

| UCN | Internal caseId | What it is | Fetched (UTC) |
|---|---|---|---|
| `16-2025-CC-017137-AXXX-MA` | `14217260` | Ferguson Enterprises LLC v. J. Williams Industrial Group Inc. — contract/debt $15–30K, default final judgment | 09:02:24Z |
| `16-2026-CA-005557-AXXX-MA` | `14430333` | McMillan v. Winn Dixie Stores LLC — business transactions, open | 09:01:33Z |
| `16-2024-CA-005914-AXXX-MA` | `13999717` | Nelson v. Winn Dixie Stores Inc — voluntarily dismissed with prejudice | 09:02:01Z |

**Generalized request patterns** (documentation only — no code is being written here, and none should be until the authorization question is settled):

```
POST https://core.duvalclerk.com/internal/CoreWebSvc.asmx/PublicLogin
  body: {}
  -> {"d":{"Token":"00000000-0000-0000-0000-000000000000", ...}}

POST https://core.duvalclerk.com/internal/CoreWebSvc.asmx/CaseSearchBegin
  body: {"token":"<token>","returnTabId":<int>,
         "inputs":{"LastName":"<ENTITY NAME>","CaseType":"CC|CA|SC|AO",
                   "CaseTypeList":"<comma-joined numeric ids>",
                   "UseNamePhoneticMatchOption":false,
                   "UseNameBeginsWithOption":true},
         "captcha":"captchaPH"}

POST https://core.duvalclerk.com/internal/CoreWebSvc.asmx/CaseSearchUpdate
  body: {"token":..., "returnTabId":<int>, "operation":"NextPage",
         "requestState":"<base64 blob from previous response>", "captcha":"captchaPH"}

POST https://core.duvalclerk.com/internal/CoreWebSvc.asmx/GetCaseById
  body: {"token":..., "returnTabId":<int>, "caseID":<int>, "simCtrl":0}   // simCtrl must be 0, not null
```

## Raw response excerpt

**A. `CaseSearchBegin` — the JSON envelope.** Complete response with the 134KB `BodyHtml` value elided; nothing else trimmed. Fetched 2026-09-15 09:02:16Z, search `LastName=FERGUSON ENTERPRISES`, `CaseType=CC`.

```json
{"d":{"__type":"CoreWebTabPackage","TargetTabId":5,"HeaderText":"Search Results",
 "BodyHtml":"<<< 89,631 bytes of server-rendered HTML elided >>>",
 "LoginOk":true,"CaptchaChallenge":null,"RedirectUrl":null,
 "RedirectOnInternalTab":false,"RedirectOnNewTab":false,
 "RenderInternalTabBodyOnNewTabRedirect":false,"ClosePlaceholderOnUrl":null,
 "OriginTabId":0,"ECertifyCartId":null,"UpdateECertifyCart":false}}
```

`"CaptchaChallenge":null` is the field to watch: when the server populates it with a reCAPTCHA site key, the search did not run and a bot check is being demanded.

**B. Result-row markup inside `BodyHtml`.** One `<tbody>` from the Winn-Dixie search, verbatim, whitespace as returned. Trimmed only at the `<tbody>` boundaries. Fetched 2026-09-15 09:00:34Z.

```html
            <tbody onclick='getCaseTabByCaseId(14430333);'>
                <tr>
                    <td>
                        <div class="searchResultItem_CaseNumber">2026-CA-005557-AXXX</div>
                                <div class="searchResultItem_Citations">
                                </div>
                    </td>
                    <td>
                                <div class="searchResultItem_Parties">
                                <div class="searchResultItem_Party" style="padding: 3px; margin-bottom: 5px;">
                                    <div class='searchResultItem_PartyName'>
                                        MCMILLAN, JAMES 
                                        (P)
                                    </div>
                                </div>        
                                <div class="searchResultItem_Party" style="padding: 3px; margin-bottom: 5px;">
                                    <div class='searchResultItem_PartyName'>
                                        WINN DIXIE STORES, LLC
```

The parse targets are the `onclick` case ID and the `searchResultItem_*` class names — `_CaseNumber`, `_PartyName`, `_CaseType`, `_Division`, `_CaseStatus`, `_NextCourtDate`, `_Relevance`. Party role is a bare `(P)` / `(D)` / `(G)` suffix in the name div, not a separate element.

**C. Case-detail parties and fees table.** Verbatim from `GetCaseById(14217260)`, fetched 2026-09-15 09:02:24Z; whitespace collapsed by my extraction, tags and text otherwise untouched. This is the record that shows the DBA chain, the address, the personal-identifier column headers, and the absence of any judgment amount.

```html
<div id="c_PartiesPanel"> <div class="caseDisplayTable"> <h2>Parties</h2> <table>
<thead> <tr> <td> Name / DOB / DL / ID # </td> <td> Party Type<br />
<span style="font-size: 85%;">Race / Sex</span> </td> <td> Address </td> </tr> </thead>
<tbody> <tr> <td> <span style="text-decoration: underline;"> FERGUSON ENTERPRISES LLC </span> </td>
<td> PLAINTIFF <br /> / </td> <td> <address> 21490 WEST DIXIE HWY<br />AVENTURA, FL33180 </address> </td> </tr> </tbody>
<tbody> <tr> <td> <span style="text-decoration: underline;"> J. WILLIAMS INDUSTRIAL GROUP, INC. DBA
J. WILLIAMS INDUSTRIAL ELECTRICAL AND MECHANICAL, INC DBA J. WILLIAMS INDUSTRIAL DBA JWI DOCK AND DOOR
DBA JWI FIR PROTECTION </span> </td> <td> DEFENDANT <br /> / </td>
<td> <address> 16114 N MAIN STREET<br />JACKSONVILLE, FL32218 </address> </td> </tr> </tbody>
</table> </div> </div>
...
<div id="c_FeesPanel"> <div class="caseDisplayTable"> <h2>Fees</h2> <table> <thead> <tr>
<td> Date </td> <td> Description </td> <td> Assessed </td> <td> Paid </td> <td> Balance </td> </tr> </thead>
<tbody> <tr> <td> 09/18/2025 </td> <td> SUMMONS($10/ea) 07/01/2023 (County) </td>
<td> $10.00 </td> <td> $10.00 </td> <td> $0.00 </td> </tr> </tbody>
<tbody> <tr> <td> 09/18/2025 </td> <td> CLAIMS &gt;15k &lt;=30k NON FORECLOSURE ACT 1/1/2023 </td>
<td> $400.00 </td> <td> $400.00 </td> <td> $0.00 </td> </tr> </tbody> </table> </div> </div>
```

**D. Docket line for the judgment itself**, same response, showing that the amount is absent and the document is released:

```html
<td class="docketDescription"> DEFAULT FINAL JUDGMENT   BOOK 21759 PAGE 1110-1112 </td>
<td> <span>3</span> </td>
<td> <div class="docketImageContainer"> <a id="c_DocketClerkGridView_c_DocketClerkGridView_ImageContainer_16"
onclick="javascript:beginImageJob(14217260, 230992630, 0);"> <div>
<span style="color:DarkGreen;font-weight:bold;">Available</span><br />
<img src="https://core.duvalclerk.com/images/imageStatus/Available.png" alt="Image is available" /><br />
<span title="This image is viewable on request, and has previously been requested, reviewed by a clerk,
and released" style="color:Silver;">VOR, Ready to view</span> </div> </a> </div> </td>
```

`BOOK 21759 PAGE 1110-1112` is the Official Records book/page — the crosswalk to the recorded-judgment system covered by the parallel recon.

**E. Decoded pagination state.** The base64 value of `c_RequestStateHiddenField_<guid>`, decoded (3,060 bytes base64 → XML). Trimmed: the `<Criteria>` element's nil fields are shown in full because they are the field inventory, but I cut nothing from within it. Fetched 2026-09-15 09:00:34Z.

```xml
<CaseSearchRequest xmlns="http://schemas.datacontract.org/2004/07/DuvalClerk.Core.Contracts"
 xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
 <CaptchaResponse>captchaPH</CaptchaResponse>
 <RequestSimulatedAccessLevelID>0</RequestSimulatedAccessLevelID>
 <User i:nil="true"/><UserToken>00000000-0000-0000-0000-000000000000</UserToken>
 <Criteria>
  <ActiveWarrant i:nil="true"/><AgencyID i:nil="true"/><ArrestDate i:nil="true"/>
  <CaseNumber><Branch>MA</Branch><County>0</County><Party/><Sequence>0</Sequence><Type>CA</Type><Year>0</Year></CaseNumber>
  <DateOfBirth>0001-01-01T00:00:00</DateOfBirth><Division i:nil="true"/>
  <FirstName i:nil="true"/><LastName>WINN DIXIE STORES</LastName><MiddleName i:nil="true"/>
  <LicenseNumber i:nil="true"/><OffenderNumber i:nil="true"/><OfficerBadgeNumber i:nil="true"/>
  <PartyGender i:nil="true"/><PartyRace i:nil="true"/><PartyTypeID i:nil="true"/>
  <SheriffNumber i:nil="true"/><StateAttorneyNumber i:nil="true"/>
  <WarrantClosed i:nil="true"/><WarrantNumber i:nil="true"/><ePortalFilingNumber i:nil="true"/>
 </Criteria>
 <Options>
  <NameSearch_UseCombinedNameFieldsOption>false</NameSearch_UseCombinedNameFieldsOption>
  <NameSearch_UsePhoneticOption>false</NameSearch_UsePhoneticOption>
  <NameSearch_UseStartsWithOption>true</NameSearch_UseStartsWithOption>
  <SortByDirection>ASC</SortByDirection><SortByFieldName>CaseNumber</SortByFieldName>
 </Options>
 <PageNumber>1</PageNumber><PageSize>25</PageSize>
 <PreviousRecordCount>183</PreviousRecordCount>
 <RequestTotalResultCount>true</RequestTotalResultCount>
</CaseSearchRequest>
```

`<PreviousRecordCount>183</PreviousRecordCount>` is the total hit count — 183 Circuit Civil cases naming a Winn-Dixie entity, across 8 pages. `<PartyGender>`, `<PartyRace>`, `<DateOfBirth>` and `<LicenseNumber>` are the criteria Datum must never populate.

## Open questions

1. **Will the Clerk authorize an automated search program, and on what terms?** This is the only question that matters. `CORE@duvalclerk.com` / (904) 255-2000. Ask specifically about (a) authorization under the AOSC24-65 "PERFORMANCE" clause for index searches, and (b) whether case-detail retrieval can be covered or is categorically outside it.
2. **What does User Role 11 (commercial bulk purchaser) actually cost and deliver?** Format, cadence, price, and whether it includes the civil index or only recorded instruments. Requires a written notarized agreement, so it needs a human with signing authority — not an agent.
3. **What is the real rate threshold before `CaptchaChallenge` fires?** I deliberately did not probe for it; finding it by hammering the server would be the exact behavior the order tells clerks to mitigate. If authorization is granted, ask for the number rather than discovering it.
4. **Is there a pre-electronic cutoff?** Oldest case I happened to touch was 2021. Whether CORE's civil index reaches back 10 or 20 years, and whether older cases are index-only with no images, is unknown. Matters for judgment staleness.
5. **How is the provenance requirement (CLAUDE.md §3) satisfied without stable URLs?** The order deliberately prevents copy-pasteable record links. Either the fact schema accepts UCN-plus-portal-URL as the citation, or CORE facts cannot be stored under the current rule. Decide this before writing the fact type, not after.
6. **Do judgment amounts justify PDF parsing at all?** The claim band plus disposition may be sufficient signal. Worth testing against the ~50-business evaluation set before anyone builds OCR — and bulk image retrieval is the part most clearly outside the automated-search carve-out, so the answer being "no" would be convenient *and* correct.
7. **Small Claims (`SC`) coverage.** I searched `CA` and `CC` only. `SC` is where sub-$8K contractor disputes land and is probably high-frequency for Mike's segment. Needs its own pass.
8. **Duval is one county.** Nothing here generalizes: every Florida clerk runs different software. This report covers Duval CORE and nothing else.

---

*Scope note: this report covers the Duval County court **case index** only. The Clerk's **Official Records** system (`or.duvalclerk.com`) — recorded judgments, judgment liens, mechanic's and construction liens, UCC filings — is a separate system with separate access rules and is covered by a parallel recon. The two connect through the book/page reference in CORE docket text; whoever writes the retrievers should treat that reference as the join key between them.*
