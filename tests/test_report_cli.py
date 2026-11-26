"""test_report_cli.py: offline tests for src/datum/report.py, the terminal command.

The command is a thin wrapper, so what is tested here is the conversation: what it asks,
what it prints, what it saves, and above all what it must never print or save. The
extraction step, the search and the report data are all fakes that are passed in, so no
API key, no database and no keyboard are needed.

Run from ~/datum:  pytest
"""

import ast                                  # parses source code into its structure, without running it
import inspect                              # reads the source of the module under test
import re                                   # the search for the words rule W4 bans
from pathlib import Path                    # the path of extract.py, which one test reads as text
from dataclasses import replace             # a copy of a frozen dataclass with one field changed

import pytest                               # the test runner; parametrize runs one test body over several cases

import report_fixtures as fx                # tests/report_fixtures.py: the fixture rows as objects
from datum import report, wording
from datum.report_builder import FakeReportBackend
from datum.search import FakeBackend

NOTE = "invented air conditioning boynton beach, ask for the owner Jane Q Doe, cell 904-555-0100"
PRIVATE = ("Jane", "Doe", "904-555-0100", "ask for the owner", "cell")   # words of the note that the extraction step leaves out
FIELDS = {"business_name": "Invented Air Conditioning", "city": "Boynton Beach", "street": "", "is_specific": True}


class Talk:
    """Plays the user: it answers each question from a script and keeps everything that was asked and printed."""

    def __init__(self, answers):
        self.answers, self.asked, self.said = list(answers), [], []

    def ask(self, prompt):
        self.asked.append(prompt)
        return self.answers.pop(0)          # running out of answers is an error: the command asked more than the test expected

    def say(self, text):
        self.said.append(str(text))

    @property
    def everything(self):
        return "\n".join(self.asked + self.said)


def run(talk, tmp_path, note=NOTE, fields=FIELDS, companies=None, extract=None):
    companies = fx.load_companies() if companies is None else companies
    return report.run(
        note, extract or (lambda text: dict(fields)), FakeBackend(companies), FakeReportBackend(companies, fx.load_flags(), fx.load_sources()),
        ask=talk.ask, say=talk.say, today=lambda: fx.BUILT_ON, reports_dir=tmp_path,
    )


def test_the_typed_note_is_never_printed_back_and_never_saved(tmp_path):
    # The old report.py wrote: How this company was identified: from the note "<the whole note>". The owner's name went into the file.
    talk = Talk(["1"])
    path = run(talk, tmp_path)
    saved = path.read_text()
    assert path == tmp_path / "T26000000001_20261124.md" and "INVENTED AIR CONDITIONING, LLC" in saved
    for word in PRIVATE + (NOTE,):
        assert word not in saved and word not in talk.everything, word
    assert 'from the business name "Invented Air Conditioning", the city "Boynton Beach"' in saved   # the EXTRACTED fields are what is shown
    assert 'I read that as: the business name "Invented Air Conditioning", the city "Boynton Beach"' in talk.everything


def test_the_note_reaches_the_extraction_step_and_nothing_else(tmp_path):
    seen = []

    def extract(text):
        seen.append(text)
        return dict(FIELDS)

    run(Talk(["1"]), tmp_path, extract=extract)
    assert seen == [NOTE]                                                 # one call, with the note as typed


def test_a_vague_note_asks_for_a_name_or_an_address_and_shows_no_company(tmp_path):
    # Acceptance test A2. The old prompt also asked for "an owner's name" (rule W6). Since leg D4 the question is the web page's own
    # (rule S18): it asks for what the two searches use, and no longer for "a street or a city".
    talk = Talk([""])                                                    # Enter alone: nothing to add
    vague = {"business_name": "pool service", "city": "", "street": "Race Track Rd", "is_specific": False}
    assert run(talk, tmp_path, note="the pool guy off race track rd", fields=vague) is None
    assert talk.asked == ["That describes a business but doesn't name one. Add its name, or its street address beginning with the house number. (press Enter if you don't know): "]
    assert "INVENTED" not in talk.everything and list(tmp_path.iterdir()) == []   # no company was shown and no report was written
    assert talk.said[-1].strip() == wording.GIVING_UP


def test_nothing_the_command_can_say_asks_for_an_owner():
    constants = [value for name, value in vars(wording).items() if name.isupper() and isinstance(value, str)]
    assert all("owner" not in text.lower() for text in constants)
    code_lines = [line.split("#")[0] for line in inspect.getsource(report).split('"""')[2].splitlines()]   # the code after the module's docstring, comments cut off
    assert all("owner" not in line.lower() for line in code_lines)


def test_two_companies_with_the_same_name_are_called_a_tie_on_the_shortlist_and_on_the_report(tmp_path):
    # The old report.py wrote "match level Strong" for a company that had tied with another (rule W7).
    first = next(c for c in fx.load_companies() if c.document_number == fx.LIEN_COMPANY)
    twin = replace(next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY),
                   entity_name="INVENTED AIR CONDITIONING INC", name_key="INVENTED AIR CONDITIONING INC", principal_city="BOYNTON BEACH")
    talk = Talk(["2"])
    path = run(talk, tmp_path, companies=[first, twin])
    tie = "2 companies match at the level Strong. Check which one you mean before you open a report.\n"
    assert tie in talk.said and talk.said.index(tie) < next(i for i, line in enumerate(talk.said) if line.startswith("1. "))   # said ABOVE the list
    assert path.name.startswith(fx.NO_FLAG_COMPANY) and "match level Strong" in path.read_text()
    assert "1 other company matched equally well." in path.read_text()
    alone = Talk(["1"])
    assert "matched equally well" not in run(alone, tmp_path, companies=[first]).read_text() and "match at the level" not in alone.everything


def test_a_same_name_company_that_did_not_fit_on_the_list_is_named_and_counted(tmp_path):
    # Seven companies share the name once the legal suffix is ignored. Five fit on the list, and the two with the longest suffixes rank last.
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    exact = [replace(base, document_number=f"T2600000010{n}", entity_name=f"INVENTED AIR {suffix}", name_key=f"INVENTED AIR {suffix}")
             for n, suffix in enumerate(("LLC", "INC", "CORP", "CO", "LTD", "LP", "PA"), start=1)]
    talk = Talk(["1"])
    fields = {"business_name": "Invented Air", "city": "", "street": "", "is_specific": True}
    path = run(talk, tmp_path, fields=fields, companies=exact)
    assert "2 more companies match at the level Strong and are not on this list." in talk.everything
    assert "   [Strong] INVENTED AIR LTD  (T26000000105)" in talk.said and "   [Strong] INVENTED AIR CORP  (T26000000103)" in talk.said   # each is named with its level and number
    assert sum(1 for line in talk.said if line.strip().startswith("MIAMI, FL  ·  name matches (")) == 7   # all seven, on the list or under it, show their place and reasons
    assert "6 other companies matched equally well." in path.read_text() # seven share the name: the one picked and six others, two of them off the list
    # Rule W1: every company the shortlist names, on the list or under it, is followed by where to check it and when it was fetched.
    sources = [line for line in talk.said if line.strip().startswith("Source: ")]
    assert len(sources) == 7 and all(line.endswith("· fetched about 2026-10-22") for line in sources)
    for number in range(101, 108):
        assert any(f"record, document number T26000000{number} (https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber)" in line for line in sources)


def seven_with_one_name(city):
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    return [replace(base, document_number=f"T2600000010{n}", entity_name=f"INVENTED AIR {suffix}", name_key=f"INVENTED AIR {suffix}", principal_city=city)
            for n, suffix in enumerate(("LLC", "INC", "CORP", "CO", "LTD", "LP", "PA"), start=1)]


def test_with_a_city_given_the_counts_say_which_companies_they_cover(tmp_path):
    # The review of leg C3 found that both sentences read as if they counted every company with the name. They count less, and now say so.
    fields = {"business_name": "Invented Air", "city": "Tampa", "street": "", "is_specific": True}
    in_the_city = Talk(["1"])                                            # seven same-name companies IN Tampa: all Strong, two off the list
    path = run(in_the_city, tmp_path, fields=fields, companies=seven_with_one_name("TAMPA"))
    assert "2 more companies match at the level Strong and are not on this list." in in_the_city.everything
    assert path.read_text().count("6 other companies matched equally well.") == 1   # Strong: counted over every candidate, on the list or not
    elsewhere = Talk(["1"])                                              # the same seven in Miami: the name matches and the city does not, so all are Likely
    path = run(elsewhere, tmp_path, fields=fields, companies=seven_with_one_name("MIAMI"))
    assert "not on this list" not in elsewhere.everything                 # nothing is claimed about the two that did not fit: they are not counted
    assert "match level Likely" in path.read_text()
    assert "4 other companies on the shortlist matched equally well." in path.read_text()   # five are shown, and the sentence says its count is of those


def test_a_company_in_a_city_that_only_begins_with_the_one_given_is_not_said_to_be_in_that_city(tmp_path):
    # "Jacksonville" also finds companies in JACKSONVILLE BEACH, because the comparison is "begins with". The sentence has to say that.
    fields = {"business_name": "Invented Air", "city": "Jacksonville", "street": "", "is_specific": True}
    talk = Talk(["1"])
    run(talk, tmp_path, fields=fields, companies=seven_with_one_name("JACKSONVILLE BEACH"))
    assert "JACKSONVILLE BEACH" in talk.everything                        # the registered city is shown on each line, so the reader can see it differs
    assert sum(1 for line in talk.said if "JACKSONVILLE BEACH, FL  ·  " in line and "; principal city on record begins with the city you gave; ACTIVE" in line) == 7
    assert "in the city you gave" not in talk.everything and "city matches" not in talk.everything


def test_a_possible_match_needs_a_yes_before_a_report_is_made(tmp_path):
    fields = {"business_name": "Invented Air Cooling", "city": "", "street": "", "is_specific": True}
    refused = Talk(["1", "n", ""])                                       # pick it, say no, then nothing more to add
    assert run(refused, tmp_path, fields=fields) is None and list(tmp_path.iterdir()) == []
    assert any("That's only a POSSIBLE match" in prompt for prompt in refused.asked)
    accepted = Talk(["1", "y"])
    saved = run(accepted, tmp_path, fields=fields).read_text()
    assert "match level Possible" in saved
    assert "**This is only a POSSIBLE match: the name is similar, and nothing else confirms it is the company you mean.**" in saved   # and the saved report says so at the top


def test_a_wrong_pick_is_asked_again_and_zero_asks_for_more(tmp_path):
    talk = Talk(["9", "abc", "0", ""])                                   # out of range, not a number, then "add more details", then nothing to add
    assert run(talk, tmp_path) is None
    assert talk.said.count("Please type a number from 0 to 5.") == 2
    assert talk.asked[-1] == "Add the business's full name or its city (press Enter if you don't know): "   # since leg D4: a street appended to a named note is not used


def test_the_command_gives_up_after_three_rounds_and_never_guesses(tmp_path):
    talk = Talk(["0", "more", "0", "more", "0", "more"])
    assert run(talk, tmp_path) is None and talk.answers == []            # three rounds, each "add more details", and then it stops asking
    assert talk.said[-1].strip() == wording.GIVING_UP


def test_others_at_the_same_level_counts_below_the_top_level_among_the_companies_shown():
    from datum.search import search_pool, shortlist
    companies = fx.load_companies()
    short = shortlist(search_pool(FakeBackend(companies), "Invented Air Conditioning", "Boynton Beach"), city_given=True)
    assert short.levels[0] == "Strong" and report.others_at_the_same_level(short, 0) == 0      # one Strong company: no tie
    below = [index for index, level in enumerate(short.levels) if level == "Possible"]
    assert len(below) >= 2 and report.others_at_the_same_level(short, below[0]) == len(below) - 1   # the other Possible companies on the list


class ApiDown(Exception):
    """Stands in for the Claude client's own errors, which are not ValueError."""


@pytest.mark.parametrize("error_class", [ValueError, RuntimeError, KeyError, ConnectionError, ApiDown])
def test_a_failed_extraction_says_two_fixed_sentences_and_never_the_errors_own_words(tmp_path, error_class):
    # extract.py used to raise ValueError("No fields returned for: <the whole note>"), and nothing caught it, so a traceback printed the note.
    def broken(text):
        raise error_class(f"No fields returned for: {text!r}")           # the worst case: an error that quotes the note

    talk = Talk([])                                                      # it must not ask anything either
    assert run(talk, tmp_path, extract=broken) is None
    assert talk.said == ["\nThe search is unavailable right now, so no company is shown.",
                         f"The extraction step stopped with this kind of error: {error_class.__name__}."]   # the class name only: it cannot hold the note
    for word in PRIVATE + (NOTE, "No fields returned"):
        assert word not in talk.everything
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("missing", ["business_name", "city", "street", "is_specific"])
def test_a_reply_with_any_one_field_missing_is_a_failed_extraction_too(tmp_path, missing):
    # One field at a time. A reply with no is_specific must not be searched as if the note had named a business (acceptance test A2).
    reply = {name: value for name, value in FIELDS.items() if name != missing}
    talk = Talk([])
    assert run(talk, tmp_path, extract=lambda text: dict(reply)) is None
    assert talk.said == ["\n" + wording.SEARCH_UNAVAILABLE, "The extraction step stopped with this kind of error: KeyError."]
    assert "INVENTED" not in talk.everything and list(tmp_path.iterdir()) == []


def names_used(node):
    """Every variable name read anywhere inside a piece of parsed code."""
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def names_that_hold_the_note(function):
    """The function's parameter for the note, and every name assigned from it, directly or through another such name."""
    holding = {function.args.args[1].arg}                                 # extract_fields(client, note): the second parameter, whatever it is called
    grew = True
    while grew:                                                           # follow "text = note", then "copy = text", until nothing new is found
        grew = False
        for node in ast.walk(function):
            if isinstance(node, ast.Assign) and names_used(node.value) & holding:
                for target in node.targets:
                    for name in names_used(target) - holding:
                        holding.add(name)
                        grew = True
    return holding


def raises_that_quote_the_note(source):
    function = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == "extract_fields")
    holding = names_that_hold_the_note(function)
    return [node for node in ast.walk(function) if isinstance(node, ast.Raise) and names_used(node) & holding]


def test_no_error_raised_by_the_extraction_step_is_built_from_the_note():
    # extract.py is parsed and not imported: importing it loads the API key, and the offline suite needs no key. Parsing sees the
    # STRUCTURE of the code, so it catches the note in an f-string, joined with +, passed to format(), renamed, or copied to another name first.
    source = (Path(report.__file__).parent / "extract.py").read_text()
    assert "raise " in source and raises_that_quote_the_note(source) == []
    for body in ('raise ValueError(f"x {note!r}")', 'raise ValueError("x " + note)', 'raise ValueError("x {}".format(note))',
                 'text = note\n    raise ValueError(f"x {text!r}")', 'text = note\n    copy = text[:80]\n    raise ValueError(copy)'):
        assert len(raises_that_quote_the_note(f"def extract_fields(client, note):\n    {body}")) == 1, body
    assert len(raises_that_quote_the_note('def extract_fields(client, text):\n    raise ValueError(f"x {text!r}")')) == 1   # the parameter under another name


def test_the_note_is_read_at_a_prompt_and_never_from_the_command_line():
    # A note typed after the command may be written to the shell's history file. Rule W6: the note is never stored.
    talk = Talk(["invented air conditioning boynton beach"])
    assert report.read_note(["jane", "doe", "roofing"], talk.ask, talk.say) == "invented air conditioning boynton beach"
    assert talk.said == [wording.NOTE_NOT_ON_COMMAND_LINE] and talk.asked == ["Describe the client: "]
    assert "jane" not in talk.everything                                  # what was typed after the command is neither used nor shown back
    quiet = Talk(["a note"])
    assert report.read_note([], quiet.ask, quiet.say) == "a note" and quiet.said == []


def uses_of_the_command_line(source):
    """(every use of argv in main() or imported at the top of the module, the uses that are an argument of read_note)."""
    tree = ast.parse(source)
    main = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "main")

    def argv_nodes(node):
        return [child for child in ast.walk(node)
                if (isinstance(child, ast.Attribute) and child.attr in ("argv", "orig_argv")) or (isinstance(child, ast.Name) and child.id in ("argv", "orig_argv"))]

    imported = [alias for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names if alias.name in ("argv", "orig_argv")]
    handed_over = [node for call in ast.walk(main) if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "read_note"
                   for argument in call.args for node in argv_nodes(argument)]
    return argv_nodes(main) + imported, handed_over


def test_main_hands_the_command_line_to_read_note_and_uses_it_nowhere_else():
    # Parsed, so that the command line joined into the note is seen however it is spelled.
    every_use, handed_over = uses_of_the_command_line(inspect.getsource(report))
    assert len(every_use) == 1 and len(handed_over) == 1                  # one use in all, and it is the argument of read_note
    for bad in ('    note = " ".join(sys.argv[1:]) or read_note([])',
                '    note = " ".join(sys.argv[1:]) or read_note(sys.argv[1:])',
                '    from sys import argv\n    note = " ".join(argv[1:]) or read_note(sys.argv[1:])',
                '    note = read_note(arguments=sys.argv[1:])\n    extra = sys.orig_argv'):
        every_use, handed_over = uses_of_the_command_line("def main():\n" + bad)
        assert len(every_use) != 1 or len(handed_over) != 1, bad          # each bad spelling is told apart from the good one


def test_a_vague_note_shows_no_company_until_a_second_extraction_names_one(tmp_path):
    # Acceptance test A2. Without the jump back to the top of the loop, the first, vague extraction would be searched and a shortlist shown.
    vague = {"business_name": "Invented Air Conditioning", "city": "", "street": "", "is_specific": False}   # a name the search WOULD find
    seen_before_second_call = []
    calls = []

    def extract(text):
        calls.append(text)
        if len(calls) == 1:
            return dict(vague)
        seen_before_second_call.extend(talk.said)                         # everything printed up to the second extraction
        return dict(FIELDS)

    talk = Talk(["invented air conditioning in boynton beach", "1"])
    path = run(talk, tmp_path, note="the ac guy", extract=extract)
    assert calls == ["the ac guy", "the ac guy invented air conditioning in boynton beach"]   # the answer is added to the note and extracted again
    assert seen_before_second_call == []                                  # nothing at all was printed about any company before that
    assert path is not None and "INVENTED AIR CONDITIONING, LLC" in talk.everything


def test_a_reply_that_calls_the_note_specific_and_gives_no_name_is_treated_as_naming_no_business(tmp_path):
    # Without this, the terminal would print: I read that as: the business name "" - and then search for nothing.
    talk = Talk([""])
    assert run(talk, tmp_path, fields={"business_name": "   ", "city": "Tampa", "street": "", "is_specific": True}) is None
    assert talk.asked == ["That describes a business but doesn't name one. Add its name, or its street address beginning with the house number. (press Enter if you don't know): "]
    assert not [line for line in talk.said if "I read that as" in line] and "INVENTED" not in talk.everything


def test_pressing_enter_at_the_possible_match_question_means_no(tmp_path):
    # The prompt ends in (y/N). A report for a Possible match that nobody confirmed would point at a company on a guess.
    fields = {"business_name": "Invented Air Cooling", "city": "", "street": "", "is_specific": True}
    for answer in ("", " ", "yes please", "N", "no"):                    # only the single letter y, in either case, is a yes
        talk = Talk(["1", answer, ""])
        assert run(talk, tmp_path, fields=fields) is None and list(tmp_path.iterdir()) == [], answer
    assert run(Talk(["1", " Y "]), tmp_path, fields=fields) is not None


def test_a_pick_one_past_the_end_of_the_list_is_asked_again(tmp_path):
    talk = Talk(["6", "²", "1"])                                         # five companies are listed: 6 is not one of them, and "²" is not a number to int()
    path = run(talk, tmp_path)
    assert talk.said.count("Please type a number from 0 to 5.") == 2 and path is not None


def test_nothing_the_terminal_prints_in_a_whole_conversation_holds_a_banned_word(tmp_path):
    w4_words = ("clean", "safe", "risky", "trustworthy", "reliable", "credit", "score", "recommend")   # typed out, not read from wording.py
    banned = re.compile(r"\b(" + "|".join(w4_words) + ")", re.IGNORECASE)
    talk = Talk(["0", "more", "1"])                                      # a shortlist, "add more details", a second shortlist, a pick, the report
    assert run(talk, tmp_path) is not None
    assert len(talk.said) > 20 and banned.findall(talk.everything) == []


def test_the_terminal_marks_an_inactive_company_beside_its_name_and_says_it_once(tmp_path):
    # Working rule S10 (leg D2). The terminal's shortlist is built from the same page candidates as the web app's.
    talk = Talk(["0", ""])                                                # look at the list, add nothing, and stop
    run(talk, tmp_path)
    lines = [line for line in talk.said if "INVENTED ROOFING CORP" in line]
    assert len(lines) == 1 and lines[0].endswith("INVENTED ROOFING CORP  (T26000000003)  ·  Inactive with the state")
    assert sum(line.count("Inactive with the state") for line in talk.said) == 1 and not [line for line in talk.said if "INACTIVE" in line]
    assert not [line for line in talk.said if "INVENTED AIR CONDITIONING, LLC" in line and "Inactive" in line]   # an active company is not marked


def test_the_terminals_question_about_a_possible_match_still_gives_an_inactive_companys_status(tmp_path):
    # The shortlist marks the company beside its name (rule S10). The question that follows a pick, and the saved report's line,
    # are not the shortlist, and they keep the status among the reasons, as they have since October.
    inactive = [c for c in fx.load_companies() if c.document_number == fx.INACTIVE_COMPANY]
    talk = Talk(["1", "y"])
    path = run(talk, tmp_path, fields={"business_name": "Invented Roofers", "city": "", "street": "", "is_specific": True}, companies=inactive)
    question = next(prompt for prompt in talk.asked if "POSSIBLE match" in prompt)
    assert "INACTIVE with the state. Nothing else confirms" in question
    assert "INACTIVE with the state) · chosen by the user from a shortlist." in path.read_text()
    assert [line for line in talk.said if line.endswith("(T26000000003)  ·  Inactive with the state")]   # and the shortlist line above it has the mark


def test_the_terminal_lists_the_companies_in_rank_order_and_says_so_when_a_lower_level_comes_first(tmp_path):
    # Phase D rule S12 (leg D3). The terminal prints the same Shortlist the page shows, so it is in rank order too, and it says the
    # rule's sentence once, after the list and before it asks for a pick. Until leg D3 the two Likely companies were printed first.
    sentence = "The list is in search order. The level beside each company says how much of the record agrees with what you typed."
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    rows = (("ACME ROOFING AND SIDING INC", "TAMPA"), ("ACME ROOFERS INC", "JACKSONVILLE"), ("ACME ROOFER INC", "JACKSONVILLE"),
            ("ACME ROOFINGS", "TAMPA"), ("ACME ROOFERS OF TAMPA INC", "TAMPA"))
    five = [replace(base, document_number=f"T2600000020{n}", entity_name=name, name_key=name, principal_city=city) for n, (name, city) in enumerate(rows, start=1)]
    acme = {"business_name": "Acme Roofing", "city": "Jacksonville", "street": "", "is_specific": True}
    talk = Talk(["0", ""])                                               # look at the list, add nothing, stop
    run(talk, tmp_path, note="acme roofing jacksonville", fields=acme, companies=five)
    numbered = [line for line in talk.said if re.match(r"\d\. \[", line)]
    assert [re.match(r"\d\. \[(\w+)\]", line).group(1) for line in numbered] == ["Possible", "Likely", "Likely", "Possible", "Possible"]
    assert talk.said.count(sentence) == 1 and talk.said.index(sentence) > talk.said.index(numbered[-1])   # once, under the list
    assert "2 companies on this list match at the level Likely." in talk.everything   # the tie reads the best level on the list
    # Five Possible companies are already in level order, so nothing is said about the order.
    talk = Talk(["0", ""])
    run(talk, tmp_path, fields={"business_name": "Invented Air Cooling", "city": "", "street": "", "is_specific": True})
    assert sentence not in talk.everything and len([line for line in talk.said if re.match(r"\d\. \[Possible\]", line)]) == 5


# --- Rule S18 (leg D4): the terminal takes the same path as the web app -----------------------------------

ADDRESS_NOTE = {"business_name": "<UNKNOWN>", "city": "", "street": "8586 palm pwwy", "is_specific": False}
# What the extraction step returned for the note "8586 palm pwwy" on Nov 25, 2026: no business, and the street as typed.


def palm_pkwy(active=1, inactive=2):
    """Invented companies whose principal address is 8586 Palm Pkwy, written three ways, plus the fixture companies."""
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    spellings = ("8586 PALM PKWY", "8586 PALM PARKWAY STE 4", "8586 Palm Pkwy., Suite 210")
    companies = [replace(base, document_number=f"T260000002{n:02d}", entity_name=f"INVENTED PIZZA {n} LLC", name_key=f"INVENTED PIZZA {n} LLC",
                         status_code="A", principal_address_1=spellings[n % 3], principal_city="ORLANDO", principal_zip="32836") for n in range(active)]
    companies += [replace(base, document_number=f"T260000003{n:02d}", entity_name=f"INVENTED TILE {n} INC", name_key=f"INVENTED TILE {n} INC",
                          status_code="I", principal_address_1=spellings[(n + 1) % 3], principal_city="ORLANDO", principal_zip="32836") for n in range(inactive)]
    return fx.load_companies() + companies


def test_an_address_alone_gets_the_address_search_in_the_terminal_and_a_report_of_the_company_picked(tmp_path):
    # Phase D rule S18. Until leg D4 the terminal asked "That describes a business but doesn't name one" for this note, and this test
    # fails on that: the question was asked, and nothing was listed.
    talk = Talk(["1"])
    path = run(talk, tmp_path, note="8586 palm pwwy", fields=ADDRESS_NOTE, companies=palm_pkwy())
    assert path == tmp_path / "T26000000200_20261124.md"
    said = talk.said
    assert 'I read that as: the street "8586 palm pwwy"' in "\n".join(said)
    assert said.index("1 active company matches.") < said.index("1. INVENTED PIZZA 0 LLC  (T26000000200)")
    assert "   Principal address 8586 PALM PKWY, ORLANDO, FL 32836" in said   # the address as the state has it, to compare with what was typed
    counted = next(line for line in said if line.startswith("2 inactive companies also match and are not listed."))
    assert "Source: Florida Division of Corporations (Sunbiz) company records (" in counted   # the count cites the records, as on the page
    assert said.count("A company's principal address is the address it gave the state, which is not always where it does business.") == 1
    assert "TILE" not in talk.everything and "T260000003" not in talk.everything   # the inactive companies are counted and never listed (rule S6)
    assert talk.asked == ["\nPick 1-1, or 0 to add more details: "]   # no question about a Possible match: a company found by its address has no level
    saved = path.read_text()
    assert ('from the street "8586 palm pwwy" · found by its principal address on record (the same house number, and a street name made only of '
            "words that were typed) · chosen by the user from the active companies listed.") in saved
    assert "match level" not in saved


def test_an_address_with_only_inactive_companies_in_the_terminal_asks_for_the_name_and_lists_nobody(tmp_path):
    talk = Talk([""])                                                    # nothing to pick, so it asks for more, and Enter alone stops
    assert run(talk, tmp_path, note="8586 palm pwwy", fields=ADDRESS_NOTE, companies=palm_pkwy(active=0, inactive=2)) is None
    said = talk.said
    assert said.index("No active company matches.") < next(i for i, line in enumerate(said) if line.startswith("2 inactive companies"))
    assert said.count("Type the business's name to look for it with the name search, which lists inactive companies too.") == 1   # rule S16
    assert talk.asked == ["Add the business's full name or its city (press Enter if you don't know): "] and "TILE" not in talk.everything


def web_answer(fields, companies):
    """The web app's answer to one note, with the same stand-ins the terminal gets: the page, as HTML."""
    from contextlib import contextmanager                             # turns a function with one `yield` into something to open with `with`
    from fastapi.testclient import TestClient                         # calls the app without a server
    from datum.web.app import create_app

    @contextmanager
    def open_backends():
        yield FakeBackend(companies), FakeReportBackend(companies, fx.load_flags(), fx.load_sources())

    code = "a-throwaway-code-for-tests"                                # not a secret: it exists only inside this test
    browser = TestClient(create_app(code, lambda note: dict(fields), open_backends, today=lambda: fx.BUILT_ON), client=("127.0.0.1", 50000))
    browser.auth = ("anyone", code)
    return browser.post("/search", data={"note": "a note"}).text


ADDRESS_SENTENCES = (wording.ADDRESS_TOO_MANY, wording.ADDRESS_NOT_FOUND, wording.ADDRESS_NOT_FOUND_IN_CITY)


def kind_on_the_page(page):
    heading = re.search(r"<h1>(.*?)</h1>", page).group(1)
    if heading == wording.SHORTLIST_HEADING:
        return "name"
    if heading == wording.ADDRESS_HEADING or any(sentence.replace("'", "&#39;") in page for sentence in ADDRESS_SENTENCES):
        return "address"
    return "ask" if wording.ASK_FOR_A_BUSINESS_ON_A_PAGE.replace("'", "&#39;") in page else "something else"


def kind_in_the_terminal(talk):
    if any(re.match(r"\d+\. \[(Strong|Likely|Possible)\]", line) for line in talk.said) or wording.NO_COMPANY_FOUND in talk.said:
        return "name"
    if any(line.startswith("A company matches when its principal address") for line in talk.said) or any(s in talk.said for s in ADDRESS_SENTENCES):
        return "address"
    return "ask" if talk.asked and talk.asked[0].startswith(wording.ASK_FOR_A_BUSINESS_ON_A_PAGE) else "something else"


@pytest.mark.parametrize("label,fields,companies,kind,listed", [
    ("a business named", FIELDS, None, "name", 5),                   # five companies, in whatever order the name search ranks them
    ("an address with one active company", ADDRESS_NOTE, "one", "address", ["T26000000200"]),
    ("an address with only inactive companies", ADDRESS_NOTE, "inactive", "address", []),
    ("an address with too many companies", ADDRESS_NOTE, "crowded", "address", []),
    ("an address nobody has", {**ADDRESS_NOTE, "street": "12 made up rd"}, "one", "address", []),
    ("no business and no house number", {"business_name": "pool service", "city": "", "street": "Race Track Rd", "is_specific": False}, None, "ask", []),
])
def test_the_terminal_and_the_web_app_give_the_same_kind_of_answer_and_the_same_companies_for_one_note(tmp_path, label, fields, companies, kind, listed):
    # Phase D rule S18: one note gets the same answer in both places. Until leg D4 the three address notes got the address search on the
    # page and a question in the terminal, and this test fails on that. The sentences an address page shows must be said in the terminal too.
    companies = {None: fx.load_companies(), "one": palm_pkwy(), "inactive": palm_pkwy(active=0, inactive=2), "crowded": palm_pkwy(active=40, inactive=11)}[companies]
    page = web_answer(fields, companies)
    talk = Talk(["0", ""] if listed else [""])                           # look at the list and pick nothing, or add nothing, so the run stops
    run(talk, tmp_path, note="a note", fields=fields, companies=companies)
    assert kind_on_the_page(page) == kind_in_the_terminal(talk) == kind, label
    on_the_page = re.findall(r'href="/company/(T\d{11})\?from=', page)
    in_the_terminal = [re.search(r"\((T\d{11})\)", line).group(1) for line in talk.said if re.match(r"\d+\. ", line)]
    assert on_the_page == in_the_terminal, label                           # the same companies, in the same order
    assert (len(on_the_page) == listed) if isinstance(listed, int) else (on_the_page == listed), label
    if kind == "address":
        visible = " ".join(re.sub(r"<[^>]+>", " ", page).replace("&#39;", "'").split())
        for sentence in (wording.ADDRESS_NO_ACTIVE, wording.ADDRESS_ONLY_INACTIVE, wording.PRINCIPAL_ADDRESS_NOTE, wording.ADDRESS_TOO_MANY,
                         wording.ADDRESS_NOT_FOUND, wording.count_text(2, wording.ADDRESS_INACTIVE_ONE, wording.ADDRESS_INACTIVE_MANY),
                         wording.count_text(1, wording.ADDRESS_ACTIVE_ONE, wording.ADDRESS_ACTIVE_MANY)):
            assert (sentence in visible) == (sentence in talk.everything), (label, sentence)   # every fixed sentence is on both, or on neither
