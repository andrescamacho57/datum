"""test_extract.py: offline tests for the command-line side of src/datum/extract.py.

What is under test: prompt v3's street line, and the option that extracts ONLY the case ids
it is given and appends their rows (Phase D, leg D1). The rows of cases 1 to 10 were made by
prompt v2 and must never be extracted again, so the tests prove that a row already in the
output file is neither rewritten nor paid for twice.

No call is made to the Claude API: the extraction step is a stand-in function. No secrets file
is read either. Importing extract.py normally loads the local secrets file into the environment,
so the fixture below swaps that loader for one that does nothing before it imports the module,
and it makes building a real API client an error.

Every case below is invented. Run from ~/datum:  pytest
"""

import csv                                  # writes the small files of cases and reads back what was appended
import importlib                            # imports the module under test by name, inside the fixture
import sys                                  # the table of imported modules

import pytest                               # the test runner


@pytest.fixture
def extract(monkeypatch):
    """The module src/datum/extract.py, imported without loading a secrets file and unable to build a real API client."""
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)   # the loader the module calls when it is imported
    monkeypatch.delitem(sys.modules, "datum.extract", raising=False)           # so the import below really runs the module's top level
    module = importlib.import_module("datum.extract")

    def no_client(*args, **kwargs):
        raise AssertionError("a test tried to build a real Claude API client")

    monkeypatch.setattr(module.anthropic, "Anthropic", no_client)
    yield module
    sys.modules.pop("datum.extract", None)                                     # the next test imports it afresh


def write_cases(path, cases):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "case_group", "input_text"])
        writer.writerows(cases)


CASES = [("1", "g", "acme roofing jax"), ("2", "g", "best pools"), ("3", "g", "12 invented way"), ("4", "g", "coral electric")]
OLD_ROWS = ("case_id,input_text,business_name,city,street,is_specific,model\r\n"
            "1,acme roofing jax,Acme Roofing,Jacksonville,,True,an-older-model\r\n"
            "2,best pools,Best Pools,,,True,an-older-model\r\n")


def stand_in(handed):
    """An extraction step that records each note it is handed and answers with fixed fields."""
    def extract_one(note):
        handed.append(note)
        return {"business_name": "", "city": "", "street": note, "is_specific": False}
    return extract_one


def test_prompt_v3_asks_for_the_house_number_and_the_street_exactly_as_typed(extract):
    # The brief gives the line word for word. The search by address reads the house number from the start of this field.
    line = ('- street: the house number and the street exactly as typed (for example "8586 palm pwwy"), '
            "without correcting the spelling, else empty.")
    assert line in extract.SYSTEM_PROMPT.splitlines()
    assert "a street or road if named" not in extract.SYSTEM_PROMPT       # prompt v2's street line is gone


def test_only_the_cases_given_are_extracted_and_their_rows_are_appended(extract, tmp_path):
    test_set, output = tmp_path / "cases.csv", tmp_path / "extracted.csv"
    write_cases(test_set, CASES)
    output.write_bytes(OLD_ROWS.encode())
    handed = []
    added = extract.extract_cases(["3"], test_set, output, stand_in(handed), say=lambda line: None)
    assert added == 1 and handed == ["12 invented way"]                   # one call, for case 3 only. Cases 1, 2 and 4 cost nothing
    written = output.read_bytes().decode()
    assert written.startswith(OLD_ROWS)                                   # the rows that were there are unchanged, byte for byte
    assert written[len(OLD_ROWS):] == f"3,12 invented way,,,12 invented way,False,{extract.MODEL}\r\n"   # and one row follows them


def test_a_case_that_already_has_a_row_is_refused_before_any_call_is_made(extract, tmp_path):
    # Cases 1 to 10 were extracted by prompt v2 and stay as they are. Asking for one of them again must cost nothing and change nothing.
    test_set, output = tmp_path / "cases.csv", tmp_path / "extracted.csv"
    write_cases(test_set, CASES)
    output.write_bytes(OLD_ROWS.encode())
    handed = []
    with pytest.raises(ValueError, match="case 2 already has a row in extracted.csv"):
        extract.extract_cases(["3", "2"], test_set, output, stand_in(handed), say=lambda line: None)
    assert handed == [] and output.read_bytes().decode() == OLD_ROWS      # not even case 3, which was new, was extracted


def test_an_unknown_id_or_an_id_given_twice_is_refused_before_any_call_is_made(extract, tmp_path):
    test_set, output = tmp_path / "cases.csv", tmp_path / "extracted.csv"
    write_cases(test_set, CASES)
    handed = []
    with pytest.raises(ValueError, match="no case with id 9 in cases.csv"):
        extract.extract_cases(["3", "9"], test_set, output, stand_in(handed), say=lambda line: None)
    with pytest.raises(ValueError, match="case 3 was given more than once"):
        extract.extract_cases(["3", "4", "3"], test_set, output, stand_in(handed), say=lambda line: None)
    assert handed == [] and not output.exists()                           # nothing was called and no file was made


def test_a_new_output_file_starts_with_the_column_names(extract, tmp_path):
    # The draft cases are extracted into a file that does not exist yet (evals/draft_extracted.csv).
    test_set, output = tmp_path / "draft_cases.csv", tmp_path / "draft_extracted.csv"
    write_cases(test_set, CASES)
    extract.extract_cases(["4", "1"], test_set, output, stand_in([]), say=lambda line: None)
    with output.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["case_id"] for row in rows] == ["4", "1"]                 # in the order the ids were given
    assert list(rows[0]) == ["case_id", "input_text", "business_name", "city", "street", "is_specific", "model"]


def test_the_command_cannot_extract_a_whole_file_and_stops_before_it_builds_a_client(extract, capsys):
    # Until Phase D, running the command with nothing after it extracted every case and overwrote the output.
    with pytest.raises(SystemExit) as stopped:
        extract.main([])
    assert stopped.value.code == 2 and "--cases" in capsys.readouterr().err   # argparse's "this option is required", and no client was built


def test_cases_from_another_file_are_never_written_to_the_committed_seed_by_default(extract, tmp_path, capsys):
    # The security review of leg D1 found this slip: --test-set pointed at the draft file with --output left out would have
    # appended unchecked draft notes to pipeline/seeds/extracted_inputs.csv, which git tracks and the repo publishes.
    drafts = tmp_path / "draft_cases.csv"
    write_cases(drafts, CASES)
    before = extract.OUTPUT.read_bytes()
    with pytest.raises(SystemExit) as stopped:
        extract.main(["--test-set", str(drafts), "--cases", "3"])
    assert stopped.value.code == 2 and "--output must name the file to write to" in capsys.readouterr().err
    assert extract.OUTPUT.read_bytes() == before                         # the committed seed was not touched, and no client was built
