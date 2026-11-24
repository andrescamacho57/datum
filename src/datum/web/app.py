"""app.py: the web app a contractor uses on a phone (Phase C, leg C4).

    GET  /                           the search box
    POST /search                     the note ─▶ extract fields ─▶ shortlist   (or: ask for a business name, and show no company)
    GET  /company/{document_number}  the report for one company
    GET  /healthz                    "ok", and nothing else
    GET  /robots.txt                 tells search engines to stay out
    GET  /static/...                 the two style sheets

The app is FastAPI (a Python web framework) with pages rendered on the server from Jinja
templates, styled by Pico CSS (decision d20). There is no JavaScript at all.

Run it from ~/datum with the virtual environment active and Postgres running:
    PYTHONPATH=src uvicorn datum.web.app:app --host 127.0.0.1
Uvicorn is the program that serves a FastAPI app. PYTHONPATH=src tells Python where the
`datum` package lives. The app needs two settings in the environment: APP_ACCESS_CODE (the
code a visitor must give) and ANTHROPIC_API_KEY (for the extraction step).

Four rules shape this file (docs/prompts/florida_master.md, section 6):
  W6  The typed note is used for one extraction call and then dropped. It arrives by POST,
      so it is never part of an address, a browser history or an access log. This file
      never logs it, never stores it and never shows it back. When the extraction step
      fails, only the error's class name is logged, because an error's message can quote
      what it was given.
  W7  A tie is said out loud, on the shortlist and on the report of the company picked.
  W8  The app is private and fails closed. Every address except /healthz needs the access
      code. The app refuses to start without one. Search engines are told not to index it
      in three places: a meta tag on every page, a header on every answer, and /robots.txt.
      A request that does not come from this machine is refused.
  W1  Everything a page states about a company is a Fact, with its source and fetch date.

Everything the app depends on is PASSED IN to create_app(): the extraction step, and a
function that opens the two backends. That is called dependency injection, and it is why
every test runs with stand-ins and no network (CLAUDE.md rule 4).

Every sentence a page shows is in datum.wording. The templates only lay out.
"""

import base64                               # decodes the "Authorization: Basic ..." header
import logging                              # the app's log. It never receives the note
import secrets                              # compare_digest (a comparison that takes the same time for any input) and random tokens
import threading                            # a lock, because requests are answered on several threads
import time                                 # a clock for forgetting old shortlists
from collections import OrderedDict         # a dict that remembers the order things were added in, to drop the oldest first
from collections.abc import Callable        # the types of the functions passed in
from contextlib import AbstractContextManager   # the type of "something you open with `with`"
from datetime import date                   # the day a report is built
from pathlib import Path                    # where the templates and the style sheets are

from fastapi import FastAPI, Form, Request                    # the app, a form field, and the incoming request
from fastapi.responses import PlainTextResponse, Response      # answers that are plain text
from fastapi.staticfiles import StaticFiles                    # serves the files in static/
from fastapi.templating import Jinja2Templates                 # renders the HTML templates, with auto-escaping on
from starlette.exceptions import HTTPException as StarletteHTTPException   # what the framework raises for an unknown address

from datum import wording
from datum.models import Identification
from datum.report_builder import CompanyNotFound, ReportBackend, ReportBuilder, candidate_for_page
from datum.search import SearchBackend, evidence, search_pool, shortlist

HERE = Path(__file__).resolve().parent                     # src/datum/web/
MAX_NOTE = 500                                              # a note longer than this is not sent to the extraction step
LOOPBACK = {"127.0.0.1", "::1"}                             # the two addresses that mean "this machine itself"
NO_INDEX = "noindex, nofollow"                              # what search engines are told, in the header and in the meta tag
SECURITY_HEADERS = {
    "X-Robots-Tag": NO_INDEX,                               # rule W8: on EVERY answer, the 401 included, so a crawler that never signs in still sees it
    "Cache-Control": "no-store",                            # a shortlist or a report is not kept by the browser or by anything between
    "Referrer-Policy": "no-referrer",                       # a link to a source's site does not tell that site which page it came from
    "X-Content-Type-Options": "nosniff",                    # the browser must not guess a file's type
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
    # Content-Security-Policy tells the browser what a page may load: the two style sheets from
    # this app, the small pictures Pico keeps inside its own file, and nothing else. No script
    # can run, from anywhere, because the app has none.
}
log = logging.getLogger("datum.web")

OpenBackends = Callable[[], AbstractContextManager[tuple[SearchBackend, ReportBackend]]]
# "A function that, called with nothing, gives something to open with `with`, which then hands
# over the search backend and the report backend." The real one opens a Postgres connection
# for one request and closes it afterwards. A test's one hands over two fakes.


class Picks:
    """Remembers, for a short while, how each company on a shortlist was identified.

    Why it exists: the shortlist is the answer to a POST, and the report is a GET of
    /company/{document_number}. The report has to say how the company was identified (the
    extracted fields, the level, the evidence, the tie), and none of that may travel in the
    address, where a browser history or a log would keep it. So the shortlist page carries a
    random token, and this object keeps what the token stands for, in memory only.

    It holds EXTRACTED fields, never the note. It forgets an entry after an hour, and keeps
    at most 200 shortlists. A report opened with no token, or with one that was forgotten,
    says it was opened by its document number.
    """

    def __init__(self, keep: int = 200, seconds: float = 3600, clock: Callable[[], float] = time.monotonic):
        self.keep, self.seconds, self.clock = keep, seconds, clock
        self.entries: OrderedDict[str, tuple[float, dict[str, Identification]]] = OrderedDict()
        self.lock = threading.Lock()        # one thread at a time may change the entries

    def put(self, identifications: dict[str, Identification]) -> str:
        """Keep one shortlist's identifications and return the token that stands for them."""
        token = secrets.token_urlsafe(16)   # 16 random bytes as text: it cannot be guessed, and it says nothing about the search
        with self.lock:
            self.entries[token] = (self.clock(), identifications)
            while len(self.entries) > self.keep:
                self.entries.popitem(last=False)   # drop the oldest
        return token

    def get(self, token: str | None, document_number: str) -> Identification | None:
        """How this company was identified on the shortlist the token stands for, or None."""
        if not token:
            return None
        with self.lock:
            entry = self.entries.get(token)
            if entry is None:
                return None
            kept_at, identifications = entry
            if self.clock() - kept_at > self.seconds:
                del self.entries[token]     # too old: forget it
                return None
            return identifications.get(document_number)


def code_given(header: str | None) -> str | None:
    """The password part of an "Authorization: Basic ..." header, or None when there is no readable one."""
    if not header or not header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header[len("Basic "):], validate=True).decode("utf-8")   # "name:password"
    except ValueError:                      # not base64, or not text
        return None
    _, colon, password = decoded.partition(":")
    return password if colon else None


def create_app(access_code: str, extract: Callable[[str], dict], open_backends: OpenBackends,
               today: Callable[[], date] = date.today, local_only: bool = True) -> FastAPI:
    """Build the app. It refuses to be built without an access code (rule W8: a forgotten setting locks the app, it does not publish it)."""
    if not access_code:
        raise RuntimeError("APP_ACCESS_CODE is not set, so the app will not start. Set it and start again.")
    expected = access_code.encode("utf-8")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)   # no automatic pages that describe the app
    templates = Jinja2Templates(directory=str(HERE / "templates"))   # auto-escaping is ON for .html: a company name can never become markup
    picks = Picks()

    def page(request: Request, name: str, status: int = 200, **context) -> Response:
        """Render one template. Every template gets the wording module as `w`, and holds no sentence of its own."""
        return templates.TemplateResponse(request, name, {"w": wording, "robots": NO_INDEX, **context}, status_code=status)

    @app.middleware("http")
    async def gate(request: Request, call_next):
        """Runs around every request: the door (rule W8), and the headers on every answer."""
        client = request.client.host if request.client else ""
        if local_only and client not in LOOPBACK:                  # not this machine: refused, before anything else is looked at
            answer: Response = PlainTextResponse("", status_code=403)
        elif request.url.path == "/healthz":                       # the one address that needs no code
            answer = await call_next(request)
        else:
            given = code_given(request.headers.get("authorization"))
            if given is None or not secrets.compare_digest(given.encode("utf-8"), expected):
                # compare_digest takes the same time whether the first character is wrong or the
                # last, so the time an answer takes tells a guesser nothing.
                answer = PlainTextResponse("", status_code=401, headers={"WWW-Authenticate": 'Basic realm="Datum", charset="UTF-8"'})
            else:
                answer = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            answer.headers[name] = value
        return answer

    @app.exception_handler(StarletteHTTPException)
    async def plain_error(request: Request, error: StarletteHTTPException):
        """An unknown address, or a method an address does not take: one plain page that repeats nothing that was typed."""
        status = error.status_code if error.status_code in (404, 405) else 404
        return page(request, "message.html", status=status, heading=wording.NOT_FOUND_HEADING, message=wording.NOT_FOUND, form=False)

    @app.get("/healthz")
    def healthz():
        return PlainTextResponse("ok")

    @app.get("/robots.txt")
    def robots():
        return PlainTextResponse("User-agent: *\nDisallow: /\n")

    @app.get("/")
    def index(request: Request):
        return page(request, "index.html")

    @app.post("/search")
    def search(request: Request, note: str = Form("")):
        """The note comes in the BODY of a POST. From here it goes to the extraction step and nowhere else."""
        note = note.strip()
        if not note:
            return page(request, "message.html", heading=wording.SEARCH_HEADING, message=wording.NOTE_EMPTY, form=True)
        if len(note) > MAX_NOTE:
            return page(request, "message.html", heading=wording.SEARCH_HEADING, message=wording.NOTE_TOO_LONG, form=True)
        try:
            fields = extract(note)          # the ONLY use of the note
            business_name, city, street = fields["business_name"], fields["city"] or "", fields["street"] or ""
            is_specific = fields["is_specific"]
        except Exception as error:          # the API is down, the key is wrong, the reply is malformed
            log.warning("the extraction step failed: %s", type(error).__name__)   # the class name only. The message could quote the note
            return page(request, "message.html", status=503, heading=wording.SEARCH_HEADING, message=wording.SEARCH_UNAVAILABLE, form=True)
        if not is_specific:                 # the note names no business: ask, and show no company at all (acceptance test A2)
            return page(request, "message.html", heading=wording.SEARCH_HEADING, message=wording.ASK_FOR_A_BUSINESS_ON_A_PAGE, form=True)
        try:
            with open_backends() as (search_backend, _):
                short = shortlist(search_pool(search_backend, business_name, city), city_given=bool(city))
        except Exception as error:          # the database cannot be reached
            log.warning("the search failed: %s", type(error).__name__)
            return page(request, "message.html", status=503, heading=wording.SEARCH_HEADING, message=wording.SEARCH_UNAVAILABLE, form=True)
        read_as = wording.READ_AS.format(fields=", ".join(
            part for part in (wording.FIELD_BUSINESS_NAME.format(value=business_name),
                              wording.FIELD_CITY.format(value=city) if city else "",
                              wording.FIELD_STREET.format(value=street) if street else "") if part))
        if not short.candidates:
            return page(request, "message.html", heading=wording.SEARCH_HEADING, message=wording.NO_COMPANY_FOUND, read_as=read_as, form=True)

        identifications = {}
        for level, found in zip(short.levels, short.candidates):
            same = short.tied_at_top if level == short.top_level else short.levels.count(level)   # the rule of report.others_at_the_same_level
            identifications[found.company.document_number] = Identification(
                business_name=business_name, city=city, street=street, level=level,
                evidence=tuple(evidence(found, short.city_given)), tied_others=same - 1,
            )
        return page(
            request, "shortlist.html", read_as=read_as, token=picks.put(identifications),
            candidates=[candidate_for_page(found, level, short.city_given) for level, found in zip(short.levels, short.candidates)],
            tie=wording.SHORTLIST_TIE if short.tied_at_top > 1 else "",
            not_shown_line=wording.not_shown_text(short.tied_not_shown),
            not_shown=[candidate_for_page(found, "Strong", short.city_given) for found in short.not_shown],   # only a Strong candidate is ever in not_shown
        )

    @app.get("/company/{document_number}")
    def company(request: Request, document_number: str):
        """The report for one company. The `from` part of the address is a random token from a shortlist, or absent."""
        identification = picks.get(request.query_params.get("from"), document_number)
        try:
            with open_backends() as (_, report_backend):
                report = ReportBuilder(report_backend, today).build(document_number, identification)
        except CompanyNotFound:             # not the shape of a document number, or no such company: a plain 404
            return page(request, "message.html", status=404, heading=wording.NOT_FOUND_HEADING, message=wording.NOT_FOUND, form=False)
        except Exception as error:          # the database cannot be reached, or no source may be shown
            log.warning("the report failed: %s", type(error).__name__)
            return page(request, "message.html", status=503, heading=wording.SEARCH_HEADING, message=wording.REPORT_UNAVAILABLE, form=False)
        return page(request, "report.html", report=report, day=wording.day_text)

    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
    return app


def other_machines_allowed(setting: str | None) -> bool:
    """True only when the setting is exactly "yes". Anything else, a typing mistake included, keeps the app to this machine (rule W8: it fails closed)."""
    return setting == "yes"


def create_app_from_environment() -> FastAPI:
    """The real app: the Claude API for the extraction step, Postgres for the two backends, the access code from the environment.

    One more setting, for the day Andres opens the app on his phone: APP_ALLOW_OTHER_MACHINES.
    Unset, the app answers this Mac only. Set to exactly "yes", it also answers other machines,
    and uvicorn then has to be started with --host 0.0.0.0 as well. The access code still
    guards every page. Over plain http on a home network the code travels unencrypted, which is
    acceptable for a few minutes of testing and is not a way to host the app.
    """
    import os                               # reads APP_ACCESS_CODE and the optional DATUM_PG_DSN
    from contextlib import contextmanager   # turns a function with one `yield` into something to open with `with`

    import anthropic                        # the Claude API client
    import psycopg                          # the Postgres driver

    from datum.extract import extract_fields   # importing it loads the local secrets file into the environment, so it comes BEFORE the code is read
    from datum.report_builder import PostgresReportBackend
    from datum.search import PostgresBackend

    access_code = os.environ.get("APP_ACCESS_CODE", "")
    dsn = os.environ.get("DATUM_PG_DSN", "dbname=datum_dev")
    claude = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY

    @contextmanager
    def open_backends():
        with psycopg.connect(dsn) as conn:  # one connection per request, closed when the request is answered
            yield PostgresBackend(conn), PostgresReportBackend(conn)

    local_only = not other_machines_allowed(os.environ.get("APP_ALLOW_OTHER_MACHINES"))
    return create_app(access_code, lambda note: extract_fields(claude, note), open_backends, local_only=local_only)


_app: FastAPI | None = None                 # the real app, built the first time something asks for it


def __getattr__(name: str):
    """Python calls this when code asks this module for a name it does not have.

    `uvicorn datum.web.app:app` asks for `app`. Building it only then, and not when the file
    is imported, means a test can import create_app without an access code or an API key,
    while the real start still fails at once when APP_ACCESS_CODE is missing.
    """
    global _app
    if name == "app":
        if _app is None:
            _app = create_app_from_environment()
        return _app
    raise AttributeError(name)
