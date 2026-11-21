# Search fixtures

## `jarowinkler_pairs.csv`

61 pairs of texts, each with the score Snowflake's `JAROWINKLER_SIMILARITY` function gives the pair. The test `tests/test_search.py` runs the plain-Python function `jaro_winkler_similarity` over every pair and expects the same score.

| | |
|---|---|
| **Origin** | One query against Snowflake: `select column2, column3, jarowinkler_similarity(column2, column3) from values (...)`. It read no table, so the scores depend only on the function and the two texts |
| **Captured** | Nov 20, 2026, during leg C2 of Phase C |
| **Columns** | `left`, `right`, `snowflake_score` (a whole number from 0 to 100) |

What the pairs are:

- 5 textbook pairs whose scores are published in many places, such as MARTHA and MARHTA.
- 27 pairs made to pin down one detail each: an empty text, one letter, nothing in common, a shared beginning of 1 to 5 letters, swapped letters, lower case against upper case, and very different lengths.
- 9 pairs from the committed test set (`pipeline/seeds/test_set.csv` and `extracted_inputs.csv`): the name the extraction step produced, against the registered name it should find. These are registered business names that were already in the repo.
- 20 pairs of invented business names with the differences a contractor's typing makes.

No pair holds a person's name, and no pair holds a license, filing, complaint or instrument number.

To refresh the file, run the same query again and replace the scores. Do that in a commit of its own (CLAUDE.md rule 5).
