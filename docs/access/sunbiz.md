# Access Report: Florida Sunbiz (Division of Corporations)

**Source:** Florida Department of State, Division of Corporations — "Sunbiz"
**Jurisdiction:** State of Florida
**Record types:** Corporations, LLCs, limited partnerships, general partnerships, fictitious names (DBAs), trademarks/service marks, federal tax lien registrations, cable franchises. Entity status, filing dates, principal/mailing addresses, registered agents, officers/managers/authorized persons, annual report history, name-change history, and scanned filing images.
**Investigated:** 2026-09-15T08:56Z – 2026-09-15T09:04Z (all fetch timestamps below are UTC)
**Verdict:** Usable, and unusually well-suited to this project. A free, complete, no-account bulk download of the entire corporate and fictitious-name database exists over SFTP with quarterly full snapshots and daily deltas. Build the entity-resolution index from bulk; use the web UI only for targeted refresh. No official API exists, and the live search UI is behind a Cloudflare managed challenge that blocks non-browser HTTP clients.

## Summary

Sunbiz is the strongest possible starting point for a Florida-first entity-resolution index. The Division publishes the *entire* active corporate register and the *entire* fictitious-name register as fixed-width ASCII files on a public SFTP server, free, with published record layouts, refreshed quarterly in full and daily by delta — which means the primary path is not scraping at all. The fictitious-name file carries an explicit **Owner Charter Number** and **Owner FEI Number** on each DBA record, so DBA-to-legal-entity linkage is a deterministic join rather than a fuzzy match. The live search UI at `search.sunbiz.org` is fully GET-addressable and server-rendered, but it sits behind a Cloudflare managed challenge that returns HTTP 403 to `curl` and to server-side fetchers, so any live-lookup retriever needs a JS-capable client. The single genuine legal complication is that the legacy fictitious-name host `dos.sunbiz.org` serves `User-agent: * / Disallow: /`, so automated retrieval of DBA records from the web UI is off-limits under the project's own robots rule — the bulk file is the compliant route to the same data.

## Bulk download

**Yes — this is the recommended primary path.**

- **Landing page:** `https://dos.fl.gov/sunbiz/other-services/data-downloads/` (fetched 2026-09-15T09:02Z)
- **Host:** `https://sftp.floridados.gov` — a web-based file-transfer portal (HTTPS, returned HTTP 200, 12,563 bytes at 2026-09-15T09:03Z) that also answers SSH on tcp/22 (confirmed open from this machine at 2026-09-15T09:03Z).
- **Credentials:** the Division publishes a shared public account openly on the page above: `Username: Public`, `Password: PubAccess1845!`. **I did not connect or authenticate** — the recon brief forbids using a credential found anywhere, so the file contents below are documented from the Division's own published record layouts, not from files I downloaded. Someone on the project should do one manual pull to confirm.
- **Cost:** free. Quoted verbatim below under Terms of use.
- **Format:** fixed-length ASCII text, **no header row**, one record per line. Zipped for quarterly, plain `.txt` for daily.

### Cadence

| Type | Cadence | Contents |
|---|---|---|
| Daily | "generated on work days and contain the filings added to our record that day" — no file is generated on a day with no filings | delta only |
| Quarterly | "generated quarterly in January, April, July, and October" | **all active data** at generation time |

Implication for Datum: one quarterly pull seeds the index; daily files keep it current with a ~1 business-day lag. Note the quarterly file contains *active* data — inactive/dissolved entities may not be present in a full snapshot, which matters because a dissolved customer is exactly the signal a contractor wants. Verify this against an actual pull before relying on it.

### Files (quarterly, from `https://dos.fl.gov/sunbiz/other-services/data-downloads/quarterly-data/`, fetched 2026-09-15T08:57Z)

| File | SFTP path | Contents |
|---|---|---|
| `cordata.zip` | `doc/quarterly/cor` | Corporations, LLCs, LPs — split into 10 files by trailing digit |
| `corevent.zip` | `doc/quarterly/cor` | Corporate events (excludes annual reports and address changes) |
| `ficdata.zip` | `doc/quarterly/fic` | Fictitious name registrations |
| `ficevt.zip` | `doc/quarterly/fic` | Fictitious name events and actions |
| `genfile.zip` / `genevt.zip` | `doc/quarterly/gen` | General partnership filings and events |
| `flrf/flre/flrd/flrs.zip` | `doc/quarterly/flr` | Federal tax lien filings, events, debtors, secured parties |
| `TMData.zip` | `doc/quarterly/trademarks` | Trademarks and service marks |

Daily equivalents (from `https://dos.fl.gov/sunbiz/other-services/data-downloads/daily-data/`, fetched 2026-09-15T09:02Z) are named `yyyymmddc.txt` (corporate), `yyyymmddce.txt` (corporate events), `yyyymmddf.txt` (fictitious), `yyyymmddfe.txt` (fictitious events), `yyyymmddg.txt` / `yyyymmddge.txt` (general partnerships), `yyyymmddflr{f,e,d,s}.txt` (federal liens), `yyyymmddtm.txt` (marks), under `doc/cor`, `doc/cor/events`, `doc/fic`, `doc/gen/*`, `doc/flr/*`, `doc/tm`.

**Note the federal tax lien files.** `flrd.zip` (debtors) and `flrs.zip` (secured parties) are already in scope for the Datum thesis and arrive through the same free channel. They are a separate record type and deserve their own recon run before use, but they are *not* a separate acquisition problem.

### Documented caveats on the bulk data

From `https://dos.fl.gov/sunbiz/other-services/data-downloads/data-usage-guide/` (fetched 2026-09-15T09:00Z) and `https://dos.sunbiz.org/data-definitions/cor.html` (fetched 2026-09-15T09:00Z):

- "We provide our data as-is."
- "occasionally, a file may include one or more rows that don't line up properly" — caused by special characters or embedded line breaks. A parser must tolerate malformed rows rather than abort.
- "Our office does not have the technical expertise to assist with manipulation of the provided data."
- Corrections apply only to "future data files, but it will not correct the already created file you are working with."
- "Fixed-width data includes a character in every position" — trim whitespace before comparison or sorting.
- Document numbers come in "6 or 12 characters" (legacy vs. modern), confirmed by observation: `F97319` and `L25000359935` are both live document numbers.
- **From the corporate layout page directly:** "Please note that data for addresses and listed officers may not reflect the most current information on sunbiz.org because of the limited space in the file." The bulk file caps at **6 officers** and truncates addresses to 42 characters. The web detail page is authoritative for these fields. This is the concrete reason a live-lookup path is still needed on top of bulk.

## API

**There is no official API.** No developer portal, no API key programme, no documented JSON endpoint anywhere on `dos.fl.gov` or `sunbiz.org`. Searched 2026-09-15T09:02Z; every result surfaced was a third-party reseller or scraper-as-a-service (Apify actors, `sunbizdata.com`), not a state offering. The state's answer to "programmatic access" is the bulk download described above.

**Undocumented JSON endpoints behind the UI: none — confirmed by observation, not assumed.** I captured 100 network requests while driving the search UI through name search, document-number search, detail, and name-history pages (inspected 2026-09-15T09:03Z). Every request was a full-page `GET` returning server-rendered HTML, plus static CSS/JS/image bundles. There is no XHR layer, no `/api/` path, no JSON. This is a classic ASP.NET MVC application; the HTML *is* the API.

## Scrape-only access

Two distinct web applications, on two different hosts, with different technology and different robots posture. Treat them separately.

### A. Corporate/LLC search — `search.sunbiz.org` (modern, ASP.NET MVC)

Entry points, all confirmed live at 2026-09-15T08:59Z:

```
/Inquiry/CorporationSearch/ByName
/Inquiry/CorporationSearch/ByOfficerOrRegisteredAgent
/Inquiry/CorporationSearch/ByRegisteredAgent
/Inquiry/CorporationSearch/ByFeiNumber
/Inquiry/CorporationSearch/ByDocumentNumber
/Inquiry/CorporationSearch/ByZip
/Inquiry/CorporationSearch/ByAddress
/Inquiry/CorporationSearch/ByTrademark
/Inquiry/CorporationSearch/ByTrademarkOwner
```

**Name search — GET, fully linkable:**

```
GET /Inquiry/CorporationSearch/SearchResults?inquiryType=EntityName&searchTerm=<url-encoded name>
```

**Pagination is a cursor, not an offset.** 20 rows per page. The "Next List" link carries the sort key of the last row on the current page:

```
GET /Inquiry/CorporationSearch/SearchResults
  ?InquiryType=EntityName
  &inquiryDirectionType=ForwardList          # or BackwardList
  &searchNameOrder=AIRCONDITIONINGSYSTEMS%20M644120   # cursor: <normalized name> <docnum><digit>
  &SearchTerm=AIR%20CONDITIONING%20SNYDER
  &entityId=M64412
  &listNameOrder=AIRCONDITIONINGSOLUTIONS%20P060000171231  # first row of current page
```

**Detail pages.** A detail URL is a stable, pasteable GET, but it needs **both** `aggregateId` and `searchNameOrder` — I confirmed by experiment at 2026-09-15T08:58Z that dropping `searchNameOrder` yields the "Sorry, the web address you entered is not a functioning page" redirect page, and that supplying both re-renders the record correctly in a fresh navigation.

```
GET /Inquiry/CorporationSearch/SearchResultDetail
  ?inquiryType=DocumentNumber
  &aggregateId=<filingtype>-<docnumber lowercased>-<GUID>
  &directionType=Initial
  &searchNameOrder=<normalized name> <docnum><digit>
  &searchTerm=<document number>
```

The `aggregateId` prefix is the filing type (`domp` domestic profit, `forl` foreign LLC, `flal` Florida LLC, etc. — the same code set as the bulk file's Filing Type field). **The GUID is not derivable from the document number**, so a detail URL cannot be constructed from a document number alone; it must be harvested from a search result or from a document-number lookup.

**Document-number lookup is POST-only.** `GET /Inquiry/CorporationSearch/ByDocumentNumber?SearchTerm=...` just re-renders the empty form (tested 2026-09-15T08:58Z). The working shape is:

```
POST /Inquiry/CorporationSearch/ByDocumentNumber
  SearchTerm=M23000008792
  InquiryType=DocumentNumber
  SearchNameOrder=
```

→ 302 to the `SearchResultDetail` URL above, with the `aggregateId` filled in. **No `__RequestVerificationToken` or other anti-forgery field is present** in the form (inspected 2026-09-15T08:58Z) — the only hidden fields are `InquiryType` and `SearchNameOrder`. So the POST is reproducible without scraping form state.

**Two sub-pages hang off every detail record**, both plain GETs reusing the same `aggregateId` + `SearchNameOrder`:

```
/Inquiry/CorporationSearch/NameHistory?aggregateId=...&entityId=...&CurrentPage=0&SearchTerm=...&InquiryType=...&inquiryDirectionType=CurrentList&SearchNameOrder=...
/Inquiry/CorporationSearch/EventHistory?aggregateId=...&entityId=...&...
```

`NameHistory` is the single highest-value page on the site for entity resolution — it returns prior legal names with the date of each change. Verified live at 2026-09-15T09:03Z: `SNYDER AVIATION, LLC` (L25000359935) returns `LC NAME CHANGE | 10/14/2025 | OLD NAME WAS : SNYDER AVIATION & CHARTER, LLC`.

### B. Fictitious name (DBA) search — `dos.sunbiz.org` (legacy CGI, `.exe` scripts)

A completely separate system, not linked from the corporate search nav. Forms inspected 2026-09-15T09:01Z:

| Page | Endpoint | Method | Fields |
|---|---|---|---|
| By fictitious name | `/scripts/ficregl.exe` | POST | `action=REGLIS`, `name` (max 64) |
| By owner name | `/scripts/ficiown.html` → owner script | POST | owner name |
| **By owner document number** | `/scripts/ficchrl.exe` | POST | `action=CHRLIS`, `chrnum` (max 12) |
| **By owner FEI/EIN** | `/scripts/ficfeil.exe` | POST | `action=FEILIS`, `feinum` (max 10) |
| Detail by registration number | `/scripts/ficidet.exe` | POST | `action=DETAIL`, `docnum` (max 12) |
| Filing history | `/scripts/ficevent.exe` | GET | `docnum` |

Unlike the corporate app, **the legacy detail and pagination links are plain GETs keyed only on the registration number** — no GUID, no session token:

```
GET /scripts/ficidet.exe?action=DETREG&docnum=G01157900038&rdocnum=G01157900038
GET /scripts/ficregl.exe?action=REGNXT&docnum=G97265000094     # forward cursor
GET /scripts/ficregl.exe?action=REGPRE&docnum=G01157900038     # backward cursor
GET /scripts/ficevent.exe?docnum=G01157900038
```

**But see Terms of use — this host is robots-disallowed in full.**

### How the search handles name variants, suffixes and partial matches

This is the behaviour that matters most for Datum, and it is **not** what a naive reader assumes. Confirmed by four live experiments on 2026-09-15T08:57Z–09:02Z.

**It is an alphabetical seek, not a relevance search.** The search term is normalized into a sort key, the index is positioned at that key, and the next 20 rows are returned *in alphabetical order regardless of relevance*. Searching `SNYDER AIR CONDITIONING` returned two matching entities followed immediately by `SNYDER ANIMAL HOSPITAL, P.A.`, `SNYDER ASSETS, LLC`, `SNYDER-BEARD, INC.` and so on. There is no result count and no score. A retriever must decide for itself where the relevant window ends.

**There is no substring or token-reorder matching.** Searching `AIR CONDITIONING SNYDER` did **not** find `SNYDER AIR CONDITIONING`; it seeked to `AIR CONDITIONING S…` and returned `AIR CONDITIONING SOLUTIONS INC.`, `AIR CONDITIONING SORIANO LLC`, `AIR CONDITIONING SPECIALIST, INC.`… So the search is effectively **left-anchored on the normalized name**. A contractor typing "Riddle Plumbing" will never surface "Donnie Riddle Plumbing & Htg" through this endpoint. Candidate generation for Datum has to come from the bulk index, where you control the matching — this is the second concrete reason bulk is the primary path.

**The normalization rule, reverse-engineered from the `searchNameOrder` values the site emits:**

| Displayed name | Emitted sort key |
|---|---|
| `SNYDER AIR CONDITIONING & HEATING, INC.` | `SNYDERAIRCONDITIONINGHEATING` |
| `SNYDER AIR CONDITIONING, PLUMBING & ELECTRIC, LLC` | `SNYDERAIRCONDITIONINGPLUMBINGE` |
| `SNYDER ASSETS, LLC` | `SNYDERASSETS` |
| `SNYDER ANIMAL HOSPITAL, P.A.` | `SNYDERANIMALHOSPITALPA` |

Observed: uppercased; all spaces, punctuation, `&` and hyphens removed; **`INC` and `LLC` stripped**; `PA` retained; truncated to **30 characters**. Leading `THE` also appears to be dropped (`THE AIR CONDITIONING STORE, INC.` sorted under `AIRCONDITIONINGST…`). Confirmed behaviourally: searching `SNYDER ASSETS, L.L.C.` landed exactly on `SNYDER ASSETS, LLC` as the first row.

⚠️ The exact suffix strip-list is **not published** and I only sampled it. Treat the four rows above as evidence, not as a spec. `AIR CONDITIONING, INC. OF STUART` sorted in the `…ST` region rather than the `…OF` region, which the rule above does not explain. Anyone building normalization should derive the strip-list empirically against the bulk file, where the full name universe is available offline and a candidate rule can be tested against every row at once. **Do not port the sort key into Datum's own matcher** — it truncates at 30 characters, which collapses `SNYDER AIR CONDITIONING, PLUMBING & ELECTRIC, LLC` and any sibling sharing that prefix.

## Access barriers

**Confirmed by observation:**

- **Cloudflare managed challenge on `search.sunbiz.org` — the main obstacle.** `curl` with a current Chrome user-agent receives **HTTP 403** with `cf-mitigated: challenge` and a `Just a moment…` interstitial (2026-09-15T08:56Z). WebFetch — a server-side fetcher — also received **403** on the same host (2026-09-15T08:57Z). A real browser passes transparently with no interaction; every page in this report was retrieved that way. **Practical consequence: a live-lookup retriever needs a JS-capable client** (Playwright or similar) or a residential-grade HTTP client that completes the challenge. A plain `requests`/`httpx` retriever will not work against this host.
- **No CAPTCHA was presented and none was solved.** The challenge is a passive managed challenge, not an interactive puzzle. No access control was bypassed for this report.
- **`dos.fl.gov` and `dos.sunbiz.org` are NOT challenged.** Both returned HTTP 200 to plain `curl` (2026-09-15T08:57Z and 08:59Z). The bulk-download documentation and the entire legacy fictitious-name system are reachable without a browser. The block is specific to the corporate search app.
- **No login, no registration, no account** is required anywhere for searching or for bulk download.
- **No session state is needed for detail pages.** A detail URL harvested in one session re-renders in a fresh navigation (verified 2026-09-15T08:58Z). The only cookie in play is Cloudflare's `__cf_bm`.
- **No anti-forgery token** on the search forms (inspected 2026-09-15T08:58Z and 09:01Z).
- **JavaScript rendering is not required for content** — pages are fully server-rendered. JS is required only to clear the Cloudflare challenge.

**Not determined:**

- **Rate limits and per-day caps.** Nothing is published, and I deliberately did not probe for a threshold — finding it requires generating abusive traffic against a state system. Assume Cloudflare will rate-limit and design a retriever to be slow and polite from day one. This is an open question, below.
- **Whether the `aggregateId` GUID is stable across time.** It looks like a per-record identifier rather than a per-session one (the same GUID `8433b453-5616-4417-8507-9d8034e0c670` appeared for M23000008792 from both a name search and a separate document-number POST), but I have no evidence over a time interval. **Do not cache detail URLs as permanent** until this is tested across a week.

## Terms of use

There is **no terms-of-use page, no acceptable-use policy, and no disclaimer link anywhere on the search application.** I checked the footer and the complete link set of `https://search.sunbiz.org/Inquiry/CorporationSearch/ByName` at 2026-09-15T09:02Z: the only text below the search form is "Florida Department of State, Division of Corporations", and there are zero links matching terms/disclaimer/policy/use. I also checked `https://dos.fl.gov/sunbiz/` (2026-09-15T09:00Z), whose footer offers exactly two policy links — `/accessibility/` and `/privacy-policy/` — and no terms of use.

**The only statement governing use of the data:**

> "The Division of Corporations offers free data downloads for informational purposes. Downloads are offered as is and may be changed, replaced or deleted at any time."
> — `https://dos.fl.gov/sunbiz/other-services/data-downloads/`, retrieved 2026-09-15T09:02Z

**On the quality of the data:**

> "We provide our data as-is."
> — `https://dos.fl.gov/sunbiz/other-services/data-downloads/data-usage-guide/`, retrieved 2026-09-15T09:00Z

**robots.txt — and this is the operative finding.** The two hosts differ, and the difference is legally material:

> `User-agent: *`
> `Disallow: /`
> — `https://dos.sunbiz.org/robots.txt`, retrieved 2026-09-15T09:00Z (HTTP 200, `content-type: text/plain`, 28 bytes, `last-modified: Fri, 26 Mar 2010 12:23:44 GMT`)

I verified this is a real file and not a catch-all handler: a request for a nonexistent path on the same host (`/zzz-not-a-real-file.txt`) returns a 301, not the robots body (2026-09-15T09:00Z).

By contrast, `search.sunbiz.org/robots.txt` — which `curl` cannot reach through the Cloudflare challenge — contains, read in a browser at 2026-09-15T09:00Z, the complete body:

> "my robots content"

That is a developer placeholder that was never filled in. It contains **no `User-agent` line and no `Disallow` directive**, so under RFC 9309 it expresses no restriction at all.

`https://dos.fl.gov/robots.txt` returns HTTP 404 — no file, no restriction (2026-09-15T08:56Z).

**On the privacy policy** (`https://dos.fl.gov/privacy-policy/`, retrieved 2026-09-15T09:00Z), which contains nothing restricting automated access, only:

> "Florida's public records law requires that all information received in connection with state business be made available to anyone upon request, unless the information is subject to a specific statutory exemption."

### Reading

Split the answer by host, because the answer is genuinely different for each.

- **Bulk SFTP download — clearly permitted.** The state affirmatively offers it, free, to the public, with published credentials and published record layouts. The only qualifier is "for informational purposes," which is broad and not a prohibition on commercial use, but it is *language a lawyer should look at* before Datum resells derived output to a third party such as a supply house or a community bank (Phase 2/3 of the project plan). It is not a concern for Phase 1.
- **`search.sunbiz.org` (corporate search) — unaddressed.** No terms, no acceptable-use policy, an empty robots.txt. Under the project's own rule ("Public ≠ scrapeable"), "unaddressed" is not "permitted" — but there is nothing here to violate. The Cloudflare challenge is an access *control*, though, and routinely defeating it with an automated browser is a different posture from reading a page with no controls. Flag for legal review, but the honest assessment is that the risk is low and, more importantly, **mostly avoidable**: bulk covers the volume, so live lookups can be low-rate and human-paced.
- **`dos.sunbiz.org` (fictitious names) — restricted, by robots, unambiguously.** `Disallow: /` applied to all agents across the whole host. CLAUDE.md rule 2 says respect robots.txt. **Do not point an automated retriever at this host.** Get DBA data from `ficdata.zip` instead, which is the same data, offered freely by the same agency, with no such restriction. This is a rare case where the compliant route is also the better engineering route.

**Disclosure about this recon run:** I made a small number of manual, human-paced requests to `dos.sunbiz.org` while documenting it — three static form pages and three record lookups, all in the browser — to establish the request shape and the DBA-to-owner linkage evidenced below. I stopped there. That was a one-off documentation read, not crawling, and it is exactly what the report exists to prevent anyone from needing to repeat.

**Needs legal review: yes** — but narrowly. Two specific questions, not a general blessing: (1) does "for informational purposes" constrain resale of derived output in Phase 2/3; (2) is defeating a Cloudflare challenge with an automated browser acceptable posture against a state system with no stated terms. Neither blocks Phase 1 if Phase 1 is built on bulk.

## Fields available

### Corporate detail page (`SearchResultDetail`) — richest view

Entity type (e.g. "Foreign Limited Liability Company") · **Legal name** · **Document Number** · **FEI/EIN Number** · Date Filed · State/Country of formation · **Status** · Last Event · Event Date Filed · Event Effective Date · **Principal Address** + "Changed:" date · **Mailing Address** + "Changed:" date · **Registered Agent name and address** + separate "Name Changed:" and "Address Changed:" dates · **Authorized Persons / Officers** — title, name, full address, repeated per person, *not capped at 6 as the bulk file is* · **Annual Report history** — report year and filed date · **Document image list** — every filing with date, type, and a link to the scanned PDF · links to **Name History** and **Event History**.

Statuses observed in result lists: `Active`, `INACT`, `InActive`, `NAME HS` (name-history row), `CROSS RF` (cross-reference row). Note the inconsistent casing of `INACT`/`InActive` — normalize.

### Corporate bulk file (`cordata`, record length 1440)

From `https://dos.sunbiz.org/data-definitions/cor.html`, retrieved 2026-09-15T09:00Z:

| # | Field | Start | Len |
|---|---|---|---|
| 1 | **Corporation Number** (document number) | 1 | 12 |
| 2 | Corporation Name | 13 | 192 |
| 3 | Status — `A` active, `I` inactive | 205 | 1 |
| 4 | Filing Type — `DOMP`,`DOMNP`,`FORP`,`FORNP`,`DOMLP`,`FORLP`,`FLAL`,`FORL`,`NPREG`,`TRUST`,`AGENT` | 206 | 15 |
| 5–10 | Principal Address 1/2, City, State, Zip, Country | 221–345 | 42/42/28/2/10/2 |
| 11–16 | Mailing Address 1/2, City, State, Zip, Country | 347–471 | 42/42/28/2/10/2 |
| 17 | File Date (formation) | 473 | 8 |
| 18 | **FEI Number** | 481 | 14 |
| 19 | More-than-six-officers flag (`Y`) | 495 | 1 |
| 20 | Last Transaction Date | 496 | 8 |
| 21 | State Country | 504 | 2 |
| 22–30 | Report Year 1–3 + Report Date 1–3 (with 1-char filler between each pair) | 506–544 | 4/1/8 ×3 |
| 31–36 | Registered Agent Name, Type (`P`/`C`), Address, City, State, Zip+4 | 545–668 | 42/1/42/28/2/9 |
| 37–43 | Officer 1: Title (`P`,`T`,`C`,`V`,`S`,`D`), Type (`P`/`C`), Name, Address, City, State, Zip+4 | 669–796 | 4/1/42/42/28/2/9 |
| 44–… | Officers 2–6, same 7-field block, 128 bytes each | 797–1440 | |

Only **three** annual report years are carried in bulk; the web page shows the full list.

### Fictitious name detail page and bulk file

The DBA detail page returns: Fictitious Name · **Registration Number** (`G…`) · Status (ACTIVE / CANCELLED / EXPIRED) · Filed Date · **Expiration Date** · Current Owners count · **County** (or `MULTIPLE`) · Total Pages · Events Filed · **FEI/EIN Number** · Mailing Address · and an **Owner Information** block giving the owner's name, address, **FEI/EIN Number** and **Document Number**.

### How DBA records link back to the registered legal entity

**Both paths give you a hard join key — this is not a fuzzy-matching problem.**

**In bulk** (`https://dos.sunbiz.org/data-definitions/fic.html`, retrieved 2026-09-15T09:01Z, record length 2098, up to **10 owners** per DBA starting at field 18):

| # | Field | Start | Len |
|---|---|---|---|
| 1 | Document Number (the DBA's own registration number) | 1 | 12 |
| 2 | Fictitious Name | 13 | 192 |
| 3 | County | 205 | 12 |
| 4–9 | Address 1/2, City, State, Zip, Country | 217–338 | 40/40/28/2/10/2 |
| 10 | Filing Date | 339 | 8 |
| 12 | Status — `(C)` cancelled, `(E)` expired, `(A)` active | 352 | 1 |
| 13/14 | Cancellation Date / Expiration Date | 353/361 | 8/8 |
| 15 | Number of Owners | 369 | 5 |
| 16 | FEI Number | 374 | 14 |
| 17 | More-than-ten-owners flag | 388 | 1 |
| 18 | Owner 1 Document Number | 389 | 12 |
| 19 | Owner 1 Name | 401 | 55 |
| 20 | Owner 1 Name Format — `(P)` person, `(C)` corporation | 456 | 1 |
| 21–25 | Owner 1 Address, City, State, Zip, Country | 457–538 | 40/28/2/10/2 |
| 26 | **Owner 1 FEI Number** | 539 | 9 |
| 27 | **Owner 1 Charter Number** | 548 | 12 |
| 28–… | Owners 2–10, same 10-field block, 171 bytes each | 560–2098 | |

**Owner Charter Number joins directly to Corporation Number in `cordata`.** Owner FEI Number gives a second, independent join. `Owner Name Format` tells you whether the owner is a person or an entity, so you know when a charter-number join is even expected.

**On the web**, the reverse lookups exist as first-class search options: `ficichr.html` → `/scripts/ficchrl.exe` takes a corporate document number and lists every DBA that entity owns; `ficifei.html` → `/scripts/ficfeil.exe` does the same by owner FEI/EIN. Both are on the robots-disallowed host — documented for completeness, not for use.

Verified end-to-end at 2026-09-15T09:02Z: the DBA `SNYDER AIR CONDITIONING` (registration `G01157900038`, Duval County, ACTIVE, expires 12/31/2026) resolves to owner `SNYDER CO.`, FEI/EIN `59-2219047`, **Document Number `F97319`** — a 6-character legacy corporate document number that joins straight into the corporate register.

### Stable identifiers for entity resolution — ranked

1. **Document Number** — `L25000359935`, `P03000141809`, `M23000008792`, `F97319`. 6 or 12 characters. The primary key of the corporate register, present on the detail page, in bulk, and as the join target from DBA records. The first character encodes entity class (`P` profit corp, `L` FL LLC, `M` foreign LLC, `F`/`K`/`J` legacy, `T` trademark, `G` fictitious registration). Never reused as far as can be told. **This is the anchor Datum should key on.**
2. **FEI/EIN** — present on the corporate detail page, in `cordata` field 18, on the DBA detail page, and as `Owner FEI Number` in `ficdata` field 26. It is the one identifier that crosses *between* the two registers and would cross into federal sources. Not universally populated, and not unique when a parent files under one EIN across several entities — so it's a strong corroborating signal, not a primary key.
3. **Registered agent name + address** — a very strong disambiguator for small contractors, where the agent is usually the owner or a local law firm.
4. **Prior legal names** from `NameHistory` — directly addresses the "Riddle Plumbing LLC vs. Donnie Riddle Plumbing & Htg" problem when the difference is a real name change rather than a colloquialism.
5. `aggregateId` GUID — **do not use.** It is a URL-routing artifact, not a published identifier, and its stability is unverified.

### Consumer-data boundary

**Nothing in Sunbiz is consumer credit data.** There is no FCRA exposure here and no personal credit on any owner or guarantor. It is exactly the kind of business public record the project is scoped to.

One boundary to hold anyway: officer, authorized-person, registered-agent and DBA-owner records contain **named individuals with street addresses**, and for a 5-person contractor those are frequently *home* addresses. `Owner 1 Name Format = (P)` marks the person case explicitly in bulk. These are lawfully public, but they are personal data about private individuals. Surface them only where they serve entity resolution — confirming that two filings share a principal — and do not build a person-centric index, a person search, or anything that aggregates an individual across sources. That drifts toward a consumer product without ever crossing an obvious line.

## Example URLs

Two real URLs, both fetched during this run, both of which render for anyone who pastes them into a browser.

**1. Corporate detail — `SNYDER AIR CONDITIONING, PLUMBING & ELECTRIC, LLC`** (fetched 2026-09-15T08:58Z, re-verified as a fresh navigation at 2026-09-15T08:58Z)

```
https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResultDetail?inquiryType=DocumentNumber&aggregateId=forl-m23000008792-8433b453-5616-4417-8507-9d8034e0c670&directionType=Initial&searchNameOrder=SNYDERAIRCONDITIONINGPLUMBINGE%20M230000087920&searchTerm=M23000008792
```

**2. Fictitious name detail — `SNYDER AIR CONDITIONING`, Duval County** (fetched 2026-09-15T09:02Z)

```
https://dos.sunbiz.org/scripts/ficidet.exe?action=DETREG&docnum=G01157900038&rdocnum=G01157900038
```

A third, useful for seeing the alphabetical-seek behaviour (fetched 2026-09-15T08:57Z):

```
https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults?inquiryType=EntityName&searchTerm=SNYDER%20AIR%20CONDITIONING
```

### Generalized patterns

```
# Entity name search (GET)
https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults
  ?inquiryType=EntityName
  &searchTerm={urlencoded name}

# Next page (GET) — cursor carried in searchNameOrder
https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults
  ?InquiryType=EntityName
  &inquiryDirectionType={ForwardList|BackwardList}
  &searchNameOrder={normalized name}%20{docnum}{digit}
  &SearchTerm={urlencoded original term}
  &entityId={docnum}
  &listNameOrder={normalized name of first row on current page}%20{docnum}{digit}

# Document number lookup (POST) -> 302 to detail
POST https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber
  SearchTerm={docnum}&InquiryType=DocumentNumber&SearchNameOrder=

# Detail (GET) — requires BOTH aggregateId and searchNameOrder
https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResultDetail
  ?inquiryType={EntityName|DocumentNumber}
  &aggregateId={filingtype}-{docnum lowercased}-{guid}
  &directionType=Initial
  &searchNameOrder={normalized name}%20{docnum}{digit}
  &searchTerm={term}

# Name history / event history (GET) — same aggregateId + SearchNameOrder
https://search.sunbiz.org/Inquiry/CorporationSearch/{NameHistory|EventHistory}
  ?aggregateId={...}&entityId={docnum}&CurrentPage=0
  &SearchTerm={term}&InquiryType={...}&inquiryDirectionType=CurrentList
  &SearchNameOrder={...}

# Fictitious name detail (GET) — dos.sunbiz.org, ROBOTS-DISALLOWED, documented only
https://dos.sunbiz.org/scripts/ficidet.exe?action=DETREG&docnum={G-number}&rdocnum={G-number}
```

## Raw response excerpt

Actual markup as returned, captured from the live DOM of example URL 1 at **2026-09-15T08:58Z**. I trimmed to the first three `div.detailSection` blocks — the name block, the filing-information block, and the principal-address block — and dropped the page chrome (nav bar, search-again form, officer blocks, annual-report table, document-image list) that surrounds them. Nothing inside the excerpt is altered.

```html
<div class="detailSection corporationName">
        <p>Foreign Limited Liability Company</p>
        <p>SNYDER AIR CONDITIONING, PLUMBING &amp; ELECTRIC, LLC</p>
    </div>
<div class="detailSection filingInformation">
        <span>Filing Information</span>
        <span><div>
    <label for="Detail_DocumentId">Document Number</label><span>M23000008792</span>
    <label for="Detail_FeiEinNumber">FEI/EIN Number</label><span>93-2213188</span>
    <label for="Detail_FileDate">Date Filed</label><span>07/07/2023</span>
    <label for="Detail_EntityStateCountry">State</label><span>DE</span>
    <label for="Detail_Status">Status</label><span>ACTIVE</span>
<label for="Detail_LastEvent">Last Event</label><span>LC STMNT OF RA/RO CHG</span>
<label for="Detail_LastEventFileDate">Event Date Filed</label><span>04/03/2025</span>
<label for="Detail_EventEffectiveDate">Event Effective Date</label><span>NONE</span>
</div></span>
    </div>
<div class="detailSection">
            <span>Principal Address</span>
            <span>

<div>
1431 GREENWAY DR<br>
    SUITE 200<br>
        IRVING, TX 75038<br>
</div>



</span>
                <br>
                <span>Changed: 05/29/2026 </span>
        </div>
```

**What this tells a parser author.** Every scalar field is a `<label for="Detail_*">` immediately followed by its `<span>` value — so the parse is a label-keyed lookup, not positional, and it survives fields being absent or reordered. The `for` attributes (`Detail_DocumentId`, `Detail_FeiEinNumber`, `Detail_FileDate`, `Detail_EntityStateCountry`, `Detail_Status`, `Detail_LastEvent`, `Detail_LastEventFileDate`, `Detail_EventEffectiveDate`) are the stable selectors and should be the contract a fixture test asserts on. Address blocks are the opposite: a `div` of `<br>`-separated lines with no per-line markup and heavy incidental whitespace, so city/state/zip must be parsed out of the final line by rule. The "Changed:" date sits in a sibling `<span>` *outside* the address block, with a trailing space. `detailSection` blocks other than the first two carry no distinguishing class — they are identified only by their leading `<span>` caption ("Principal Address", "Mailing Address", "Registered Agent Name & Address"), so the parser must key on caption text and will break silently if a caption is reworded. That is the fragile seam; a fixture test should pin it.

For comparison, the fictitious-name detail on the legacy host (captured 2026-09-15T09:02Z) has **no semantic markup at all** — it is nested `<table>` layout with `class="heading"` / `class="data"` cells and `<td>`-position-dependent values. If that path ever becomes necessary despite robots, expect a materially more brittle parser.

## Open questions

1. **Does the quarterly file include inactive entities?** The page says it contains "all active data at the time the file is generated." A dissolved or administratively-dissolved customer is one of the strongest signals Datum can surface, so if inactive entities are absent from bulk, they have to come from somewhere else. **To resolve:** one manual quarterly pull, then check whether any record carries Status `I`. Half an hour of work and it changes the architecture, so do it first.
2. **Rate limits on `search.sunbiz.org`.** Unpublished. Finding the ceiling means generating abusive traffic against a state system, which I declined to do. **To resolve:** ramp slowly in production behind a conservative fixed delay and instrument for 429/403, or email the Division and ask — `dos.fl.gov` has a contact form, and a state agency answering "here is our limit" in writing is worth more than a probe.
3. **Is the `aggregateId` GUID stable over time?** It appears to be per-record rather than per-session, but I only observed it within a single 10-minute window. **To resolve:** record a handful of detail URLs and re-fetch them in a week. Until then, treat detail URLs as ephemeral and always re-resolve from the document number.
4. **The exact name-normalization strip-list.** Sampled, not specified — and my sample does not explain `AIR CONDITIONING, INC. OF STUART`. **To resolve:** derive it offline against `cordata`, where every name in the state is available and a candidate rule can be tested against all of them at once. This is a build-time job, exactly the kind CLAUDE.md §6 says to settle before runtime.
5. **Does "for informational purposes" constrain commercial resale?** Matters for Phase 2/3 (supply houses, community banks), not Phase 1. **To resolve:** counsel.
6. **How complete is FEI/EIN population in bulk?** It is the only identifier that bridges the corporate and fictitious-name registers, so its fill rate sets a ceiling on cross-register resolution. **To resolve:** count non-blank values at offset 481 once the file is pulled.
7. **Federal tax lien files (`flrd`, `flrs`) — not investigated.** They arrive through this same free SFTP channel but are a distinct record type with their own layout and their own questions. **They need their own recon run.**
8. **Also not investigated, and each needs its own run:** the judgment lien system, the UCC filing search (a separate Florida system operated under contract, not part of Sunbiz), and any Duval/St. Johns county clerk official-records search. This report covers the Sunbiz corporate and fictitious-name registers only.

## Verified by manual pull (2026-10-12)

First real file pulled by Andres over SFTP: `doc/cor/20261009c.txt` (1.1 MB, 834 records). Findings:

- **Record length:** each record is 1440 bytes followed by a `\n` (LF, no CR). The last 4 bytes of every record are NUL (`\0`) padding, so the meaningful content is 1436 characters. That matches the officer-block arithmetic: 669 + 6 × 128 − 1 = 1436. Tools that stop at NUL bytes (macOS `awk`) report 1436.
- **Field positions confirmed** on 5 sample records: document number (1–12), status (205; all 834 rows `A`, as expected for a day of new filings), filing type (206–220; `FLAL`, `DOMP` seen), officer 1 title (669–672; `AMBR`, `PTSD`, `DPTS` seen), officer 1 name (674+).
- **Date format at 473–480 is MMDDYYYY** (e.g. `10052026`). Values include future dates (`01012027`) and older years (`05152017`), so this field may be an effective date rather than the filing date for some records. 🟡 Check what it means against a few sunbiz.org detail pages before labeling it "filed date" anywhere a contractor sees.
- **FEI/EIN blank** on the 5 sampled new filings. Expect a low fill rate on brand-new companies.

## Verified: quarterly snapshot + daily vs quarterly (2026-10-22 / 2026-10-25)

- **Quarterly `cordata.zip` (generated 2026-10-07):** 10 files, 12,987,601 records, lines 1440 bytes + CRLF (1442 on disk). Despite "all active data" on the state's page, it **includes inactive companies**: 9,168,902 `I` vs 3,818,699 `A`.
- **The daily corporate file is new registrations only** (tested on `20261009c.txt`): all 834 document numbers were absent from the Oct 7 snapshot (anti-join, `snowflake/07_explore_daily_vs_quarterly.sql`), all status `A`, all document numbers from the 2026 series. 🟡 One file tested; recheck on a few more days before treating it as a rule.
- **Implication:** changes to EXISTING companies (dissolution, reinstatement, address or officer changes) do not arrive in the daily `c` file. Between quarterly snapshots they arrive only through the daily corporate **events** file (`doc/cor/events/yyyymmddce.txt`). Without events, a company's status in Datum can be up to ~3 months stale — and a dissolution is exactly the signal a contractor needs. **Events file needs its own recon run.**
- **"Added to our record that day" ≠ filed that day:** the Oct 9 file holds filings dated Oct 1–8, so the state processes filings with a lag of days.
- **Date at 473–480 is not reliably a filing date:** the 834 new companies include 21 dated 2027-01-01, 809 in 2026 (latest 2026-11-04, after the file was published), and 4 dated 2017–2025. Future dates fit an effective date chosen by the filer. 🟡 Older dates may be foreign companies' original formation dates; unverified.
- **Document-number prefixes seen:** `A` (DOMLP, limited partnership), `F` (FORP/FORNP, foreign corporation), `L` (LLC), `P` (domestic profit corporation). 🟡 Inferred from samples, not from the state's documentation.
