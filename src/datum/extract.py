"""extract.py: step 1 of Datum search.

Prompt v3 (2026-11-25, Phase D, leg D1): the street line now asks for the house number and the
street exactly as typed, without correcting the spelling. The search by address reads the house
number from the start of that field, and it compares the street's words itself, so a corrected
spelling would hide what the contractor typed. Nothing else in the prompt changed.

Prompt v2 (2026-10-27): v1 dropped "really good" from "really good beer" and invented the city
"Surfside" from "surfside luxery homes". v2 adds two general rules: keep ordinary words that
could be part of a name, and never take a city from inside the name.

(Original summary:) Turn messy contractor text into structured fields.

What the command does: it reads the test cases whose ids it is given from a file of cases, asks
Claude to pull the business name, the city and the street out of each, and APPENDS one row per
case to the output file. A row that is already in the output file is never written again. That
is on purpose: the rows of cases 1 to 10 in pipeline/seeds/extracted_inputs.csv were made by
prompt v2 and stay as they are, so the evaluation's history can be compared across legs. Until
Phase D the command extracted the whole test set and overwrote the file, which would have
replaced those ten rows with whatever prompt v3 returns today.

Run from ~/datum with the project's virtual environment active:
    python src/datum/extract.py --cases 11 12 13
The checked cases are read from pipeline/seeds/test_set.csv and written to
pipeline/seeds/extracted_inputs.csv. For the draft cases, which git ignores (working rule S1):
    python src/datum/extract.py --test-set evals/draft_cases.csv --output evals/draft_extracted.csv --cases 101 102
Needs the environment variable ANTHROPIC_API_KEY (the SDK reads it automatically). Each case is
one paid call to the Claude API, about $0.0004 (the plan's figure, not read off a bill).
"""

import argparse                 # reads --cases, --test-set and --output from the command line
import csv                      # read and write CSV files (built into Python)
import sys                      # the exit code
from collections.abc import Callable   # the type of "a function that turns a note into fields"
from pathlib import Path        # build file paths that work on any operating system

import anthropic                # Anthropic's SDK: wraps the HTTPS (REST) calls to the Claude API

from dotenv import load_dotenv   # python-dotenv's function that reads NAME=value lines from a .env file into the environment
load_dotenv()                    # look for a .env file, starting in this file's folder (src/datum) and walking up to ~/datum, then load it

# --- Settings -------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]          # this file is src/datum/extract.py → go up 2 folders to ~/datum
TEST_SET = REPO_ROOT / "pipeline" / "seeds" / "test_set.csv"            # the default input: the hand-checked test cases
OUTPUT = REPO_ROOT / "pipeline" / "seeds" / "extracted_inputs.csv"      # the default output: one row of fields per case
COLUMNS = ("case_id", "input_text", "business_name", "city", "street", "is_specific", "model")   # the output's columns, in file order
MODEL = "claude-haiku-5-5"      # the smallest, cheapest Claude model: extraction is a simple task

# The instructions the model follows on every call. Kept short and specific.
SYSTEM_PROMPT = """You extract search fields from a contractor's note about a commercial client in Florida.
Return ONLY what the note says or clearly implies. Never invent a legal company name.
- business_name: the name of the business, with common abbreviations expanded
  (AC -> Air Conditioning, HVAC stays HVAC, mgmt -> Management, grp -> Group, bros -> Brothers).
  Keep every word that could be part of the name, even ordinary words: business names are
  often plain phrases (e.g. "best little bakery" -> Best Little Bakery). When unsure whether
  a word belongs to the name, keep it. Fix obvious misspellings.
  Leave out city names, street names, and filler words like "the guy" or "off".
- city: ONLY if the note contains a city name or a common nickname for one (jax -> Jacksonville).
  Never take a city from a word inside the business name. Otherwise empty.
- street: the house number and the street exactly as typed (for example "8586 palm pwwy"), without correcting the spelling, else empty.
- is_specific: true if the note names a specific business; false if it only describes one
  (e.g. "the pool guy") and more details are needed to identify it."""

# The exact shape we want back. Using a "tool" with a JSON schema forces structured output:
# the model must fill these fields instead of writing free text we'd have to parse.
# EXTRACT_TOOL = {...} - A normal Python dictionary assigned to a variable you named EXTRACT_TOOL.

# Name, description, input schema are fields Anthropic’s API recognizes as a tool definition.
EXTRACT_TOOL = {
    "name": "record_search_fields",                      # the tool's name (we force the model to call it)
    "description": "Record the search fields extracted from the note.",
    "input_schema": {                                    # JSON Schema: the fields, their types, which are required
        "type": "object",
        "properties": {
            "business_name": {"type": "string"},
            "city": {"type": "string"},
            "street": {"type": "string"},
            "is_specific": {"type": "boolean"},
        },
        "required": ["business_name", "city", "street", "is_specific"], #means “all four fields must be present.”
    },  # type, properties, required - fields for the JSON Schema, a standard for describing how data must be structured.
}



def extract_fields(client: anthropic.Anthropic, note: str) -> dict:  # 1. Define the function and its inputs - creates a function named extract_fields.
    # client is an Anthropic SDK client—the Python object used to communicate with Claude’s API.
    # note is the text you want Claude to read.
    # : anthropic.Anthropic and : str are type hints describing the expected inputs.
    # -> dict is a type hint saying the function should return a Python dictionary.Type hints describe expectations; Python doesn’t automatically enforce them.
    """Send one note to Claude and return the extracted fields as a Python dict."""
    response = client.messages.create(  # 2. Send the request to Claude. One HTTPS POST to the Messages API
        # This calls the SDK’s create method. The SDK sends the API request, 
        # waits for the reply, and stores the result in response.
        # Everything inside the parentheses configures that request:
        model=MODEL,                # Use the model specified by the MODEL variable.
        max_tokens=300,             # cap on the reply length (a few fields need very little). Limit the generated reply to 300 tokens. Tokens are pieces of text, not exactly words.
        system=SYSTEM_PROMPT,       # Follow the instructions stored in SYSTEM_PROMPT.
        tools=[EXTRACT_TOOL],       # offer the tool...Here is the tool definition describing the fields to fill in.
        # You pass the dictionary to the SDK when making a request
        # The SDK sends that definition to Claude through the API. 
        tool_choice={"type": "tool", "name": "record_search_fields"},  # ...and require the model to use it
        # No temperature setting: the installed SDK rejects it for this model. Repeatability
        # comes from saving the output to a CSV instead: the eval always scores that saved file.
        
        # It follows the same pattern:
        # - tool_choice= is a named argument to create().
        # - Its value is a dictionary.
        # - That dictionary contains two key–value pairs.
        # Together, they tell the API:
        # “Require Claude to use the specific tool named record_search_fields.”
        
        messages=[{"role": "user", "content": note}],    # the contractor's note is the user message. This is a list of a dictionary with two key-value pairs being passed as the argument named messages. 
    )
    # 3. Look through the response
    # Claude’s response contains a list of content blocks. A block might contain text or a request to use a tool.
    # This loop examines those blocks one at a time.
    for block in response.content:                       # the reply is a list of content blocks
        if block.type == "tool_use":                     # find the tool call...This asks: “Is this block a tool call?”
            return block.input                           # ...its input IS our structured fields
    raise ValueError("The model returned no fields for the note")  # should never happen with tool_choice forced. The note is NOT in the message: an error message ends up on a screen or in a log, and the note must not (Phase C working rule W6)


# This function takes a written note, sends it to Claude, 
# and returns the extracted fields as a Python dictionary.

# For example:

# Input note:
# "Find Acme LLC at 123 Main Street in Boston"

# Expected return value:
# {
#     "business_name": "Acme LLC",
#     "city": "Boston",
#     "street": "123 Main Street",
#     "is_specific": True
# }

# The dictionary itself doesn’t run a function or search for a business. 
# It describes the fields Claude should supply; your code then reads those 
# values.



def read_rows(path: Path) -> list[dict]:
    """Every row of a CSV file, each as a dict keyed by column name. A file that does not exist yet has no rows."""
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def extract_cases(case_ids: list[str], test_set: Path, output: Path, extract: Callable[[str], dict],
                  say: Callable[[str], None] = print) -> int:
    """Extract ONLY the cases whose ids are given, and append one row for each to the output file. Returns how many rows were added.

    Everything is checked before the first call is made, so a mistake costs nothing: an id
    that is not in the file of cases, an id given twice, or an id that already has a row in
    the output. That last check is what keeps a row from ever being extracted twice. The
    rows already in the output file are not rewritten: the file is opened for appending.
    """
    cases = {row["case_id"]: row for row in read_rows(test_set)}
    already = {row["case_id"] for row in read_rows(output)}
    unknown = [case_id for case_id in case_ids if case_id not in cases]
    done = [case_id for case_id in case_ids if case_id in already]
    twice = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if unknown:
        raise ValueError(f"no case with id {', '.join(unknown)} in {test_set.name}, so nothing was extracted")
    if done:
        raise ValueError(f"case {', '.join(done)} already has a row in {output.name}. A case is never extracted twice, so nothing was extracted")
    if twice:
        raise ValueError(f"case {', '.join(twice)} was given more than once, so nothing was extracted")
    # None of these messages holds a note: an error message ends up on a screen or in a log (working rule W6).

    new_file = not output.exists()
    with output.open("a", newline="") as f:              # "a" = append: what is already in the file stays byte for byte
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()                         # a new file starts with the column names
        for case_id in case_ids:
            case = cases[case_id]
            fields = extract(case["input_text"])         # one paid call
            writer.writerow({
                "case_id": case_id,                      # the join key back to the file of cases
                "input_text": case["input_text"],
                "business_name": fields["business_name"],
                "city": fields["city"],
                "street": fields["street"],
                "is_specific": fields["is_specific"],
                "model": MODEL,                          # provenance: which model produced this row
            })
            say(f'{case_id:>3}  {case["input_text"]:<35} -> {fields}')   # show progress as it runs
    return len(case_ids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract the search fields of the test cases whose ids are given, and append them to the output file.")
    parser.add_argument("--cases", nargs="+", required=True, metavar="ID",
                        help="the case ids to extract. Required: there is no way to extract a whole file, because that would extract old cases again")
    parser.add_argument("--test-set", type=Path, default=TEST_SET, help="the file of cases to read (default: the hand-checked test set)")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="the file to append the extracted rows to (default: the committed seed)")
    args = parser.parse_args(argv)
    if args.test_set.resolve() != TEST_SET.resolve() and args.output.resolve() == OUTPUT.resolve():
        # Any file of cases but the checked test set is a file of DRAFTS, and the default output is the seed that git tracks. Without
        # this stop, leaving --output out would write unchecked draft notes into a public file (working rule S1).
        parser.error("--test-set names a file other than the checked test set, so --output must name the file to write to. "
                     "The default output is the committed seed, which may only hold checked cases")

    client = anthropic.Anthropic()                       # reads ANTHROPIC_API_KEY from the environment
    try:
        added = extract_cases(args.cases, args.test_set, args.output, lambda note: extract_fields(client, note))
    except ValueError as error:                          # one of the three checks above. Its message names ids and files, never a note
        print(f"NOT EXTRACTED: {error}")
        return 1
    print(f"\nAppended {added} rows to {args.output}")
    return 0


if __name__ == "__main__":                               # run main() only when executed directly, not when imported
    sys.exit(main())                                     # run main and pass its result to the shell
