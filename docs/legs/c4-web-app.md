# Leg C4: the web app

Branch `leg/c4-web-app` (stacked on `leg/c3-fact-report`) · the pull request is opened after the review · run on Nov 24, 2026 · risk tier **High** · status: **built, with every check passing. The Deep review is in progress, and its result is added to section 4 in a later commit.**

This is the last of the four legs of Phase C. Leg C2 made the search and leg C3 made the report. This leg puts both on pages that a contractor can open on a phone. The app runs on the Mac. Putting it on the internet is not part of this phase.

**The short version**

- **The app works from end to end on the Mac.** I started it with the brief's command and ran the two live checks against the real data and the real extraction step.
  - `ferguson ac boynton beach` put **FERGUSON AIR CONDITIONING & REFRIGERATION, INC.** first, in **1.65 seconds** (acceptance test A1).
  - `the pool guy off race track rd` showed **no company**, in **0.88 seconds**, and asked for a business name, a street or a city (acceptance test A2).
- **It is private and it fails closed** (working rule W8). Every address except `/healthz` answers 401 without the access code. The app refuses to start with no code set. Search engines are told not to index it in three places. A request from another machine is refused.
- **The typed note goes to the extraction step and nowhere else** (working rule W6). It arrives in the body of a POST, so it is never part of an address. It is not logged, not stored and not shown back. A test captures every log line during a search and fails if the note is in one.
- **Every page fits a phone 390 pixels wide.** Six screenshots are under `data/screens/`, which git ignores.
- The offline tests pass: **429**, of which 61 are new in this leg. They start no server and make no network call.
- The leg made **2 of the 10 live extraction calls** the phase allows, and used **no Snowflake credits**.

**What is left for Andres**

1. **Three things only you can do** (section 7): put an access code in the secrets file, open the app on your phone, and decide where to host it.
2. **Rule on three questions this leg could not decide.** Each has a row in `docs/open_questions.md`.
   - Q42: the pages ask for a street, and the search does not use one.
   - Q43: a search engine's crawler cannot read `/robots.txt`, because that address needs the access code too.
   - Q44: the app keeps extracted fields in memory for up to an hour, so that a report can say how its company was identified.
3. Read section 3, which holds the calls I made where the brief did not say.
4. Answer the three questions in section 6, because this is a High-tier change.

The app is built and shown to nobody. Whether it is ready for a contractor is your call, and it depends on gates outside this phase: the 90% bar on the hand-checked test set, the link hand checks and a lawyer's review.

---

## 1. What I built

### The picture

```
 a phone or a browser                          src/datum/web/app.py  (FastAPI)
        │
        │  every request ──▶ the gate:  from this Mac?  ──no──▶ 403
        │                               /healthz?       ──yes─▶ "ok"
        │                               access code?    ──no──▶ 401, and the browser shows its sign-in box
        ▼
 GET  /                    the search box
 POST /search   the note ──▶ extraction step (Claude) ──▶ business name, city, street
                                   │ names no business ──▶ a page that asks for one. No company is shown
                                   ▼
                             search.py (Postgres) ──▶ shortlist page, each company a link with a random token
 GET  /company/{number}?from={token} ──▶ report_builder.py ──▶ report page
 GET  /robots.txt          "Disallow: /"
 GET  /static/...          Pico CSS and four rules of Datum's own
```

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| `src/datum/web/app.py` | The web app. FastAPI is a Python web framework: a function is attached to an address, and the framework calls it when a request for that address arrives. Uvicorn is the program that listens on a port and hands each request to the app | Decision d20: FastAPI, pages rendered on the server, no JavaScript framework. The app has no JavaScript at all |
| `create_app()` | The function that builds the app from three things passed in: the access code, the extraction step, and a function that opens the two backends | Passing them in is called dependency injection. The tests pass in stand-ins, so they need no API key, no database and no network (`CLAUDE.md` rule 4) |
| The gate | A piece of code that runs around every request. It refuses another machine, lets `/healthz` through, asks everything else for the access code, and puts five headers on every answer | Working rule W8. One place decides who gets in, so a new page cannot be added without the code in front of it |
| `Picks` | A small store in memory that remembers, for an hour, how each company on a recent shortlist was identified. The shortlist's links carry a random token that stands for it | The report has to say how its company was picked (rules W6 and W7), and those details may not travel in an address, where a browser history would keep them |
| `src/datum/web/templates/` | Seven Jinja templates. A template is an HTML page with holes, and Jinja fills the holes. It escapes what it fills in, so a company name can never become markup | Decision d20. The templates hold no sentence of their own: every word comes from `wording.py` or from the data, and a test checks it |
| `src/datum/web/static/` | Pico CSS 2.1.1 with its license and a note on where it came from, and `datum.css` with four rules | One copy in the repo means a contractor's phone loads the style sheet from Datum and never calls a third party |
| 14 new entries in `src/datum/wording.py` | The sentences and labels of the pages | Leg C3's rule: every fixed sentence lives in one module |

### The pages

| Address | What it shows | When |
|---|---|---|
| `GET /` | A heading, one box and a button | Always |
| `POST /search` | The shortlist: up to five companies, each with its level, document number, city, reasons, source and fetch date, and a link to its report | The note names a business, and the search finds at least one company |
| | A sentence that asks for a business name, a street or a city, and the box again. No company | The note names no business (acceptance test A2), is empty, or is longer than 500 characters |
| | "The search is unavailable right now, so no company is shown." | The extraction step or the database fails |
| `GET /company/{document_number}` | The report of leg C3, laid out as a page | The number belongs to a company |
| | A plain 404 page that repeats nothing from the address | The number has the wrong shape, or no company has it |
| `GET /healthz` | The two letters `ok` | Always, with no access code |

### Files

| File | New or changed |
|---|---|
| `src/datum/web/app.py` | New |
| `src/datum/web/templates/` (7 files) | New |
| `src/datum/web/static/` (`pico.min.css`, `PICO_LICENSE.md`, `README.md`, `datum.css`) | New |
| `tests/test_web.py` | New. 61 tests under 37 names |
| `src/datum/wording.py` | Changed: 14 entries added for the pages |
| `requirements.txt` | Changed: five packages and the six they brought with them |
| `docs/open_questions.md` | Changed: Q42 to Q44 added |

No Snowflake object, no dbt model and no Postgres table was touched.

### Packages

The brief names the packages and asks for the current stable version of each, pinned with a comment.

| Package | Version | What it is for |
|---|---|---|
| `fastapi` | 0.165.0 | The web framework, and its test client |
| `uvicorn` | 0.54.0 | The program that serves the app |
| `Jinja2` | 3.1.6 | The template library |
| `python-multipart` | 0.0.34 | Reads a submitted form |
| `httpx` | 0.28.1 | What FastAPI's test client is built on. It makes no network call in the tests |

Six more came with them as dependencies: `starlette`, `MarkupSafe`, `click`, `certifi`, `httpcore` and `annotated-doc`. ✅ No package that was already installed changed version, and `requirements.txt` matches the environment line for line. No other package was added.

---

## 2. Checks

### Check 1: the tests

```
pytest
429 passed in 1.66s

ruff check src tests
All checks passed!
```

✅ `tests/test_web.py` holds 61 tests. Each drives the app through FastAPI's test client, which calls the app inside the test's own process: no server starts, no port opens and nothing leaves the machine. The tests the brief asks for by name:

| What the brief asks | The test | The input that makes it fail |
|---|---|---|
| The app will not start without the code | `test_the_app_will_not_be_built_without_an_access_code` and `test_a_start_with_no_access_code_in_the_environment_fails` | An empty or missing access code that does not raise an error |
| Every route but `/healthz` answers 401 without it | `test_every_address_but_healthz_answers_401_without_the_access_code`, run for 13 addresses, each with no code, a wrong code, and the code typed as the name | Any address that answers anything but 401. A second test fails if the app gains a route that is not on the list of 13 |
| The three no-index signals are present | `test_the_three_no_index_signals_are_present` | A page without the meta tag, an answer without the header, or a `/robots.txt` that does not say `Disallow: /` |
| The note does not appear in the logs during a search | `test_nothing_about_a_search_is_written_to_a_log` | The note, the extracted name, or the words of an error that quotes the note, in any log line. Every logger is captured at its most talkative level |
| Auto-escaping stays on | `test_a_company_name_that_holds_markup_is_shown_as_text_and_never_as_markup` | A company called `<script>alert("x")</script> & <b>INVENTED</b> CO LLC` whose markup reaches the page unescaped |
| A document number that does not look like one, or matches no company, gets a plain 404 | `test_an_address_that_names_no_company_gets_a_plain_404_that_repeats_nothing`, run for 8 addresses | A 404 page that repeats anything from the address, or any other status |
| When extraction fails, the page says the search is unavailable and shows no company | `test_a_failed_extraction_says_the_search_is_unavailable_and_shows_no_company` | Four kinds of error, and a reply with each field missing in turn. It fails if a company or a link to one is on the page |
| A vague note shows no company (A2) | `test_a_vague_note_asks_for_a_business_and_shows_no_company` | Any company, any link to one, or any word of the note on the page |
| Every page has a viewport tag and no fixed width wider than 390 pixels | `test_every_page_has_a_viewport_tag_and_loads_only_the_apps_own_style_sheets` and `test_nothing_of_datums_own_sets_a_width_wider_than_a_phone` | A page without the tag, a script, a style sheet from another site, or a width in pixels above 390 in Datum's own files |

The other tests, grouped by what they guard:

| What is guarded | Tests |
|---|---|
| The door | A malformed sign-in header is refused and does not crash. Any user name is accepted and only the code counts. A request from another machine is refused, with the code or without it. Only the exact word "yes" switches that off |
| The note | It is never shown back and never part of an address. It reaches the extraction step once, trimmed. An empty or over-long note is never sent. The search address takes only a POST |
| The shortlist | The right company is first. A tie is said on the shortlist and on the report (rule W7). The Strong companies that did not fit are shown under the list with their source and without a link |
| The report page | No page holds a banned word (rule W4), for each of the six fixture companies. Each lien shows its own source and fetch date. Every checked and unchecked source is on the page. A report opened by its number alone claims no match level |
| The token | It is forgotten after an hour, the oldest goes first, and a token from one shortlist says nothing about a company that was not on it |
| The files | The templates hold no sentence of their own. Pico's file has the checksum its README records and calls no other address |

### Check 2: the app started with the brief's command, and the two live checks

The brief asks for `uvicorn datum.web.app:app --host 127.0.0.1`, with a throwaway access code set on the same line and never written anywhere. I put one more setting on that line, `PYTHONPATH=src`, which tells Python where the `datum` package is. The code was made up by the shell, kept in a shell variable for the length of one command, and is not in any file, any log or this report.

```
PYTHONPATH=src APP_ACCESS_CODE=<a throwaway code> uvicorn datum.web.app:app --host 127.0.0.1

healthz without the code:     ok [200]
home page without the code:   401
home page with a wrong code:  401
home page with the code:      200

--- live check 1: ferguson ac boynton beach
status 200, 1.654628 seconds
<h2><a href="/company/P98000033661?from=TOKEN">FERGUSON AIR CONDITIONING &amp; REFRIGERATION, INC.</a></h2>
I read that as: the business name "Ferguson Air Conditioning", the city "Boynton Beach"

--- live check 2: the pool guy off race track rd
status 200, 0.884162 seconds
company links on the page: 0
That describes a business but doesn't name one. Add its name, a street or a city.

--- the report of the first company
status 200, 0.020181 seconds
No flags found in the sources checked.
How this company was identified: from the business name "Ferguson Air Conditioning", the city "Boynton Beach" · match level Likely
(name is similar (91/100); principal city on record begins with the city you gave; ACTIVE) · chosen by the user from a shortlist.

--- headers
x-robots-tag: noindex, nofollow
cache-control: no-store
robots.txt: User-agent: *  Disallow: /
```

| Check | Result | Time |
|---|---|---|
| A1: `ferguson ac boynton beach` puts FERGUSON AIR CONDITIONING & REFRIGERATION, INC. first | ✅ It is the first company on the shortlist | 1.65 seconds, of which the extraction call is the larger part |
| A2: `the pool guy off race track rd` shows no company | ✅ No company and no link to one. The page asks for a name, a street or a city | 0.88 seconds |
| The report of the company picked | ✅ Built from the real tables | 0.02 seconds |

- ✅ These two are the only live extraction calls of the leg, and of the phase so far. Working rule W10 allows 10.
- ✅ The server's own log holds 10 request lines, each with the method, the address and the status. It holds no access code and no note: I searched it for "ferguson", "pool guy" and "race track" and found none.
- 🟡 The report's line says "chosen by the user from a shortlist". In this check a command followed the first link. Nobody chose.
- 🟡 Acceptance test A1 says "on a phone, under 3 seconds, on the deployed address". This was the Mac talking to itself, so it shows the app's own time and not a phone's.

### Check 3: the screenshots at 390 pixels

✅ Google Chrome is installed, and six screenshots are under `data/screens/`, which git ignores. They show the invented fixture companies, so they hold no real company.

| File | The page |
|---|---|
| `1_search.png` | The search box |
| `2_shortlist.png` | A shortlist of five |
| `3_report_with_flags.png` | A report with two federal liens |
| `4_report_no_flags.png` | A report with no flag |
| `5_asks_for_a_business.png` | The page for a vague note |
| `6_not_found.png` | The plain 404 page |

- ✅ I looked at the shortlist and at the report with flags. Every line wraps inside the 390 pixels, the two-column table fits, and nothing is cut off at the right edge.
- **How they were made, because the first attempt misled me.** Headless Chrome (Chrome with no window) will not make its window narrower than about 500 pixels on this Mac. Asked for 390, it laid the page out at 500 and cut the picture at 390, which looked exactly like a page that overflows a phone. So each page is shown inside a frame exactly 390 pixels wide, in a wider window, and the picture is cut to the frame.
- 🟡 A screenshot is not a phone. Tap targets, the on-screen keyboard and the sign-in box on iOS are yours to try (section 7).

### Check 4: what a visitor without the code sees

```
GET  /                      → 401, empty body, WWW-Authenticate: Basic, X-Robots-Tag: noindex, nofollow
POST /search (with a note)  → 401, and the note never reaches the extraction step
GET  /company/T26000000001  → 401
GET  /static/pico.min.css   → 401
GET  /robots.txt            → 401
GET  /docs, /openapi.json   → 401 (and FastAPI's automatic pages are switched off behind it)
GET  /healthz               → 200 "ok"
any address, another machine→ 403, with the code or without it
```

✅ This is `test_every_address_but_healthz_answers_401_without_the_access_code` and `test_a_request_from_another_machine_is_refused_even_with_the_code`, and the first four lines of check 2 on the real server.

---

## 3. Decisions I made and why

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | The door is one piece of code that runs around every request, and not a check inside each page | A page added later is behind the door without anyone remembering to put it there. Static files and unknown addresses are covered too | A route that should ever be public has to be named in the gate, as `/healthz` is |
| 2 | The app refuses a request that does not come from the Mac itself, unless `APP_ALLOW_OTHER_MACHINES` is set to exactly `yes` | Rule W8: during this phase only the Mac can reach the app. Uvicorn is told to listen on `127.0.0.1`, and the app checks again, so one mistyped start command does not open it. The switch exists because the brief lists "open the app on his phone" as a step for you | With the switch on, the code travels unencrypted over the home network. That is acceptable for a few minutes of testing and it is not hosting |
| 3 | A shortlist's link carries a random token, and the app keeps what the token stands for in memory for an hour | The report has to say how its company was identified (rules W6 and W7). The brief makes the report a GET, and the extracted name in an address would land in a browser history. A token says nothing | 🟡 The extracted fields are held in memory for up to an hour, 200 shortlists at most. Restarting the app forgets them, and a report opened later says "opened by its document number". Question Q44 |
| 4 | `/robots.txt` needs the access code, like everything else | The brief's test says every route but `/healthz` answers 401 without the code | 🟡 A crawler cannot read the file. The header on every answer, the 401 included, is the signal it can see. Question Q43 |
| 5 | The Strong companies that did not fit on the shortlist are shown under it without a link | Leg C3 shows them and does not let them be picked, because whether they belong on the list is question Q34 | A contractor who wants one of them has to search again with more detail. Its document number is on the page |
| 6 | A note longer than 500 characters is not sent to the extraction step | The box is for a business name and a city. A very long text costs more to extract and is more likely to hold things about people | A long, honest note is turned away with a sentence that says why |
| 7 | When extraction or the database fails, the page answers with status 503 and one fixed sentence, and the log gets the error's class name only | An error's message can quote the note, and a database error can quote a query. Neither may reach a page or a log | The log says what kind of error it was and not what it said |
| 8 | Every 404 says the same sentence and repeats nothing from the address | An address can hold anything a person or a program types. A page that repeated it would show markup or a person's name back | The page does not say whether the number had the wrong shape or belongs to no company |
| 9 | The search box tells the browser not to remember what is typed (`autocomplete="off"`) | Rule W6 says the note is never stored. A browser's memory of form entries is a store | The contractor types the name again each time |
| 10 | Five headers go on every answer: no indexing, no caching, no referrer, no guessing a file's type, and a content policy that allows only the app's own two style sheets | A shortlist should not sit in a cache, and a link to the state's site should not tell that site which page it came from. With no script allowed, markup that slipped through could not run | Pico's small pictures live inside its file, so the policy allows pictures from the page itself (`data:`) |
| 11 | The real app is built the first time Uvicorn asks for it, and not when the file is imported | The tests import `create_app` with no access code set. The real start still fails at once when the code is missing, because Uvicorn asks for the app straight away | One unusual function, `__getattr__`, at the bottom of `app.py`, with a comment and two tests |
| 12 | One Postgres connection is opened per request and closed when the request is answered | The app answers requests on several threads, and one shared connection is not safe to use from two threads at once | A connection costs a few milliseconds each time. At a contractor's pace that is nothing |
| 13 | The start command needs `PYTHONPATH=src` in front of the brief's command | The `datum` package is in `src/` and is not installed into the environment. Without the setting, Uvicorn cannot find it | One more thing to type. Section 7 gives the whole line |

---

## 4. What I couldn't verify, and open questions for Andres

### What I couldn't verify

1. 🟡 **The app on a real phone.** The screenshots are 390 pixels wide. A phone's keyboard, its sign-in box and its tap targets were not tried (section 7).
2. 🟡 **The app reached from another machine.** The switch `APP_ALLOW_OTHER_MACHINES` and the refusal of other machines are tested with stand-ins. I did not start the app on `0.0.0.0` or open it from a second device.
3. 🟡 **The three-second target of acceptance test A1 on a deployed address.** The live check took 1.65 seconds on the Mac. A host and a phone network add time I did not measure.
4. 🟡 **Whether a street should be searched** (question Q42). The pages ask for one and the search does not use it.
5. 🟡 **What a crawler does with a `/robots.txt` it cannot read** (question Q43).
6. 🟡 **Whether holding extracted fields in memory for an hour is within rule W6** (question Q44).
7. 🟡 **More than one visitor at a time.** The token store has a lock and each request has its own database connection. I did not load-test the app.
8. 🟡 **The cost of an extraction call.** The figure of about $0.0004 a call is the plan's, and I did not read it off a bill.
9. 🔴 **That the access code alone is enough protection for a hosted app.** HTTP Basic sends the code with every request, and without HTTPS it travels unencrypted. On the Mac that does not matter. On a host it needs HTTPS, which is part of the hosting decision and not of this leg.

### Questions added to `docs/open_questions.md`

| # | The question, in short |
|---|---|
| Q42 | The pages ask for a street, and the search does not use one |
| Q43 | A crawler cannot read `/robots.txt`, because it needs the access code |
| Q44 | Extracted fields are kept in memory for an hour, so that a report can say how its company was identified |

### The review

The Deep review is in progress. Its rounds, and every finding with its answer, are added here in a later commit.

---

## 5. Cost

| Item | Rate | Units | Cost |
|---|---|---|---|
| Snowflake | About $2 a credit | 0 credits. The leg made no call to Snowflake | $0 |
| Claude API, the extraction step | 🟡 About $0.0004 a call (the plan's figure) | 2 calls, the two live checks | 🟡 About $0.0008, less than a tenth of a cent |
| Postgres, Uvicorn and Chrome on the Mac | Free | | $0 |

Phase C has used about **0.63** of its cap of 3 Snowflake credits (0.47 in leg C1, 0.15 in leg C2, none in legs C3 and C4), and **2** of its 10 live extraction calls. No hosted account, hosted database or paid service was created.

---

## 6. Three questions Andres should be able to answer

1. A request arrives for `/company/P98000033661` with no access code. Which piece of code answers it, what does it answer, and why is that piece a single gate around every request and not a check inside the page's function?
2. The note is sent with POST and not with GET. What is the difference, and name two places the note would have ended up with GET.
3. The shortlist links to a report with `?from=` and a random token. What does the token stand for, where is that kept, and what does the report say when the token is unknown?

**Answers, to check yourself.** (1) The gate in `create_app()` answers, before any page's function runs. It answers 401 with a `WWW-Authenticate: Basic` header, which is what makes a browser show its sign-in box, and with the header that tells a crawler not to index. One gate means a page added later is behind it without anyone having to remember, and so are the style sheets and every unknown address. (2) A GET puts what was typed into the address, after a question mark. A POST sends it in the body of the request, which is not part of the address. With GET the note would be in the browser's history and in the server's access log, and it could be bookmarked or shared with the link. (3) The token stands for how each company on that shortlist was identified: the extracted business name, city and street, the match level, the evidence and how many others tied. The app keeps that in memory, in `Picks`, for an hour. With an unknown or forgotten token the report says "opened by its document number, so no match level applies", because it then knows of no search.

---

## 7. What only Andres can do

### 1. Put an access code in the secrets file

**Why.** The app refuses to start without a code. I may not read or edit the secrets file, so this line is yours to add.

1. In VS Code (Visual Studio Code), open the file `.env` in the folder `~/datum`. It is the file that already holds your `ANTHROPIC_API_KEY`.
2. Add one line at the end: `APP_ACCESS_CODE=` followed by a code you make up. Make it long, such as four unrelated words with hyphens between them. Type no spaces around the `=`.
3. Save the file. Git ignores it, so it is never committed.

**Done when** the next step starts the app with no error about `APP_ACCESS_CODE`.

### 2. Start the app and open it on the Mac

In the VS Code terminal:

```
cd ~/datum
source .venv/bin/activate
PYTHONPATH=src uvicorn datum.web.app:app --host 127.0.0.1
```

| Piece | What it does |
|---|---|
| `cd ~/datum` | Moves the terminal into the project folder |
| `source .venv/bin/activate` | Switches this terminal to the project's own Python and packages |
| `PYTHONPATH=src` | A setting for this one command: it tells Python that the `datum` package is in the folder `src` |
| `uvicorn` | The program that serves the app |
| `datum.web.app:app` | Which app to serve: the thing called `app` in the file `src/datum/web/app.py` |
| `--host 127.0.0.1` | Listen only for this Mac itself. `127.0.0.1` is the address every computer uses for "me" |

Then open `http://127.0.0.1:8000` in Chrome. The browser shows a sign-in box. Type anything as the name, and your access code as the password. Postgres has to be running: `brew services start postgresql@17` starts it.

**Done when** you see "Check a company" and one box. To stop the app, press Control and C in the terminal.

### 3. Open it on your phone

**Why.** The screenshots show the layout fits. Only a phone shows whether it is comfortable to use.

1. Put the phone on the same Wi-Fi as the Mac.
2. In a second terminal, run `ipconfig getifaddr en0`. It prints the Mac's address on your network, four numbers with dots between them.
3. Stop the app, and start it this way: `APP_ALLOW_OTHER_MACHINES=yes PYTHONPATH=src uvicorn datum.web.app:app --host 0.0.0.0`. The first setting tells the app to answer machines other than the Mac, and `0.0.0.0` tells Uvicorn to listen for them.
4. If macOS asks whether Python may accept incoming connections, allow it.
5. On the phone, open `http://` followed by the Mac's address and `:8000`.

🟡 I did not run these steps, so treat the first try as a test of the instructions too. While the app runs this way, your access code travels unencrypted over your home network. Stop it when you are done, and start it the normal way next time.

**Done when** you have searched for a company on the phone and read its report without scrolling sideways.

### 4. Decide on hosting

The database is 5,503 MB (leg C2's report, check 4), the app needs HTTPS in front of it before the access code is worth anything away from the Mac, and questions Q43 and Q44 change a little once the app is hosted. Creating a hosted account or database is a stop condition of the brief, so nothing was created.
