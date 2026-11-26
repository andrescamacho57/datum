"""test_web.py: offline tests for src/datum/web/app.py, the web app.

Every test drives the app through FastAPI's test client, which calls the app in the same
process: no server is started, no port is opened and nothing leaves the machine. The three
things the app depends on are stand-ins that are passed in: the extraction step is a
function that returns fixed fields, the search holds the invented companies of
tests/fixtures/report/, and the report data comes from the same fixtures.

Several tests are about what must NOT happen: a page without the access code, the typed
note in a log or on a page, a company on the page for a vague note, markup from a company
name reaching the browser. Each says which input makes it fail.

Run from ~/datum:  pytest
"""

import ast                                  # parses source code into its structure, without running it
import hashlib                              # the checksum of the Pico CSS file
import inspect                              # reads the source of the module under test
import logging                              # the level at which the logs are captured
import re                                   # patterns for links, widths and banned words
from contextlib import contextmanager       # turns a function with one `yield` into something to open with `with`
from dataclasses import replace             # a copy of a frozen dataclass with one field changed
from html.parser import HTMLParser          # reads a page the way a browser would, to get the text a person sees
from pathlib import Path                    # the app's templates and static files

import pytest                               # the test runner
from fastapi.testclient import TestClient   # calls the app without a server

import report_fixtures as fx                # tests/report_fixtures.py: the fixture rows as objects
import datum.web.app as web
from datum import wording
from datum.report_builder import FakeReportBackend
from datum.search import FakeBackend
from datum.web.app import Picks, code_given, create_app, other_machines_allowed

CODE = "a-throwaway-code-for-tests"         # not a secret: it exists only inside this file
NOTE = "invented air conditioning boynton beach, ask for the owner Jane Q Doe, cell 904-555-0100"
PRIVATE = ("Jane", "Doe", "904-555-0100", "ask for the owner", "cell")   # words of the note that the extraction step leaves out
FIELDS = {"business_name": "Invented Air Conditioning", "city": "Boynton Beach", "street": "", "is_specific": True}
W4_WORDS = ("clean", "safe", "risky", "trustworthy", "reliable", "credit", "score", "recommend")   # typed out, not read from wording.py
BANNED = re.compile(r"\b(" + "|".join(W4_WORDS) + ")", re.IGNORECASE)
W4_SENTENCE = ("Datum shows a record only when it can confirm that the record belongs to this company. "
               "A record filed under a similar name or at a different address is not shown.")
WEB = Path(web.__file__).resolve().parent   # src/datum/web/


class Text(HTMLParser):
    """Collects the text a person would read on a page: everything between the tags."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def seen(html: str) -> str:
    """The visible text of a page, with runs of white space made one space."""
    reader = Text()
    reader.feed(html)
    return " ".join(" ".join(reader.parts).split())


def make(extract=None, companies=None, flags=None, sources=None, failing_database=False, **settings):
    """An app built from stand-ins, and a list that records every note the extraction step was handed."""
    companies = fx.load_companies() if companies is None else companies
    handed = []

    def default_extract(note):
        handed.append(note)
        return dict(FIELDS)

    def wrapped(note):
        handed.append(note)
        return extract(note)

    search_backend = FakeBackend(companies)                               # one for the app's whole life, so a test can read what it was asked

    @contextmanager
    def open_backends():
        if failing_database:
            raise ConnectionError("could not connect to the database")
        yield search_backend, FakeReportBackend(companies, fx.load_flags() if flags is None else flags, fx.load_sources() if sources is None else sources)

    app = create_app(CODE, wrapped if extract else default_extract, open_backends, today=lambda: fx.BUILT_ON, **settings)
    app.state.search_backend = search_backend
    return app, handed


def as_user(app, name, code, address="127.0.0.1"):
    """A browser stand-in that sends this name and code with every request, as a browser does after its sign-in box."""
    browser = TestClient(app, client=(address, 50000), follow_redirects=False)
    browser.auth = (name, code)
    return browser


def client_for(app, signed_in=True, address="127.0.0.1"):
    """A browser stand-in from this machine, with the right access code or with none."""
    return as_user(app, "anyone", CODE, address) if signed_in else TestClient(app, client=(address, 50000), follow_redirects=False)


@pytest.fixture
def browser():
    app, _ = make()
    return client_for(app)


# --- Rule W8: private, and closed when a setting is forgotten ---------------------------------

def test_the_app_will_not_be_built_without_an_access_code():
    for missing in ("", None, " ", "   ", "\t"):                         # missing, empty, or only spaces: a slip of the keyboard is not a code
        with pytest.raises(RuntimeError, match="APP_ACCESS_CODE is not set"):
            create_app(missing, lambda note: dict(FIELDS), lambda: None)


def test_uvicorns_name_for_the_app_is_built_on_first_use_and_only_once(monkeypatch):
    # `uvicorn datum.web.app:app` asks the module for `app`. It is built then, once, and kept.
    built = []
    monkeypatch.setattr(web, "_app", None)
    monkeypatch.setattr(web, "create_app_from_environment", lambda: built.append("built") or "the app")
    assert web.app == "the app" and web.app == "the app" and built == ["built"]
    with pytest.raises(AttributeError):
        web.no_such_name


def test_importing_the_module_builds_no_app():
    # Read from the code's structure: at the top level of app.py nothing may CALL create_app or create_app_from_environment, inside
    # a try or not. If importing built the app, a test run on a machine that has a code set would start a real app without anyone asking.
    tree = ast.parse(inspect.getsource(web))
    top_level_calls = [getattr(call.func, "id", getattr(call.func, "attr", "")) for statement in tree.body
                       if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                       for call in ast.walk(statement) if isinstance(call, ast.Call)]
    assert "create_app" not in top_level_calls and "create_app_from_environment" not in top_level_calls
    assert "getLogger" in top_level_calls                                 # the check does see top-level calls: this one is there


def test_a_start_with_no_access_code_in_the_environment_fails(monkeypatch):
    # The real start reads APP_ACCESS_CODE from the environment. With none, building the app must raise, so that uvicorn stops.
    def from_an_empty_environment():
        return create_app("", lambda note: dict(FIELDS), lambda: None)

    monkeypatch.setattr(web, "_app", None)
    monkeypatch.setattr(web, "create_app_from_environment", from_an_empty_environment)
    with pytest.raises(RuntimeError, match="will not start"):
        web.app


EVERY_ADDRESS = [("GET", "/"), ("POST", "/search"), ("GET", "/search"), ("GET", "/company/T26000000001"), ("GET", "/company/nonsense"),
                 ("GET", "/robots.txt"), ("GET", "/static/pico.min.css"), ("GET", "/static/datum.css"), ("GET", "/static/README.md"),
                 ("GET", "/no-such-page"), ("GET", "/docs"), ("GET", "/openapi.json"), ("GET", "/healthz/extra"),
                 ("POST", "/healthz"), ("PUT", "/healthz"), ("OPTIONS", "/healthz"), ("DELETE", "/healthz"), ("HEAD", "/healthz"),   # only a plain GET of /healthz is open
                 ("GET", "/heal%0Athz"), ("GET", "/heal%09thz"), ("GET", "/healthz/"), ("GET", "//healthz"), ("GET", "/HEALTHZ")]
# The two with %0A and %09 hold a line break and a tab. Read one way they spell /healthz, and the router does not read them that way.


@pytest.mark.parametrize("method, path", EVERY_ADDRESS)
def test_every_address_but_healthz_answers_401_without_the_access_code(method, path):
    app, handed = make()
    for attempt in (client_for(app, signed_in=False), as_user(app, "anyone", "a wrong code"),
                    as_user(app, CODE, "")):     # no code, a wrong code, and the code typed as the NAME
        answer = attempt.request(method, path, data={"note": NOTE} if method == "POST" else None)
        assert answer.status_code == 401 and answer.text == "", (method, path)
        assert answer.headers["www-authenticate"].startswith("Basic ")   # this header is what makes a browser show its sign-in box
        assert answer.headers["x-robots-tag"] == "noindex, nofollow"     # even the refusal tells a crawler not to index
    assert handed == []                                                   # and the note of the refused POST never reached the extraction step


def test_the_routes_the_app_really_has_are_all_in_the_list_above():
    # If a route is added and not listed, the test above would not cover it. This fails until the list is extended.
    app, _ = make()
    listed = {path for _, path in EVERY_ADDRESS}
    for route in app.routes:
        path = getattr(route, "path", "")
        example = path.replace("{document_number}", "T26000000001")
        assert path == "/healthz" or example in listed or any(known.startswith(path + "/") for known in listed), path


def test_healthz_says_ok_without_the_code_and_nothing_else(browser):
    app, _ = make()
    answer = client_for(app, signed_in=False).get("/healthz")
    assert (answer.status_code, answer.text) == (200, "ok") and answer.headers["content-type"].startswith("text/plain")
    assert answer.headers["x-robots-tag"] == "noindex, nofollow"


def test_the_access_code_is_compared_with_compare_digest(monkeypatch):
    # The brief asks for secrets.compare_digest, which takes the same time for a wrong first character as for a wrong last one.
    # A plain == would let the same requests in and keep the same ones out, so only watching the call can tell the two apart.
    calls = []
    real = web.secrets.compare_digest
    monkeypatch.setattr(web.secrets, "compare_digest", lambda given, expected: calls.append((given, expected)) or real(given, expected))
    app, _ = make()
    assert client_for(app).get("/").status_code == 200 and as_user(app, "anyone", "a wrong code").get("/").status_code == 401
    assert calls == [(CODE.encode(), CODE.encode()), (b"a wrong code", CODE.encode())]   # once per request, as bytes, the given code first


def test_the_framework_describes_itself_at_no_address():
    app, _ = make()
    assert (app.docs_url, app.redoc_url, app.openapi_url) == (None, None, None)
    browser = client_for(app)
    for address in ("/docs", "/redoc", "/openapi.json"):
        assert browser.get(address).status_code == 404                    # with the code too: there is no such page


def test_a_page_that_fails_in_a_way_nobody_foresaw_answers_an_empty_500_and_logs_only_the_kind(caplog, capfd):
    # A company whose source address is not a web address cannot become a Fact, so building the shortlist raises. The error's own
    # message quotes the value. Uvicorn would print that message and the code around it. The app has to stop it first.
    broken = replace(next(c for c in fx.load_companies() if c.document_number == fx.LIEN_COMPANY), source_url="ftp://see-the-secretary/file")
    app, _ = make(companies=[broken])
    with caplog.at_level(logging.DEBUG):
        answer = client_for(app).post("/search", data={"note": NOTE})
    assert (answer.status_code, answer.text) == (500, "") and answer.headers["x-robots-tag"] == "noindex, nofollow"
    printed = "".join(capfd.readouterr())
    for text in (caplog.text, printed):
        assert "see-the-secretary" not in text and "Traceback" not in text and "Invented Air Conditioning" not in text
    assert "a page failed: ValueError" in caplog.text or "a page failed: ValidationError" in caplog.text


def test_a_form_the_search_box_did_not_send_gets_a_plain_page_that_describes_nothing(browser):
    answer = browser.post("/search", files={"note": ("jane-doe-contract.pdf", b"the contents of a file", "application/pdf")})   # a file where the note should be
    assert answer.status_code == 400 and "That could not be read as a search. Type the business's name in the box." in seen(answer.text)
    assert "jane-doe" not in answer.text and "contents of a file" not in answer.text and "detail" not in answer.text


def test_any_user_name_is_accepted_and_only_the_code_counts(browser):
    app, _ = make()
    for name in ("", "andres", "x" * 200):
        assert as_user(app, name, CODE).get("/").status_code == 200


def test_a_malformed_sign_in_header_is_refused_and_does_not_crash():
    assert code_given("Basic " + "YW55b25lOmEtY29kZQ==") == "a-code"         # "anyone:a-code"
    for header in (None, "", "Bearer abc", "Basic", "Basic !!!not-base64!!!", "Basic " + "bm9jb2xvbg==", "Basic /w=="):   # the last two: no colon, and bytes that are not text
        assert code_given(header) is None, header
    app, _ = make()
    for header in ("Bearer abc", "Basic !!!", "Basic /w=="):
        assert TestClient(app, client=("127.0.0.1", 50000), headers={"Authorization": header}).get("/").status_code == 401


def test_a_request_from_another_machine_is_refused_even_with_the_code():
    # During this phase the app is for this Mac only. uvicorn is told to listen on 127.0.0.1, and the app checks again.
    app, handed = make()
    for address in ("192.168.1.20", "10.0.0.5", "8.8.8.8", "testclient", ""):
        answer = client_for(app, address=address).post("/search", data={"note": NOTE})
        assert answer.status_code == 403 and answer.text == "" and answer.headers["x-robots-tag"] == "noindex, nofollow", address
        assert client_for(app, address=address).get("/healthz").status_code == 403
    assert handed == []
    assert client_for(app, address="::1").get("/").status_code == 200    # the other address that means "this machine"
    opened, _ = make(local_only=False)                                   # the switch a later phase will use, behind a real host
    assert client_for(opened, address="192.168.1.20").get("/").status_code == 200


def test_only_the_exact_word_yes_lets_another_machine_in():
    # APP_ALLOW_OTHER_MACHINES is for testing on a phone. Unset, misspelled or set to anything else, the app stays with this Mac.
    assert other_machines_allowed("yes") is True
    for setting in (None, "", "Yes", "YES", "y", "1", "true", "yes ", " yes", "no"):
        assert other_machines_allowed(setting) is False, setting


# --- Rule W8: search engines are told not to index, in three places ------------------------------

def test_the_three_no_index_signals_are_present(browser):
    pages = [browser.get("/"), browser.post("/search", data={"note": NOTE}), browser.get("/company/" + fx.LIEN_COMPANY),
             browser.get("/company/nonsense"), browser.get("/no-such-page"), browser.post("/search", data={"note": ""})]
    for answer in pages:
        assert '<meta name="robots" content="noindex, nofollow">' in answer.text      # 1. the meta tag, on every page
        assert answer.headers["x-robots-tag"] == "noindex, nofollow"                  # 2. the header, on every answer
    robots = browser.get("/robots.txt")
    assert (robots.status_code, robots.text) == (200, "User-agent: *\nDisallow: /\n")   # 3. the robots file: every crawler, every address


def test_every_answer_carries_the_headers_that_keep_a_page_out_of_caches_and_other_sites(browser):
    for answer in (browser.get("/"), browser.post("/search", data={"note": NOTE}), browser.get("/company/" + fx.LIEN_COMPANY), browser.get("/static/datum.css")):
        assert answer.headers["cache-control"] == "no-store" and answer.headers["referrer-policy"] == "no-referrer"
        assert answer.headers["x-content-type-options"] == "nosniff"
        assert answer.headers["content-security-policy"] == ("default-src 'none'; style-src 'self'; img-src 'self' data:; form-action 'self'; "
                                                             "base-uri 'none'; frame-ancestors 'none'")   # the whole policy, word for word


# --- The search ---------------------------------------------------------------------------------

def test_a_note_that_names_a_business_gives_a_shortlist_with_the_right_company_first(browser):
    answer = browser.post("/search", data={"note": NOTE})
    assert answer.status_code == 200
    names = re.findall(r'<h2><a href="/company/(T\d{11})\?from=([A-Za-z0-9_-]{16,})">([^<]+)</a>(?: <small>· Inactive with the state</small>)?</h2>', answer.text)
    assert names[0][0] == fx.LIEN_COMPANY and names[0][2] == "INVENTED AIR CONDITIONING, LLC" and len(names) == 5
    assert len({token for _, token, _ in names}) == 1                     # one random token for the whole shortlist
    text = seen(answer.text)
    assert "Which company do you mean?" in text
    assert 'I read that as: the business name "Invented Air Conditioning", the city "Boynton Beach"' in text
    assert "Strong · Document number T26000000001 · BOYNTON BEACH, FL" in text
    assert "principal city on record begins with the city you gave" in text and "ACTIVE" in text
    # Rule W1: each company on the list is followed by where to check it and when it was fetched.
    assert text.count("Source: Florida Division of Corporations (Sunbiz) record, document number T") == 5 and text.count("fetched about 2026-10-22") == 5


def test_the_typed_note_is_never_shown_back_and_never_part_of_an_address(browser):
    answer = browser.post("/search", data={"note": NOTE})
    for word in PRIVATE + (NOTE,):
        assert word not in answer.text, word                              # not in the page, visible or hidden
    links = re.findall(r'href="([^"]+)"', answer.text)
    assert links and not [link for link in links if "invented" in link.lower() or "boynton" in link.lower()]   # no address carries even the extracted fields
    assert str(answer.url).endswith("/search") and "?" not in str(answer.url)   # the note travelled in the body of the POST, not in the address
    assert 'autocomplete="off"' in answer.text                            # the browser is told not to keep what is typed in the box


def test_the_note_reaches_the_extraction_step_and_nothing_else():
    app, handed = make()
    client_for(app).post("/search", data={"note": "  " + NOTE + "  "})
    assert handed == [NOTE]                                               # one call, with the note trimmed of the spaces around it


def test_nothing_about_a_search_is_written_to_a_log(caplog):
    # Rule W6. Every logger is captured at its most talkative level while a search, a failed search and a report run.
    def broken(note):
        raise ValueError(f"No fields returned for: {note!r}")            # the worst case: an error that quotes the note

    with caplog.at_level(logging.DEBUG):
        app, _ = make()
        browser = client_for(app)
        page = browser.post("/search", data={"note": NOTE})
        browser.get(re.search(r'href="(/company/[^"]+)"', page.text).group(1))
        failing, _ = make(extract=broken)
        assert client_for(failing).post("/search", data={"note": NOTE}).status_code == 503
    logged = caplog.text
    for word in PRIVATE + (NOTE, "invented air conditioning", "Invented Air Conditioning", "No fields returned"):
        assert word not in logged, word                                   # not the note, not the extracted name, not the error's own words
    assert "the extraction step failed: ValueError" in logged             # only the kind of error is logged


def test_a_vague_note_asks_for_a_business_and_shows_no_company():
    # Acceptance test A2: "the pool guy off race track rd" names no business. Working rule S7: its street has no house number, so it
    # still asks for more. The app holds a company whose street IS Race Track Rd, and a search by address would list it.
    on_that_road = replace(next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY), principal_address_1="12 RACE TRACK RD")
    app, _ = make(companies=fx.load_companies() + [replace(on_that_road, document_number="T26000000099")],
                  extract=lambda note: {"business_name": "pool service", "city": "", "street": "Race Track Rd", "is_specific": False})
    answer = client_for(app).post("/search", data={"note": "the pool guy off race track rd"})
    text = seen(answer.text)
    assert answer.status_code == 200 and "That describes a business but doesn't name one. Add its name, or its street address beginning with the house number." in text
    assert app.state.search_backend.address_calls == [] and app.state.search_backend.calls == []   # neither search ran: a street alone matches thousands of companies
    assert "INVENTED" not in answer.text and "/company/" not in answer.text and "Document number" not in text   # no company at all
    assert "race track" not in answer.text.lower() and "pool" not in answer.text.lower()   # and nothing of the note or of what was read from it
    assert '<form method="post" action="/search">' in answer.text         # the box is there to try again


def test_the_note_is_on_no_page_whatever_goes_wrong(caplog, capfd):
    # Rule W6, for every way a search can end. Each page is searched for the note, in the text a person sees and in the page's source.
    def broken(note):
        raise RuntimeError(f"the model said nothing about {note!r}")

    endings = {
        "a shortlist": make(),
        "extraction failed": make(extract=broken),
        "the reply has no name": make(extract=lambda note: {**FIELDS, "business_name": None}),
        "the database is down": make(failing_database=True),
        "no company is close": make(companies=[]),
        "the note names no business": make(extract=lambda note: {**FIELDS, "is_specific": False}),
        "the companies at an address": make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy()),
        "no company at the address": make(extract=lambda note: dict(BY_ADDRESS)),
        "too many companies at the address": make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy(active=51, inactive=0)),
        "the database is down for an address": make(extract=lambda note: dict(BY_ADDRESS), failing_database=True),
    }
    with caplog.at_level(logging.DEBUG):
        for ending, (app, _) in endings.items():
            answer = client_for(app).post("/search", data={"note": NOTE})
            for word in PRIVATE + (NOTE,):
                assert word not in answer.text, (ending, word)
    printed = "".join(capfd.readouterr())                                 # what the app printed, which under Uvicorn is the server's log too
    for word in PRIVATE + (NOTE, "the model said nothing"):
        assert word not in caplog.text and word not in printed, word


def test_a_reply_with_no_business_name_is_an_extraction_failure_and_is_logged_as_one(caplog):
    with caplog.at_level(logging.DEBUG):
        for name in (None, 7, ["Acme"]):
            app, _ = make(extract=lambda note, name=name: {**FIELDS, "business_name": name})
            assert client_for(app).post("/search", data={"note": NOTE}).status_code == 503
    assert caplog.text.count("the extraction step failed: ") == 3 and "the search failed" not in caplog.text   # the fault is the reply's, not the database's
    empty, _ = make(extract=lambda note: {**FIELDS, "business_name": "   "})
    answer = client_for(empty).post("/search", data={"note": NOTE})       # a reply that calls the note specific and gives no name names no business
    assert answer.status_code == 200 and "That describes a business but doesn't name one." in seen(answer.text) and "/company/" not in answer.text


def test_a_failed_extraction_says_the_search_is_unavailable_and_shows_no_company():
    for error in (ValueError("x"), RuntimeError("x"), KeyError("city"), ConnectionError("x")):
        def broken(note, error=error):
            raise error

        app, _ = make(extract=broken)
        answer = client_for(app).post("/search", data={"note": NOTE})
        assert answer.status_code == 503 and "The search is unavailable right now, so no company is shown." in seen(answer.text)
        assert "Try again" not in answer.text                             # a wrong key does not pass in a few minutes, so the page does not say it will
        assert "INVENTED" not in answer.text and "/company/" not in answer.text
    for missing in FIELDS:                                                # a reply with any one field missing is a failed extraction too
        app, _ = make(extract=lambda note, missing=missing: {name: value for name, value in FIELDS.items() if name != missing})
        answer = client_for(app).post("/search", data={"note": NOTE})
        assert answer.status_code == 503 and "INVENTED" not in answer.text, missing


def test_a_database_that_cannot_be_reached_says_unavailable_and_never_shows_an_error(caplog):
    app, _ = make(failing_database=True)
    browser = client_for(app)
    with caplog.at_level(logging.DEBUG):
        search = browser.post("/search", data={"note": NOTE})
        report = browser.get("/company/" + fx.LIEN_COMPANY)
    assert search.status_code == 503 and "The search is unavailable right now" in seen(search.text)
    assert report.status_code == 503 and "The report is unavailable right now." in seen(report.text) and "Try again" not in report.text
    for answer in (search, report):
        assert "could not connect" not in answer.text and "ConnectionError" not in answer.text and "Traceback" not in answer.text
    assert "the search failed: ConnectionError" in caplog.text and "the report failed: ConnectionError" in caplog.text
    assert "could not connect" not in caplog.text                         # the kind of error is logged, and never what the error said


def test_an_empty_or_far_too_long_note_is_never_sent_to_the_extraction_step():
    app, handed = make()
    browser = client_for(app)
    for note, sentence in (("", "Nothing was typed. Type the business's name and its city, or a street address that begins with its house number."),
                           ("   ", "Nothing was typed. Type the business's name and its city, or a street address that begins with its house number."),
                           ("x" * 501, "That is too long to search for. Type the business's name and its city, or a street address that begins with its house number.")):
        answer = browser.post("/search", data={"note": note})
        assert answer.status_code == 200 and sentence in seen(answer.text) and "x" * 40 not in answer.text
    assert browser.post("/search").status_code == 200                     # a POST with no field at all is an empty note, not an error page
    assert handed == []
    browser.post("/search", data={"note": "x" * 500})
    assert handed == ["x" * 500]                                          # exactly at the limit is still searched


def test_a_name_no_company_is_close_to_says_so():
    app, _ = make(companies=[], extract=lambda note: {**FIELDS, "street": "Race Track Rd"})
    text = seen(client_for(app).post("/search", data={"note": NOTE}).text)
    assert "No company with a name close to that was found. Check the spelling of the business's name." in text and "Which company" not in text
    # The page says what the extraction step read, the street included, so the contractor can see WHAT was searched for.
    assert 'I read that as: the business name "Invented Air Conditioning", the city "Boynton Beach", the street "Race Track Rd"' in text


def test_a_possible_match_carries_a_caution_on_the_shortlist_and_on_its_report():
    # The terminal asks "Make the report anyway?" before it reports on a Possible match. A page cannot ask, so it says this where it will be read.
    caution = "This is only a POSSIBLE match: the name is similar, and nothing else confirms it is the company you mean."
    app, _ = make(extract=lambda note: {"business_name": "Invented Air Cooling", "city": "", "street": "", "is_specific": True})
    browser = client_for(app)
    shortlist = browser.post("/search", data={"note": "invented air cooling"})
    cards = shortlist.text.split("<article>")[1:]
    assert len(cards) == 5 and all("<strong>Possible</strong>" in card and caution in card for card in cards)   # every card on this list is Possible, and each says so
    report = browser.get(re.search(r'href="(/company/[^"]+)"', shortlist.text).group(1))
    text = seen(report.text)
    assert "match level Possible" in text and text.count(caution) == 1 and text.index(caution) < text.index("found in")   # at the top, before the summary line
    strong, _ = make()
    browser = client_for(strong)
    shortlist = browser.post("/search", data={"note": NOTE})
    first_card = shortlist.text.split("<article>")[1]
    assert "<strong>Strong</strong>" in first_card and caution not in first_card      # a Strong company carries none
    assert caution not in browser.get(re.search(r'href="(/company/T26000000001[^"]+)"', shortlist.text).group(1)).text
    assert caution not in browser.get("/company/" + fx.LIEN_COMPANY).text             # and a report opened by its number claims no level at all
    # A Likely company has the same name, or is in the city given. "Nothing else confirms it" would be false there, so it carries no caution.
    mixed, _ = make(extract=lambda note: {**FIELDS, "city": "Tampa"})   # the air-conditioning company has the name and another city. The roofing company is in Tampa
    cards = {re.search(r"T\d{11}", card).group(0): card for card in client_for(mixed).post("/search", data={"note": NOTE}).text.split("<article>")[1:]}
    levels = {number: re.search(r"<strong>(Strong|Likely|Possible)</strong>", card).group(1) for number, card in cards.items()}
    assert levels[fx.LIEN_COMPANY] == "Likely" and levels[fx.INACTIVE_COMPANY] == "Likely" and list(levels.values()).count("Possible") == 3
    for number, card in cards.items():
        assert (caution in card) == (levels[number] == "Possible"), number   # on every Possible card, and on no other


def test_an_inactive_company_is_marked_beside_its_name_on_the_shortlist_and_the_words_are_said_once():
    # Working rule S10 (leg D2). On Nov 24 the first company on Andres's shortlist was inactive, and the only sign of it was the
    # last line of its reasons. The fixture's roofing company is inactive and the other four on this list are active.
    answer = client_for(make()[0]).post("/search", data={"note": NOTE})
    cards = {re.search(r"Document number (T\d{11})", card).group(1): card for card in answer.text.split("<article>")[1:]}
    assert len(cards) == 5
    inactive = cards[fx.INACTIVE_COMPANY]
    assert re.search(r'<h2><a href="/company/T26000000003\?from=[^"]+">INVENTED ROOFING CORP</a> <small>· Inactive with the state</small></h2>', inactive)   # beside the name
    assert inactive.count("Inactive with the state") == 1 and "INACTIVE" not in inactive   # said once: the words are no longer among the reasons
    assert not re.findall(r"<li[^>]*>[^<]*nactive[^<]*</li>", inactive, flags=re.IGNORECASE)
    # The report of that company keeps every fact it had (the brief: "Keep every other fact the report shows today, in the same
    # words"). The line that says how it was identified still gives its status. Round 1 of the review found my first version dropped it.
    browser = client_for(make()[0])
    link = re.search(r'href="(/company/T26000000003\?from=[^"]+)"', browser.post("/search", data={"note": NOTE}).text).group(1)
    identified = re.search(r"How this company was identified:</strong>([^<]+)</p>", browser.get(link).text).group(1)
    assert "INACTIVE with the state) · chosen by the user from a shortlist." in identified
    for number, card in cards.items():
        if number != fx.INACTIVE_COMPANY:
            assert "Inactive with the state" not in card and "<small>·" not in card and '<li class="as-recorded">ACTIVE</li>' in card, number   # an active company has no mark
    # A company with no status on record is not marked: no status is not "inactive" (CLAUDE.md rule 3).
    no_status = [replace(c, status_code=None) if c.document_number == fx.INACTIVE_COMPANY else c for c in fx.load_companies()]
    unknown = client_for(make(companies=no_status)[0]).post("/search", data={"note": NOTE}).text
    assert "Inactive with the state" not in unknown and '<li class="as-recorded">status not on record</li>' in unknown
    # A Strong company that did not fit on the list is shown under it with no link. It is marked the same way.
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    seven = [replace(base, document_number=f"T2600000010{n}", entity_name=f"INVENTED AIR {suffix}", name_key=f"INVENTED AIR {suffix}", status_code="I" if suffix == "LTD" else "A")
             for n, suffix in enumerate(("LLC", "INC", "CORP", "CO", "LTD", "LP", "PA"), start=1)]
    under = client_for(make(companies=seven, extract=lambda note: {"business_name": "Invented Air", "city": "", "street": "", "is_specific": True})[0]).post("/search", data={"note": "invented air"})
    assert "<h2>INVENTED AIR LTD <small>· Inactive with the state</small></h2>" in under.text and under.text.count("Inactive with the state") == 1


def test_a_value_is_shown_with_the_spaces_the_record_holds():
    # Thousands of companies have a city such as FORT  LAUDERDALE, with two spaces. A browser shows one, and the line that says its
    # spelling does not begin with "Fort Lauderdale" would then look false. The page keeps the record's own spacing.
    base = next(c for c in fx.load_companies() if c.document_number == fx.LIEN_COMPANY)
    app, _ = make(companies=[replace(base, principal_city="FORT  LAUDERDALE")], extract=lambda note: {**FIELDS, "city": "Fort Lauderdale"})
    answer = client_for(app).post("/search", data={"note": NOTE})
    assert '<span class="as-recorded">FORT  LAUDERDALE, FL</span>' in answer.text
    assert '<li class="as-recorded">principal city on record is FORT  LAUDERDALE, and that spelling does not begin with the city you gave</li>' in answer.text
    assert re.search(r"\.as-recorded\s*\{\s*white-space:\s*pre-wrap;", (WEB / "static" / "datum.css").read_text())
    # The report repeats that reason in the line that says how the company was identified, so that line keeps the spacing too.
    report = client_for(app).get(re.search(r'href="(/company/[^"]+)"', client_for(app).post("/search", data={"note": NOTE}).text).group(1))
    line = re.search(r'<p class="as-recorded"><strong>How this company was identified:</strong>([^<]+)</p>', report.text)
    assert line and "principal city on record is FORT  LAUDERDALE, and that spelling" in line.group(1)
    assert '<td class="as-recorded">1 INVENTED WAY, FORT  LAUDERDALE, FL 33426</td>' in report.text
    blank_city, _ = make(extract=lambda note: {**FIELDS, "city": "   "})  # a city of only spaces is no city: the exact-name company stays Strong
    assert "<strong>Strong</strong>" in client_for(blank_city).post("/search", data={"note": NOTE}).text.split("<article>")[1]


def test_two_companies_with_one_name_are_called_a_tie_on_the_shortlist_and_on_the_report():
    # Rule W7, through the web app this time.
    first = next(c for c in fx.load_companies() if c.document_number == fx.LIEN_COMPANY)
    twin = replace(next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY),
                   entity_name="INVENTED AIR CONDITIONING INC", name_key="INVENTED AIR CONDITIONING INC", principal_city="BOYNTON BEACH")
    app, _ = make(companies=[first, twin])
    browser = client_for(app)
    shortlist = browser.post("/search", data={"note": NOTE})
    text = seen(shortlist.text)
    tie = "2 companies match at the level Strong. Check which one you mean before you open a report."
    assert tie in text and text.index(tie) < text.index("INVENTED AIR CONDITIONING, LLC")   # above the list, naming the level and the count
    link = re.findall(r'href="(/company/T26000000005\?from=[^"]+)"', shortlist.text)[0]
    report = seen(browser.get(link).text)
    assert "match level Strong" in report and "1 other company matched equally well." in report
    alone, _ = make(companies=[first])
    assert "match at the level" not in client_for(alone).post("/search", data={"note": NOTE}).text


def test_strong_companies_that_did_not_fit_on_the_list_are_shown_under_it_with_their_source_and_without_a_link():
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    seven = [replace(base, document_number=f"T2600000010{n}", entity_name=f"INVENTED AIR {suffix}", name_key=f"INVENTED AIR {suffix}")
             for n, suffix in enumerate(("LLC", "INC", "CORP", "CO", "LTD", "LP", "PA"), start=1)]
    app, _ = make(extract=lambda note: {"business_name": "Invented Air", "city": "", "street": "", "is_specific": True}, companies=seven)
    browser = client_for(app)
    answer = browser.post("/search", data={"note": "invented air"})
    text = seen(answer.text)
    assert "2 more companies match at the level Strong and are not on this list." in text
    assert len(re.findall(r'href="/company/T\d{11}\?from=', answer.text)) == 5      # five can be picked
    assert "<h2>INVENTED AIR LTD</h2>" in answer.text and "<h2>INVENTED AIR CORP</h2>" in answer.text   # the two others are named, with no link
    assert text.count("Source: Florida Division of Corporations (Sunbiz) record, document number T") == 7   # and all seven cite their source
    report = seen(browser.get(re.search(r'href="(/company/[^"]+)"', answer.text).group(1)).text)
    assert "6 other companies matched equally well." in report


S12_SENTENCE = "The list is in search order. The level beside each company says how much of the record agrees with what you typed."   # typed out, not read from wording.py


def five_out_of_level_order():
    """Five invented companies whose levels come out Possible, Likely, Likely, Possible, Possible in rank order for "Acme Roofing" in Jacksonville.

    They do so under search version 1's order and under rule S2 alike, with a different company on top (tests/test_search.py has
    the same five and says why), so this fixture does not depend on which order the app uses.
    """
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    rows = (("ACME ROOFING AND SIDING INC", "TAMPA"), ("ACME ROOFERS INC", "JACKSONVILLE"), ("ACME ROOFER INC", "JACKSONVILLE"),
            ("ACME ROOFINGS", "TAMPA"), ("ACME ROOFERS OF TAMPA INC", "TAMPA"))
    return [replace(base, document_number=f"T2600000020{n}", entity_name=name, name_key=name, principal_city=city) for n, (name, city) in enumerate(rows, start=1)]


def test_a_list_with_a_lower_level_above_a_higher_one_is_in_rank_order_and_says_so_once_under_the_list():
    # Phase D rule S12 (leg D3). Until then the page put the two Likely companies on top, and this test fails on that order.
    acme = {"business_name": "Acme Roofing", "city": "Jacksonville", "street": "", "is_specific": True}
    answer = client_for(make(companies=five_out_of_level_order(), extract=lambda note: dict(acme))[0]).post("/search", data={"note": "acme roofing jacksonville"})
    cards = answer.text.split("<article>")[1:]
    assert [re.search(r"<strong>(Strong|Likely|Possible)</strong>", card).group(1) for card in cards] == ["Possible", "Likely", "Likely", "Possible", "Possible"]
    text = seen(answer.text)
    tie = "2 companies on this list match at the level Likely. Check which one you mean before you open a report."
    assert tie in text and "at the level Possible" not in text            # rule W7 reads the BEST level on the list, not the first card's
    assert text.count(S12_SENTENCE) == 1
    assert text.rindex("Source: Florida Division of Corporations") < text.index(S12_SENTENCE) < text.index("Search again")   # under the whole list
    # The report of a Likely company still counts the other Likely one, and only that one.
    browser = client_for(make(companies=five_out_of_level_order(), extract=lambda note: dict(acme))[0])
    link = re.search(r'href="(/company/T26000000202\?from=[^"]+)"', browser.post("/search", data={"note": "acme roofing jacksonville"}).text).group(1)
    assert "match level Likely" in seen(browser.get(link).text) and "1 other company on the shortlist matched equally well." in seen(browser.get(link).text)
    # A list whose levels already go from best to worst says nothing about its order: five Possible companies, and then Strong before Likely.
    all_possible = client_for(make(extract=lambda note: {"business_name": "Invented Air Cooling", "city": "", "street": "", "is_specific": True})[0])
    assert S12_SENTENCE not in all_possible.post("/search", data={"note": "invented air cooling"}).text
    in_order = [replace(c, entity_name=name, name_key=name) for c, name in zip(five_out_of_level_order()[1:3], ("ACME ROOFING LLC", "ACME ROOFERS INC"))]
    page = client_for(make(companies=in_order, extract=lambda note: dict(acme))[0]).post("/search", data={"note": "acme roofing jacksonville"}).text
    assert [re.search(r"<strong>(Strong|Likely|Possible)</strong>", card).group(1) for card in page.split("<article>")[1:]] == ["Strong", "Likely"]
    assert S12_SENTENCE not in page
    # The first card can have the best level and the list still be out of order below it: Likely, Possible, Likely. The sentence shows then too.
    below = [replace(c, entity_name=name, name_key=name, principal_city=city) for c, (name, city) in zip(five_out_of_level_order()[:3], (
        ("ACME ROOFING OF JACKSONVILLE INC", "JACKSONVILLE"), ("ACME ROOFING AND SIDING INC", "TAMPA"), ("ACME ROOFER INC", "JACKSONVILLE")))]
    page = client_for(make(companies=below, extract=lambda note: dict(acme))[0]).post("/search", data={"note": "acme roofing jacksonville"}).text
    assert [re.search(r"<strong>(Strong|Likely|Possible)</strong>", card).group(1) for card in page.split("<article>")[1:]] == ["Likely", "Possible", "Likely"]
    assert seen(page).count(S12_SENTENCE) == 1


def test_a_place_that_is_in_a_companys_name_puts_it_first_and_the_card_and_the_report_say_why():
    # Phase D rule S14 (leg D3), through the web app, on the shape of checked case 12 with invented companies. The extraction step
    # read the place as the city, and the company's principal city is Orlando. Before rule S14 the shorter namesake came first.
    in_name = "every word of the city you gave is in the company's name"   # typed out, not read from wording.py
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    rows = (("Q PIZZA WP LLC", "WINTER PARK"), ("Q PIZZA DURBIN, LLC", "SAINT JOHNS"), ("Q PIZZA LAKE BUENA VISTA LLC", "ORLANDO"))
    pizzas = [replace(base, document_number=f"T2600000030{n}", entity_name=name, name_key=name.replace(",", ""), principal_city=city) for n, (name, city) in enumerate(rows, start=1)]
    browser = client_for(make(companies=pizzas, extract=lambda note: {"business_name": "Q Pizza", "city": "Lake Buena Vista", "street": "", "is_specific": True})[0])
    answer = browser.post("/search", data={"note": "q pizza lake buena vista"})
    cards = [seen(card) for card in answer.text.split("<article>")[1:]]
    assert [re.search(r"T\d{11}", card).group(0) for card in cards] == ["T26000000303", "T26000000301", "T26000000302"]   # the company with the place in its name is first
    assert in_name in cards[0] and in_name not in cards[1] and in_name not in cards[2]
    assert "principal city on record is ORLANDO, and that spelling does not begin with the city you gave" in cards[0]   # the principal city is still said, beside it
    assert cards[0].startswith("Q PIZZA LAKE BUENA VISTA LLC Possible ·") and "This is only a POSSIBLE match" in cards[0]   # rule S4: its level did not rise
    report = seen(browser.get(re.search(r'href="(/company/T26000000303\?from=[^"]+)"', answer.text).group(1)).text)
    assert "match level Possible (" in report and f"; {in_name}; ACTIVE) · chosen by the user from a shortlist." in report   # the report's line gives the same reasons


# --- The search by address (Phase D, leg D1; working rules S5 to S8) -----------------------------------

S16_SENTENCE = "Type the business's name to look for it with the name search, which lists inactive companies too."   # typed out, not read from wording.py

BY_ADDRESS = {"business_name": "<UNKNOWN>", "city": "", "street": "8586 palm pwwy", "is_specific": False}
# What the extraction step returned for the note "8586 palm pwwy" on Nov 25, 2026: no business, and the street exactly as typed.
S8_SENTENCE = "A company's principal address is the address it gave the state, which is not always where it does business."   # typed out, not read from wording.py


def at_palm_pkwy(active=1, inactive=2, city="ORLANDO"):
    """Invented companies whose principal address is 8586 Palm Pkwy, written the three ways the state's records write such a street."""
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    spellings = ("8586 PALM PKWY", "8586 PALM PARKWAY", "8586 Palm Pkwy.")
    companies = [replace(base, document_number=f"T260000002{n:02d}", entity_name=f"INVENTED PIZZA {n} LLC", name_key=f"INVENTED PIZZA {n} LLC",
                         status_code="A", principal_address_1=spellings[n % 3], principal_city=city, principal_zip="32836") for n in range(active)]
    companies += [replace(base, document_number=f"T260000003{n:02d}", entity_name=f"INVENTED TILE {n} INC", name_key=f"INVENTED TILE {n} INC",
                          status_code="I", principal_address_1=spellings[(n + 1) % 3], principal_city=city, principal_zip="32836") for n in range(inactive)]
    return fx.load_companies() + companies


def test_an_address_alone_lists_the_one_active_company_there_and_says_two_inactive_ones_are_not_listed():
    # Working rules S5, S6 and S8, on the shape of the search that failed Andres on Nov 24. Before leg D1 this note got
    # "That describes a business but doesn't name one", because the app never read the street.
    app, handed = make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy())
    browser = client_for(app)
    answer = browser.post("/search", data={"note": "8586 palm pwwy"})
    text = seen(answer.text)
    assert answer.status_code == 200 and handed == ["8586 palm pwwy"] and "doesn't name one" not in text
    assert "Companies by principal address" in text and 'I read that as: the street "8586 palm pwwy"' in text
    assert "UNKNOWN" not in answer.text and 'the business name "' not in text   # what the reply holds as a name, when it names no business, is never shown
    links = re.findall(r'<h2><a href="/company/(T\d{11})\?from=([A-Za-z0-9_-]{16,})">([^<]+)</a></h2>', answer.text)
    assert [(number, name) for number, _, name in links] == [("T26000000200", "INVENTED PIZZA 0 LLC")]   # the ACTIVE company, and it alone
    assert "TILE" not in answer.text and "T260000003" not in answer.text   # rule S6: the two inactive companies are counted and never listed
    assert "1 active company matches." in text
    assert ("2 inactive companies also match and are not listed. "
            "Source: Florida Division of Corporations (Sunbiz) company records · fetched about 2026-10-22") in text   # the count cites the records it was made from
    assert "Document number T26000000200 · Principal address 8586 PALM PKWY, ORLANDO, FL 32836" in text   # the address as the state has it, to compare with what was typed
    # The sentence that says what was compared, typed out. Since rule S15 (leg D4) it names all twelve directions and the office
    # units, which are not compared, and says that an apartment, unit or lot number still is.
    assert 'A company matches when its principal address on record begins with the house number 8586, and every word of its street name is among the words you typed once three things are left out of both: the kind of street, such as ST or PKWY; a direction (N, S, E, W, NORTH, SOUTH, EAST, WEST, NE, NW, SE or SW); and an office unit word (STE, SUITE, BLDG, FL, FLOOR, RM or ROOM) with the one word after it, unless that word is a unit word too. A street name with no word left after that matches nothing. Punctuation counts as a space, so in STE 400-B the B is still compared, and so is a unit written as one word, such as STE200. An apartment, unit or lot on the record is compared, the word and its number, so both have to be typed too. You gave no city, so a match can be in any city.' in text
    assert "also begins with the city you gave" not in text               # no city was given, and the page says that none was compared
    assert "this principal address" not in text and "at this address" not in text   # the page says "matches", which is all the comparison shows (round 1 of the review)
    assert text.count(S8_SENTENCE) == 1                                   # rule S8: once ...
    assert text.index("INVENTED PIZZA 0 LLC") < text.index("2 inactive companies") < text.index(S8_SENTENCE) < text.index("Search again")   # ... and under the results
    assert BANNED.findall(text) == [] and "Strong" not in text and "Likely" not in text and "Possible" not in text   # rule W4, and no match level: rule S4 keeps those for names
    assert '<meta name="robots" content="noindex, nofollow">' in answer.text and '<meta name="viewport" content="width=device-width, initial-scale=1">' in answer.text
    assert app.state.search_backend.address_calls and app.state.search_backend.calls == []   # the address search ran, and the name search did not
    for word in ("8586", "palm", "pwwy"):
        assert not [link for link in re.findall(r'href="([^"]+)"', answer.text) if word in link.lower()]   # no address carries what was read from the note

    report = browser.get(f"/company/{links[0][0]}?from={links[0][1]}")
    page = seen(report.text)
    assert ('How this company was identified: from the street "8586 palm pwwy" · found by its principal address on record (the same house number, '
            "and a street name made only of words that were typed) · chosen by the user from the active companies listed.") in page
    assert "match level" not in page and "POSSIBLE" not in page and "other active compan" not in page   # no level, no caution, and nobody else was listed
    # An inactive company was counted and never listed, so the page's token says nothing about it: its report claims no address search.
    unlisted = seen(browser.get(f"/company/T26000000300?from={links[0][1]}").text)
    assert "opened by its document number, so no match level applies." in unlisted and "found by its principal address" not in unlisted


def test_several_active_companies_at_an_address_are_listed_by_document_number_and_the_report_says_how_many_others():
    app, _ = make(extract=lambda note: dict(BY_ADDRESS), companies=list(reversed(at_palm_pkwy(active=3, inactive=1))))
    browser = client_for(app)
    answer = browser.post("/search", data={"note": "8586 palm pwwy"})
    text = seen(answer.text)
    assert re.findall(r'<h2><a href="/company/(T\d{11})\?from=', answer.text) == ["T26000000200", "T26000000201", "T26000000202"]   # document-number order
    assert ("3 active companies match. They are in document-number order, which says nothing about which one you mean.") in text
    assert "1 inactive company also matches and is not listed." in text
    assert text.count("Source: Florida Division of Corporations (Sunbiz) record, document number T") == 3   # each listed company cites its own record
    second = seen(browser.get(re.findall(r'href="(/company/T26000000201\?from=[^"]+)"', answer.text)[0]).text)
    assert "2 other active companies were listed with it." in second     # rule W7: a tie is said on the report of whichever one was picked


def test_a_city_given_with_an_address_keeps_only_the_companies_in_that_city_and_the_page_says_so():
    companies = at_palm_pkwy()
    elsewhere = replace(next(c for c in at_palm_pkwy() if c.document_number == "T26000000200"), document_number="T26000000250",
                        entity_name="INVENTED GLASS OF MIAMI LLC", name_key="INVENTED GLASS OF MIAMI LLC", principal_address_1="8586 PALM AVE", principal_city="MIAMI")
    with_city, _ = make(extract=lambda note: {**BY_ADDRESS, "city": "Orlando"}, companies=companies + [elsewhere])
    text = seen(client_for(with_city).post("/search", data={"note": "8586 palm pwwy orlando"}).text)
    assert 'I read that as: the street "8586 palm pwwy", the city "Orlando"' in text
    assert "INVENTED PIZZA 0 LLC" in text and "MIAMI" not in text and "1 active company matches." in text
    assert "An apartment, unit or lot on the record is compared, the word and its number, so both have to be typed too. Its principal city on record also begins with the city you gave." in text
    no_city, _ = make(extract=lambda note: dict(BY_ADDRESS), companies=companies + [elsewhere])
    both = seen(client_for(no_city).post("/search", data={"note": "8586 palm pwwy"}).text)
    assert "2 active companies match." in both      # with no city, 8586 PALM AVE in Miami matches too ...
    assert "You gave no city, so a match can be in any city." in both               # ... and the page says why
    assert "Principal address 8586 PALM AVE, MIAMI, FL 32836" in both               # ... and its own address is shown, so the reader can tell the two apart


def test_an_address_search_that_lists_nobody_says_why_and_shows_no_company():
    nobody, _ = make(extract=lambda note: dict(BY_ADDRESS))               # no company has that address
    answer = client_for(nobody).post("/search", data={"note": "8586 palm pwwy"})
    text = seen(answer.text)
    assert answer.status_code == 200 and "/company/" not in answer.text and 'I read that as: the street "8586 palm pwwy"' in text
    assert "No company matches. A company matches when its principal address on record begins with the house number 8586, and every word of its street name is among the words you typed once three things are left out of both: the kind of street, such as ST or PKWY; a direction (N, S, E, W, NORTH, SOUTH, EAST, WEST, NE, NW, SE or SW); and an office unit word (STE, SUITE, BLDG, FL, FLOOR, RM or ROOM) with the one word after it, unless that word is a unit word too. A street name with no word left after that matches nothing. Punctuation counts as a space, so in STE 400-B the B is still compared, and so is a unit written as one word, such as STE200. An apartment, unit or lot on the record is compared, the word and its number, so both have to be typed too. You gave no city, so a match can be in any city. Check the house number and the spelling of the street's name, and add the apartment, unit or lot number if the address has one." in text   # the one description of the comparison, and what to check
    assert "add the suite" not in text.lower()                            # a suite is not compared since rule S15, so the page no longer advises adding one
    assert S8_SENTENCE not in text                                        # there are no results for it to stand under
    # With a city given, the city is one of the things compared. Companies DO have that house number and street, in Orlando, so the
    # page may not say that none has: it has to say that the city was part of the comparison (round 2 of the review).
    elsewhere, _ = make(extract=lambda note: {**BY_ADDRESS, "city": "Tampa"}, companies=at_palm_pkwy())
    answer = client_for(elsewhere).post("/search", data={"note": "8586 palm pwwy tampa"})
    text = seen(answer.text)
    assert "/company/" not in answer.text and 'I read that as: the street "8586 palm pwwy", the city "Tampa"' in text
    assert "No company matches. A company matches when its principal address on record begins with the house number 8586, and every word of its street name is among the words you typed once three things are left out of both: the kind of street, such as ST or PKWY; a direction (N, S, E, W, NORTH, SOUTH, EAST, WEST, NE, NW, SE or SW); and an office unit word (STE, SUITE, BLDG, FL, FLOOR, RM or ROOM) with the one word after it, unless that word is a unit word too. A street name with no word left after that matches nothing. Punctuation counts as a space, so in STE 400-B the B is still compared, and so is a unit written as one word, such as STE200. An apartment, unit or lot on the record is compared, the word and its number, so both have to be typed too. Its principal city on record also begins with the city you gave. Check the house number, the spelling of the street's name and the city, and add the apartment, unit or lot number if the address has one." in text
    assert "You gave no city" not in text                                 # the city was part of the comparison, and the page says so

    only_inactive, _ = make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy(active=0, inactive=2))
    answer = client_for(only_inactive).post("/search", data={"note": "8586 palm pwwy"})
    text = seen(answer.text)
    assert "/company/" not in answer.text and "TILE" not in answer.text       # nobody is listed, and nobody can be opened
    assert "No active company matches." in text and "2 inactive companies also match and are not listed." in text
    assert text.count(S8_SENTENCE) == 1

    crowded, _ = make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy(active=40, inactive=11))   # 51 companies at one address
    answer = client_for(crowded).post("/search", data={"note": "8586 palm pwwy"})
    text = seen(answer.text)
    assert "/company/" not in answer.text and "INVENTED PIZZA" not in answer.text
    assert "That house number and street name are on the records of too many companies to list them. Add the business's name." in text
    fifty, _ = make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy(active=40, inactive=10))    # exactly 50 is still listed
    assert len(re.findall(r'href="/company/T', client_for(fifty).post("/search", data={"note": "8586 palm pwwy"}).text)) == 40

    down, _ = make(extract=lambda note: dict(BY_ADDRESS), failing_database=True)
    answer = client_for(down).post("/search", data={"note": "8586 palm pwwy"})
    assert answer.status_code == 503 and "The search is unavailable right now, so no company is shown." in seen(answer.text) and "/company/" not in answer.text


def test_an_address_with_only_inactive_companies_asks_for_the_business_name_after_the_count_and_lists_none():
    # Phase D rule S16 (leg D4). Until then the page stopped at "No active company matches." and the count, with no next step, and
    # this test fails on that page. The sentence comes once, after the count, repeats no number and names no company.
    answer = client_for(make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy(active=0, inactive=2))[0]).post("/search", data={"note": "8586 palm pwwy"})
    text = seen(answer.text)
    count = "2 inactive companies also match and are not listed."
    assert text.count(S16_SENTENCE) == 1 and text.count(count) == 1 and text.count("No active company matches.") == 1
    assert text.index("No active company matches.") < text.index(count) < text.index(S16_SENTENCE) < text.index(S8_SENTENCE) < text.index("Search again")
    assert "/company/" not in answer.text and "TILE" not in answer.text and "T260000003" not in answer.text   # still none of them is listed or can be opened
    assert not re.search(r"\d", S16_SENTENCE)                                # the sentence says no number: the count is said once, above it
    # It is shown only when no active company and at least one inactive one match. Not beside an active company, not with nothing
    # inactive, and not for companies with no status on record, which are never called inactive (CLAUDE.md rule 3).
    with_active = seen(client_for(make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy(active=1, inactive=2))[0]).post("/search", data={"note": "8586 palm pwwy"}).text)
    assert "1 active company matches." in with_active and S16_SENTENCE not in with_active
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    no_status = [replace(base, document_number="T26000000401", entity_name="INVENTED GLASS LLC", name_key="INVENTED GLASS LLC", status_code=None,
                         principal_address_1="8586 PALM PKWY", principal_city="ORLANDO")]
    unknown = seen(client_for(make(extract=lambda note: dict(BY_ADDRESS), companies=fx.load_companies() + no_status)[0]).post("/search", data={"note": "8586 palm pwwy"}).text)
    assert "1 company with no status on record also matches and is not listed." in unknown and S16_SENTENCE not in unknown
    nobody = seen(client_for(make(extract=lambda note: dict(BY_ADDRESS))[0]).post("/search", data={"note": "8586 palm pwwy"}).text)
    assert S16_SENTENCE not in nobody                                     # no company matched at all: there is no inactive company to look for


def test_a_street_with_nothing_left_to_compare_matches_nothing_and_the_page_says_so_without_denying_it():
    # Round 2 of leg D4's review. Since rule S15, SOUTH is a direction, so a stored 12 SOUTH ST (an invented record) keeps no word to
    # compare, and it matches nothing. A note with a mistyped street type, "12 south stt", keeps STT and gets the address search. The
    # page's sentence for "no match" must not deny that record: it states the rule, which says a street must keep at least one word.
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    south = [replace(base, document_number="T26000000501", entity_name="INVENTED SOUTH LLC", name_key="INVENTED SOUTH LLC", status_code="A",
                     principal_address_1="12 SOUTH ST", principal_city="ORLANDO")]
    answer = client_for(make(extract=lambda note: {**BY_ADDRESS, "street": "12 south stt"}, companies=fx.load_companies() + south)[0]).post("/search", data={"note": "12 south stt"})
    text = seen(answer.text)
    assert "/company/" not in answer.text and "INVENTED SOUTH" not in answer.text   # nothing to compare: the record is not listed
    assert "No company matches. A company matches when its principal address on record begins with the house number 12," in text
    assert "A street name with no word left after that matches nothing." in text and "none has a principal address" not in text


@pytest.mark.parametrize("record,note,clause", [
    ("12 MADE UP RD STE 400-B", "12 made up rd", "Punctuation counts as a space, so in STE 400-B the B is still compared"),
    ("12 MADE UP RD STE 400-C", "12 made up rd ste 400-b", "Punctuation counts as a space, so in STE 400-B the B is still compared"),
    ("12 MADE UP RD BLDG APT 305", "12 made up rd #305", "with the one word after it, unless that word is a unit word too"),
    ("12 MADE UP RD BLDG APT 305", "12 made up rd #305", "the word and its number, so both have to be typed too"),
    ("STE 200 12 MADE UP RD", "12 made up rd", "begins with the house number 12,"),
    ("12 MADE UP RD #200", "12 made up rd suite 200", "every word of its street name is among the words you typed once three things are left out of both"),
    ("12 SOUTH ST", "12 south stt", "A street name with no word left after that matches nothing."),
])
def test_a_record_the_search_leaves_out_is_explained_by_the_page_and_never_denied(record, note, clause):
    # Three review rounds of leg D4 each found a record that a "no match" sentence described wrongly. These are all seven of them, as
    # invented records. For each, the page lists nobody, and the one description of the comparison it shows holds the clause that
    # leaves that record out. The page makes no claim of its own about what no record has.
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    there = [replace(base, document_number="T26000000601", entity_name="INVENTED CO LLC", name_key="INVENTED CO LLC", status_code="A",
                     principal_address_1=record, principal_city="ORLANDO")]
    answer = client_for(make(extract=lambda typed: {**BY_ADDRESS, "street": note}, companies=fx.load_companies() + there)[0]).post("/search", data={"note": note})
    text = seen(answer.text)
    assert "/company/" not in answer.text and "INVENTED CO LLC" not in answer.text   # the search leaves the record out
    assert text.count("No company matches. A company matches when") == 1 and clause in text
    assert "none has" not in text


def test_a_company_with_no_status_on_record_is_counted_apart_and_never_called_inactive():
    # CLAUDE.md rule 3: a gap is said and never filled in. Every company has a status today, so this is a guard, and round 1 of the
    # review found that nothing tested it.
    base = next(c for c in at_palm_pkwy() if c.document_number == "T26000000200")
    no_status = replace(base, document_number="T26000000400", entity_name="INVENTED GAP LLC", name_key="INVENTED GAP LLC", status_code=None)
    app, _ = make(extract=lambda note: dict(BY_ADDRESS), companies=at_palm_pkwy(inactive=0) + [no_status])
    answer = client_for(app).post("/search", data={"note": "8586 palm pwwy"})
    text = seen(answer.text)
    assert ("1 company with no status on record also matches and is not listed. "
            "Source: Florida Division of Corporations (Sunbiz) company records · fetched about 2026-10-22") in text
    assert "inactive" not in text and "INVENTED GAP" not in answer.text and "T26000000400" not in answer.text and "1 active company matches." in text
    alone, _ = make(extract=lambda note: dict(BY_ADDRESS), companies=[no_status])
    text = seen(client_for(alone).post("/search", data={"note": "8586 palm pwwy"}).text)
    assert "No company matches" not in text and "No active company matches." in text   # a company does match, so the page may not say that none does
    assert "1 company with no status on record also matches and is not listed." in text and text.count(S8_SENTENCE) == 1


@pytest.mark.parametrize("street", ["4th st south", "1st ave", "12 parkway", "12"])
def test_a_street_that_gives_nothing_to_look_up_asks_and_claims_no_result(street):
    # Rule S7, and round 1 of the review: "4th st south" has no house number, because 4TH is the street. "12 parkway" has a house number
    # and no street name, so nothing could be compared, and a page that said "no company matches" would report a search that never ran.
    on_fourth = replace(next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY), principal_address_1="4TH ST SOUTH")
    at_twelve = replace(on_fourth, document_number="T26000000098", principal_address_1="12 PARKWAY")
    app, _ = make(extract=lambda note: {**BY_ADDRESS, "street": street}, companies=fx.load_companies() + [replace(on_fourth, document_number="T26000000099"), at_twelve])
    answer = client_for(app).post("/search", data={"note": street})
    text = seen(answer.text)
    assert "That describes a business but doesn't name one. Add its name, or its street address beginning with the house number." in text
    assert "No company matches" not in text and "/company/" not in answer.text and app.state.search_backend.address_calls == []


def test_a_note_that_names_a_business_gets_the_name_search_even_when_its_street_has_a_house_number():
    # Working rule S5: the address search runs only when the note names no business.
    app, _ = make(extract=lambda note: {**FIELDS, "street": "8586 palm pwwy"}, companies=at_palm_pkwy())
    answer = client_for(app).post("/search", data={"note": NOTE})
    text = seen(answer.text)
    assert "Which company do you mean?" in text and "Companies by principal address" not in text
    assert app.state.search_backend.address_calls == [] and len(app.state.search_backend.calls) == 1
    assert re.findall(r'<h2><a href="/company/(T\d{11})', answer.text)[0] == fx.LIEN_COMPANY


def test_markup_in_an_address_or_in_the_street_that_was_read_is_shown_as_text_on_the_address_page():
    mark = "<i>x</i>"
    base = next(c for c in at_palm_pkwy() if c.document_number == "T26000000200")
    hostile = replace(base, entity_name="INVENTED PIZZA " + mark, principal_address_1="8586 PALM PKWY " + mark)   # its street's words are PALM, PKWY, I, X and I
    app, _ = make(extract=lambda note: {**BY_ADDRESS, "street": "8586 palm pwwy " + mark}, companies=[hostile])
    answer = client_for(app).post("/search", data={"note": "8586 palm pwwy"})
    assert "T26000000200" in answer.text and "<i>" not in answer.text and answer.text.count("&lt;i&gt;x&lt;/i&gt;") == 3   # the name, the address, and what was read


# --- The report page -----------------------------------------------------------------------------

def test_a_report_reached_from_the_shortlist_says_how_the_company_was_identified(browser):
    shortlist = browser.post("/search", data={"note": NOTE})
    link = re.search(r'href="(/company/T26000000001\?from=[^"]+)"', shortlist.text).group(1)
    answer = browser.get(link)
    text = seen(answer.text)
    assert answer.status_code == 200 and "Datum company check: INVENTED AIR CONDITIONING, LLC" in text
    assert ('How this company was identified: from the business name "Invented Air Conditioning", the city "Boynton Beach" · match level Strong (' in text
            and "· chosen by the user from a shortlist." in text)
    assert "2 flags found in 3 sources checked." in text
    for word in PRIVATE + (NOTE,):
        assert word not in answer.text


def test_a_report_opened_by_its_number_alone_claims_no_match_level(browser):
    for address in ("/company/" + fx.LIEN_COMPANY, "/company/" + fx.LIEN_COMPANY + "?from=", "/company/" + fx.LIEN_COMPANY + "?from=not-a-real-token"):
        text = seen(browser.get(address).text)
        assert "How this company was identified: opened by its document number, so no match level applies." in text and "match level Strong" not in text


@pytest.mark.parametrize("document_number", [fx.LIEN_COMPANY, fx.LICENSE_COMPANY, fx.INACTIVE_COMPANY, fx.NEW_COMPANY, fx.NO_FLAG_COMPANY, fx.GAPS_COMPANY])
def test_no_report_page_holds_a_word_that_reassures_or_judges(browser, document_number):
    # Rule W4, on the page a contractor reads. It fails on any of the eight words, on a missing sentence, and on the no-flags line beside a flag.
    answer = browser.get("/company/" + document_number)
    text = seen(answer.text)
    assert answer.status_code == 200 and BANNED.findall(text) == []
    assert text.count(W4_SENTENCE) == 1
    assert "Sourced public-record facts, not advice. Verify on the official record before relying on them." in text
    has_flags = "<h2>Flags</h2>" in answer.text
    assert ("No flags found in the sources checked." in text) == (not has_flags)
    assert "None" not in text                                             # a gap in the record is said in words, never printed as None
    assert "Sources checked" in text and "Not checked" in text and "Court cases" in text


@pytest.mark.parametrize("document_number", [fx.LIEN_COMPANY, fx.LICENSE_COMPANY, fx.INACTIVE_COMPANY, fx.NEW_COMPANY, fx.NO_FLAG_COMPANY])
def test_the_report_page_opens_with_a_summary_that_agrees_with_the_records_under_it(browser, document_number):
    # Phase D, leg D2 (working rule S9). Everything is read off the page a contractor sees: the summary at the top, and the rows below.
    answer = browser.get("/company/" + document_number)
    summary = re.search(r"<p><strong>((Active|Inactive) with the state as of Oct 7, 2026\. ([^<]+?), on record since (\d{4})\. "
                        r"(No flags found in the sources checked\.|(\d+) flags? found in 3 sources checked\.))</strong></p>\n<p>([^<]+)</p>", answer.text)
    assert summary, answer.text[:900]
    _, status, entity_type, year, count_line, count, next_paragraph = summary.groups()

    def row(label):
        return re.search(rf'<tr><th scope="row">{label}</th><td class="as-recorded">([^<]*)</td></tr>', answer.text).group(1)

    assert (status, entity_type, year) == (row("Status with the state"), row("Entity type"), row("Date on record")[:4])   # the same status, type and year as the table
    cards = answer.text.count("<article>")
    assert count_line == "No flags found in the sources checked." if cards == 0 else count == str(cards)   # the count is the number of flag cards on the page
    assert next_paragraph == W4_SENTENCE                                  # rule W4's sentence comes right after the summary line
    assert seen(answer.text).count(summary.group(1)) == 1 and answer.text.count("with the state as of") == 1   # the summary is on the page once, not a second time lower down
    assert "data published 2026-10-07</a>" in answer.text                 # the date in the summary is the record's published date, as the table has it
    text = seen(answer.text)
    order = [text.index(part) for part in (summary.group(1), "The records behind this summary", "Legal name", "Sources checked", "Not checked", "How this company was identified")]
    assert order == sorted(order)                                         # the summary first, and the details under their heading
    if cards:
        assert text.index(summary.group(1)) < text.index("Flags") < text.index("The records behind this summary")   # the flags the summary counts come before the details
    assert "<h2>The records behind this summary</h2>" in answer.text and BANNED.findall(text) == []


def test_the_report_page_states_every_company_fact_and_cites_the_company_record(browser):
    # Rule W1 on the page itself: the facts, and for the record as a whole its address to check it on and its fetch date.
    answer = browser.get("/company/" + fx.LIEN_COMPANY)
    for label, value in (("Legal name", "INVENTED AIR CONDITIONING, LLC"), ("Document number", "T26000000001"), ("Status with the state", "Active"),
                         ("Entity type", "Florida limited liability company (LLC)"),
                         ("Date on record", "2019-05-06 (may be an effective date; confirm on the official record)"),
                         ("Principal address", "1 INVENTED WAY, BOYNTON BEACH, FL 33426")):
        assert f'<tr><th scope="row">{label}</th><td class="as-recorded">{value}</td></tr>' in answer.text, label
    assert ('<tr><th scope="row">Official record</th><td><a href="https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber" rel="noopener noreferrer">'
            "Florida Division of Corporations (Sunbiz) record, document number T26000000001, data published 2026-10-07</a> · fetched about 2026-10-22</td></tr>") in answer.text
    assert "Report built 2026-11-24" in seen(answer.text)                 # the day the app was told is today, not the day the test runs
    checked = re.findall(r'<li>[^<]+ Source: <a href="(https://[^"]+)" rel="noopener noreferrer">[^<]+</a> · (fetched (?:about )?\d{4}-\d{2}-\d{2})</li>', answer.text)
    assert checked == [("https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber", "fetched about 2026-10-22"),
                       ("https://dos.fl.gov/sunbiz/search/", "fetched 2026-11-18"),
                       ("https://www.myfloridalicense.com/portalsearches/VerifyLicensee", "fetched about 2026-11-12")]   # each checked source: its link and its fetch date
    shortlist = browser.post("/search", data={"note": NOTE})
    assert shortlist.text.count('<a href="https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber" rel="noopener noreferrer">Florida Division') == 5


def test_every_flag_on_the_page_carries_its_caveat_word_for_word(browser):
    lien = seen(browser.get("/company/" + fx.LIEN_COMPANY).text)
    assert lien.count("Open or closed is read from the state's federal lien files published through 2026-11-16. A release filed after that date "
                      "is not reflected. The state's files carry no dollar amount.") == 2      # once per lien
    inactive = browser.get("/company/" + fx.INACTIVE_COMPANY).text.replace("&#39;", "'")
    assert "<li>Data as of the snapshot date; changes since then aren't covered until the events file is loaded</li>" in inactive
    assert "<li>May be an effective date</li>" in browser.get("/company/" + fx.NEW_COMPANY).text
    license_page = seen(browser.get("/company/" + fx.LICENSE_COMPANY).text)
    assert "A license is held by a person who qualifies the business; this line is about the license, not the person." in license_page


def test_the_lien_report_shows_each_lien_with_its_own_source_and_fetch_date(browser):
    answer = browser.get("/company/" + fx.LIEN_COMPANY)
    text = seen(answer.text)
    assert "<h3>Florida Department of State federal lien filing 26FLR9900001</h3>" in answer.text
    assert "Date on the record: 2026-11-16" in text and "Status: closed. Certificate of release filed 2026-11-16." in text
    assert ('Source: <a href="https://dos.fl.gov/sunbiz/search/" rel="noopener noreferrer">Florida Department of State federal lien filing 26FLR9900001</a> · fetched 2026-11-18'
            in answer.text)
    assert "Florida Department of State federal lien filing 19FLR9900002</a> · fetched about 2026-11-18" in answer.text   # an estimated fetch time says "about" (rule W1)
    inactive = browser.get("/company/" + fx.INACTIVE_COMPANY)
    assert "<h3>Inactive with the state</h3>" in inactive.text and "1 flag found in 3 sources checked." in seen(inactive.text)
    assert "<li>Inactive with the Florida Division of Corporations</li>" in inactive.text
    assert "On record since 2026-06-15" in seen(browser.get("/company/" + fx.NEW_COMPANY).text)


def test_every_checked_source_and_every_unchecked_one_is_on_the_page(browser):
    answer = browser.get("/company/" + fx.NO_FLAG_COMPANY)
    text = seen(answer.text)
    for label in ("Florida Division of Corporations company record (Sunbiz): data through 2026-10-07.",
                  "Federal tax liens filed with the Florida Department of State: data through 2026-11-16.",
                  "Florida DBPR construction contractor licenses: data through 2026-11-10."):
        assert label in text
    for item in ("Florida DBPR discipline records against construction license holders", "Duval County recorded liens, tax warrants and judgments") + wording.NOT_CHECKED_ALWAYS:
        assert f"<li>{item}</li>" in answer.text.replace("&#39;", "'")
    assert text.index("Sources checked") < text.index("Not checked") < text.index("How this company was identified")


def test_a_company_name_that_holds_markup_is_shown_as_text_and_never_as_markup():
    hostile = '<script>alert("x")</script> & <b>INVENTED</b> CO LLC'
    company = replace(next(c for c in fx.load_companies() if c.document_number == fx.LIEN_COMPANY), entity_name=hostile)
    app, _ = make(companies=[company])
    browser = client_for(app)
    for answer in (browser.post("/search", data={"note": NOTE}), browser.get("/company/" + fx.LIEN_COMPANY)):
        assert "<script>" not in answer.text and "<b>INVENTED</b>" not in answer.text
        assert "&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt; &amp; &lt;b&gt;INVENTED&lt;/b&gt; CO LLC" in answer.text
        assert hostile in seen(answer.text)                               # a person still reads the name exactly as the state has it


def test_markup_in_any_value_a_page_shows_is_escaped_and_no_template_can_switch_that_off():
    # Every place a page prints data, not only the company's name: what the extraction step read, a city, a citation, a status note.
    mark = "<i>x</i>"
    base = next(c for c in fx.load_companies() if c.document_number == fx.LIEN_COMPANY)
    company = replace(base, principal_city="BOYNTON" + mark, principal_address_1="1 INVENTED WAY" + mark)
    flags = [replace(row, citation=row.citation + mark, status_note="Note" + mark, caveat=row.caveat + mark)
             for row in fx.load_flags() if row.document_number == fx.LIEN_COMPANY]
    seven = [replace(base, document_number=f"T2600000010{n}", entity_name=f"INVENTED AIR{mark} {suffix}", name_key=f"INVENTED AIR {suffix}")
             for n, suffix in enumerate(("LLC", "INC", "CORP", "CO", "LTD", "LP", "PA"), start=1)]   # two of these land UNDER the list
    app, _ = make(companies=[company], flags=flags, extract=lambda note: {**FIELDS, "business_name": "Invented" + mark + " Air Conditioning", "street": "Bay" + mark})
    browser = client_for(app)
    shortlist = browser.post("/search", data={"note": NOTE})
    report = browser.get(re.search(r'href="(/company/[^"]+)"', shortlist.text).group(1))
    under, _ = make(companies=seven, extract=lambda note: {"business_name": "Invented Air", "city": "", "street": "", "is_specific": True})
    under_the_list = client_for(under).post("/search", data={"note": "invented air"})
    for answer, times in ((shortlist, 4), (report, 9), (under_the_list, 7)):
        assert "<i>" not in answer.text and answer.text.count("&lt;i&gt;x&lt;/i&gt;") >= times, (answer.url, answer.text.count("&lt;i&gt;x&lt;/i&gt;"))
    for path in sorted((WEB / "templates").glob("*.html")):               # and no template may opt out of escaping, for any value
        text = path.read_text()
        assert "|safe" not in text.replace(" ", "") and "autoescape" not in text and "Markup" not in text, path.name


@pytest.mark.parametrize("address", ["/company/nonsense", "/company/T26000000099", "/company/t26000000001", "/company/T26000000001%27%20or%201=1",
                                     "/company/%3Cscript%3Ealert(1)%3C%2Fscript%3E", "/company/..%2F..%2Fetc", "/no-such-page", "/company/"])
def test_an_address_that_names_no_company_gets_a_plain_404_that_repeats_nothing(browser, address):
    answer = browser.get(address)
    assert answer.status_code == 404 and seen(answer.text) == "Datum Not found Nothing was found at this address. Search again"
    assert "script" not in answer.text.lower().replace('<meta name="robots"', "") and "nonsense" not in answer.text and "T26000000099" not in answer.text


def test_the_search_address_takes_only_a_post(browser):
    answer = browser.get("/search?note=jane+doe")                         # a note in an address would land in a history and a log
    assert answer.status_code == 405 and "jane" not in answer.text and "Nothing was found at this address." in seen(answer.text)


# --- The token that links a shortlist to a report ---------------------------------------------------

def test_a_shortlists_token_is_forgotten_after_an_hour_and_the_oldest_goes_first():
    now = [1000.0]
    picks = Picks(keep=2, seconds=3600, clock=lambda: now[0])
    how = fx.builder and __import__("datum.models", fromlist=["Identification"]).Identification(business_name="Acme", level="Strong", evidence=("ACTIVE",))
    first = picks.put({"T1": how})
    assert picks.get(first, "T1") == how and picks.get(first, "T2") is None and picks.get(None, "T1") is None and picks.get("unknown", "T1") is None
    now[0] += 3600
    assert picks.get(first, "T1") == how                                  # exactly an hour old: still there
    now[0] += 1
    assert picks.get(first, "T1") is None and first not in picks.entries  # an hour and a second later it is gone
    second, third, fourth = picks.put({"T1": how}), picks.put({"T1": how}), picks.put({"T1": how})
    assert picks.get(second, "T1") is None and picks.get(third, "T1") == how and picks.get(fourth, "T1") == how   # only the newest two are kept
    assert len({first, second, third, fourth}) == 4 and all(len(token) >= 16 for token in (first, second, third, fourth))


def test_an_old_shortlist_is_forgotten_even_when_nobody_asks_for_it_again():
    # The review found that an entry was only removed when its own token was looked up. One that nobody reopened stayed for as long as
    # the app ran, while the docstring and question Q44 said "at most an hour".
    now = [1000.0]
    picks = Picks(clock=lambda: now[0])
    how = __import__("datum.models", fromlist=["Identification"]).Identification(business_name="Acme", level="Strong", evidence=("ACTIVE",))
    old = picks.put({"T1": how})
    now[0] += 3601
    newer = picks.put({"T2": how})                                        # somebody else searches. Nobody has asked for the old token
    assert old not in picks.entries and list(picks.entries) == [newer]
    now[0] += 3601
    assert picks.get("some-other-token", "T9") is None and picks.entries == {}   # a lookup of any token forgets the old ones too


def test_a_token_from_one_shortlist_says_nothing_about_a_company_that_was_not_on_it(browser):
    shortlist = browser.post("/search", data={"note": NOTE})
    token = re.search(r"\?from=([A-Za-z0-9_-]+)", shortlist.text).group(1)
    off_the_list = [c.document_number for c in fx.load_companies() if c.document_number not in shortlist.text]
    assert len(off_the_list) == 1                                         # six invented companies, five on the list
    other = seen(browser.get(f"/company/{off_the_list[0]}?from={token}").text)
    assert "opened by its document number, so no match level applies." in other and "match level" not in other.replace("no match level applies", "")


# --- A phone, and the files the pages load ----------------------------------------------------------

def test_every_page_has_a_viewport_tag_and_loads_only_the_apps_own_style_sheets(browser):
    pages = [browser.get("/"), browser.post("/search", data={"note": NOTE}), browser.get("/company/" + fx.LIEN_COMPANY), browser.get("/company/nonsense")]
    for answer in pages:
        assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in answer.text
        assert re.findall(r'<link rel="stylesheet" href="([^"]+)">', answer.text) == ["/static/pico.min.css", "/static/datum.css"]
        assert "<script" not in answer.text and "http://" not in answer.text.replace("http://www.w3.org", "")   # no script, and nothing loaded from elsewhere
        outside = [link for link in re.findall(r'(?:src|href)="(https?://[^"]+)"', answer.text)]
        assert all(link.startswith(("https://search.sunbiz.org/", "https://dos.fl.gov/", "https://www.myfloridalicense.com/")) for link in outside)   # only links to the sources


def test_nothing_of_datums_own_sets_a_width_wider_than_a_phone():
    # Acceptance test A11: usable at 390 pixels. Pico's own file is left alone: its wide rules sit inside rules for wide screens.
    own = [WEB / "static" / "datum.css"] + sorted((WEB / "templates").glob("*.html"))
    assert len(own) == 10                                                 # the style sheet and nine templates, two of them for the address results (leg D1)
    for path in own:
        text = path.read_text()
        widths = [int(number) for number in re.findall(r"width\s*[:=]\s*[\"']?(\d+)\s*px", text)]
        assert all(width <= 390 for width in widths), (path.name, widths)
        other_units = re.findall(r"width\s*:\s*[\d.]+\s*(?:rem|em|vw|ch|pt|cm|in)\b", text)   # 40rem is about 640 pixels: a width in any unit but % is refused
        assert other_units == [] and "min-width" not in text, (path.name, other_units)
        assert "style=" not in text and "<style" not in text              # no inline style: the page's rules live in the two files, as the policy header requires


def test_the_templates_hold_no_sentence_of_their_own():
    # Every sentence on a page comes from wording.py or from the data. What is left of a template once its tags are removed must be marks only.
    for path in sorted((WEB / "templates").glob("*.html")):
        text = path.read_text()
        text = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", " ", text, flags=re.DOTALL)   # Jinja's own tags
        text = re.sub(r"<[^>]+>", " ", text)                                # HTML tags
        words = re.findall(r"[A-Za-z]{2,}", text)
        assert words == [], (path.name, words)
        # A sentence can also hide inside a tag, in an attribute a person reads or hears. None of the templates may have one.
        spoken = re.findall(r"\b(placeholder|title|alt|aria-label|aria-description|value|label)\s*=", path.read_text())
        assert spoken == [], (path.name, spoken)


def test_the_style_sheets_are_served_and_pico_is_the_file_the_readme_describes(browser):
    pico = browser.get("/static/pico.min.css")
    assert pico.status_code == 200 and pico.headers["content-type"].startswith("text/css") and "Pico CSS" in pico.text[:200] and "v2.1.1" in pico.text[:200]
    checksum = hashlib.sha256((WEB / "static" / "pico.min.css").read_bytes()).hexdigest()
    readme = (WEB / "static" / "README.md").read_text()
    assert checksum in readme and "2.1.1" in readme and "MIT License" in (WEB / "static" / "PICO_LICENSE.md").read_text()
    assert re.findall(r"url\((?!\"data:)", pico.text) == []                # the file calls no other address: every url() in it is a picture written into the file
    assert browser.get("/static/datum.css").status_code == 200
