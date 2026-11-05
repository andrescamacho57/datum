"""extract.py: step 1 of Datum search.

Prompt v2 (2026-10-27): v1 dropped "really good" from "really good beer" and invented the city
"Surfside" from "surfside luxery homes". v2 adds two general rules: keep ordinary words that
could be part of a name, and never take a city from inside the name.

(Original summary:) Turn messy contractor text into structured fields.

What it does: reads each test input from pipeline/seeds/test_set.csv, asks Claude to pull out
the business name, city, and street, and writes the results to
pipeline/seeds/extracted_inputs.csv. dbt then loads that CSV into Snowflake as a seed, and
the scoring script searches on the CLEAN fields instead of the raw text.

Run from ~/datum with the project's virtual environment active:
    python src/datum/extract.py
Needs the environment variable ANTHROPIC_API_KEY (the SDK reads it automatically).
"""

import csv                      # read and write CSV files (built into Python)
from pathlib import Path        # build file paths that work on any operating system

import anthropic                # Anthropic's SDK: wraps the HTTPS (REST) calls to the Claude API

from dotenv import load_dotenv   # python-dotenv's function that reads NAME=value lines from a .env file into the environment
load_dotenv()                    # look for a .env file, starting in this file's folder (src/datum) and walking up to ~/datum, then load it

# --- Settings -------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]          # this file is src/datum/extract.py → go up 2 folders to ~/datum
TEST_SET = REPO_ROOT / "pipeline" / "seeds" / "test_set.csv"            # input: the 10 test cases
OUTPUT = REPO_ROOT / "pipeline" / "seeds" / "extracted_inputs.csv"      # output: one row of fields per case
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
- street: a street or road if named, else empty.
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
    raise ValueError(f"No fields returned for: {note!r}")  # should never happen with tool_choice forced


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



def main() -> None:
    client = anthropic.Anthropic()                       # reads ANTHROPIC_API_KEY from the environment

    with TEST_SET.open(newline="") as f:                 # open the test set for reading
        cases = list(csv.DictReader(f))                  # each row becomes a dict keyed by column name

    rows = []
    for case in cases:
        fields = extract_fields(client, case["input_text"])
        rows.append({
            "case_id": case["case_id"],                  # the join key back to test_set
            "input_text": case["input_text"],
            "business_name": fields["business_name"],
            "city": fields["city"],
            "street": fields["street"],
            "is_specific": fields["is_specific"],
            "model": MODEL,                              # provenance: which model produced this row
        })
        print(f'{case["case_id"]:>2}  {case["input_text"]:<35} -> {fields}')  # show progress as it runs

    with OUTPUT.open("w", newline="") as f:              # "w" = write (overwrite) the output file
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()                             # first line: column names
        writer.writerows(rows)                           # one line per case

    print(f"\nWrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":                               # run main() only when executed directly, not when imported
    main()
