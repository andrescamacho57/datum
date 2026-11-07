# Datum — Interview Answers

Defensible answers to the questions this project invites.
Rule: lead with the decision and the reason, then name the tradeoff.
**Added to each session.** Practice out loud — recognizing an answer isn't the same
as being able to say it.

---

## The 30-second project pitch

> At Amex I worked credit risk for small business cards, so I've seen how defaults
> ripple: a business doesn't pay, and the people downstream of it eat the loss.
> Small trade contractors are a big part of that downstream. A plumber or roofer
> takes a commercial job without any real way to check who they're working for.
>
> So I'm building Datum, a risk and verification tool. Before the job, it answers:
> is this a real, active company, and what's on the public record against it? It
> pulls Florida's full corporate register from the state's bulk files, loads it into
> Snowflake, and dbt models it into a searchable company table with tests on the
> grain. Every line of a report links back to its official record.
>
> It's pre-launch: the pipeline is proven end to end, and I'm loading the full
> 13-million-record register now while doing customer outreach in parallel.

**Why it works:** domain credibility first, a real problem, engineering as the means.
Honest about stage — "pre-launch" is a strength when the next sentence shows motion.

**Never say** "credit check" or "credit product." It's risk and verification of
*businesses* — and the distinction is legal (FCRA), not just wording.

---

## "How do you inspect data before loading it?"

**This was asked in a real interview. It's one of the strongest stories in the
project — lead with it for data quality, debugging, or attention to detail.**

> Before I spend warehouse compute on a file, I check it on my laptop in about five
> minutes. Four questions: is it complete, is it shaped the way the documentation
> says, is it what I think it is, and what's going to surprise the loader.
>
> On Datum, the source is Florida's corporate register — fixed-width text files, no
> delimiters, every field at a set character position. First file was a daily
> update. I ran `wc -l` and got 834 lines. Then `head -c` to look at the first
> record, and `awk` to check every line length. The state's layout says records are
> 1436 characters, and awk agreed. But Snowflake, after loading, said 1440. So I
> dumped the raw bytes with `od -c` and found four NUL bytes padding every record —
> zero bytes that aren't in the documentation. macOS awk stops reading at a NUL, so
> it hid them.
>
> Then I spot-checked the field positions on a handful of records against the
> published layout — document number, status, filing type — before writing a single
> line of parsing code.
>
> For the quarterly full snapshot, 1.7 GB zipped, I listed the archive with
> `unzip -l` before extracting, because it unpacked to 18.7 GB on a nearly full disk.
> I divided each file's size by its line count, which in a fixed-width file gives the
> exact line length: 1442 bytes, versus 1441 for the daily file. That told me the
> quarterly files use Windows line endings — a carriage return the loader would keep.
> I predicted the loader would keep that carriage return, so lines would come in at
> 1441. They came in at 1440 — Snowflake strips the whole Windows line ending. Wrong
> prediction, caught by checking, and the length check tolerated either case anyway.
> And every one of the ten files loaded exactly file size divided by 1442 rows — zero
> lost, zero split.
>
> Two of the ten files had identical sizes and line counts, and I suspected a
> duplicate. An `md5` checksum disproved it — and after upload, their gzipped sizes
> differed too, which identical files can't do. And then I realized why: in a
> fixed-width file, the same line count forces the same size, so it was one
> coincidence, not two.
>
> Everything I learn gets encoded so it can't regress: a well-formed flag in staging
> for damaged lines, unique and not-null tests on the company ID, and an
> accepted-values test on the status field — which also catches any shift in field
> positions, since a shifted parse puts junk where A or I should be.

**Why it works:** concrete, ordered, and every step has a reason. Shows the habit of
verifying instead of trusting, using cheap local tools before expensive cloud ones,
reasoning from arithmetic, disproving your own hypothesis, and turning a finding
into a permanent test.

**The short version (if they want 20 seconds):**
> Completeness, shape, identity, surprises. Line counts against what the source says,
> look at the raw bytes, check field positions against the documentation, checksum
> anything suspicious — all on my laptop before the warehouse. Then whatever I find
> becomes a test.

**Likely follow-up — "What would you automate?"**
> The checks become a pre-load script: expected line count and line length per file
> type, checksum recorded with the load, and the load refuses a file that fails. The
> dbt tests stay as the second line of defense after the load.

---

## "How do you know the pipeline is right, not just green?"

> Known-answer tests. I look a company up by hand on the state's website, write down
> its document number, name and status, then query my mart by that exact number and
> compare every field. I did it for a company from the daily file and for one filed in
> 1998 that only exists in the quarterly snapshot. Both matched — which proves the
> download, the load, the position-based parsing, and the newest-version rule in one
> shot.
>
> I select by the ID, not the name, on purpose. Names repeat — the state's own search
> shows several "FERGUSON LLC"s. Finding a company from what a contractor types is a
> different problem, matching, and that gets its own 50-name evaluation set.

**Why it works:** separates "the data is right" from "the search is right" — two
different claims that need two different tests.

---

## "How do you evaluate the LLM part of your system?"

> Search is a chain: an LLM extracts the business name and city from what the contractor
> typed, then plain SQL matches it against 13 million registered names. I built a small
> test set with known answers first and scored a no-LLM baseline: 60% top-1, 80% with a
> five-result shortlist. Then I added the extraction step and scored again: 90% recall at
> five. It fixed cases string math can't — "ferguson ac" became "Ferguson Air
> Conditioning" — but it also broke one: it read "really good beer" as a description and
> dropped the name. I only caught that because I check the extraction output separately
> from the final score. I froze the model's outputs to a file so scores stay comparable,
> and I stopped tuning the prompt after two rounds, because tuning on your own test set
> inflates it.

**Why it works:** baseline first, component-level evaluation, an honest regression, and
awareness of overfitting the eval. → Chip Huyen on evaluation; *Building Effective Agents*
(the LLM does one narrow step in a fixed workflow).

**Also answers:** "Have you worked with REST APIs in Python?" — the extraction is an
SDK call to Anthropic's REST API; the key lives in an environment variable, never in code.

---

## "Tell me about a change you decided NOT to ship"

> I tested two improvements to Datum's company search against my baseline. One let vague
> notes still search when a registered name matched exactly — it fixed "really good beer"
> but turned "the pool guy" into a confident match to a company literally named POOL LLC.
> Same score as before, 6 out of 10, but it traded a cheap error for an expensive one.
> Asking a contractor "can you add the city?" costs seconds; showing the wrong company as
> fact costs trust. So I kept the simpler version. Credit risk taught me that — you don't
> judge a decision model by accuracy alone, you weigh what each kind of mistake costs.
> I also saw that at 10 test cases each change flipped about one case either way, so the
> right move was to stop tuning and grow the test set.

**Why it works:** shows judgment over metric-chasing, ties back to the Amex background,
and knows the limits of a small evaluation set.

---

## "Why bulk files instead of an API or scraping?"

> The state publishes the entire register as bulk files over SFTP, free, with record
> layouts — it's the intended channel for this. There's no official API, and the
> search website sits behind a bot challenge; the fictitious-name site explicitly
> disallows automated access. Bulk is the most complete source and the compliant one.
>
> I do use APIs where a source offers one — court records come next, through
> CourtListener's REST API. I just don't force a pattern where a better one exists.

**Why it works:** shows judgment about ingestion patterns *and* awareness of terms of
use — which matters for a product reselling public data.

---

## "Why is the raw table one column?"

> The files are fixed-width, and Snowflake has no fixed-width loader. So raw stores
> each line exactly as received — one VARCHAR, plus the file name and load time —
> and dbt cuts it into columns. If I ever get a position wrong, I fix one SQL file and
> rebuild. Nothing gets reloaded, and raw is always a faithful record of what the
> state sent.

**Tradeoff:** every query on raw is unreadable. That's fine — nobody queries raw;
they query staging.

---

## "Why did you flag bad rows instead of filtering them?"

> The state warns that stray line breaks can split a record. In staging I compute
> `is_well_formed` — true when the line is at least the documented length — instead
> of deleting short lines. A deleted row is invisible: you can't count it or notice
> the problem growing. A flag can be counted and investigated, and the mart filters
> on it in one visible place.

---

## "How do you make sure there's exactly one row per company?"

> The mart's grain is one row per document number, the state's ID. I deduplicate
> with `QUALIFY ROW_NUMBER()` partitioned by document number, newest first, and a
> `unique` test on the ID enforces it on every build. If the dedupe logic ever breaks,
> the build fails rather than shipping two answers for one company.
>
> One thing I caught in design: I was ordering "newest" by load time — when *I*
> loaded it. If I load an older quarterly snapshot after a newer daily file, that
> ranks stale data first. The fix is ordering by a date from the state's own record.

**Why it works:** shows the test enforcing the grain, and self-correction on a subtle
bug before it shipped.

---

## "How do you control Snowflake costs on a solo project?"

> Three layers. An X-Small warehouse, the smallest size. Sixty-second auto-suspend,
> so it stops billing a minute after the last query. And a resource monitor that
> suspends the warehouse at ten credits a month — a hard stop, not an alert I might
> miss. And I make sure every session runs on that warehouse, because the account's
> default warehouse isn't under the monitor.
>
> Storage is nearly free; compute is where the money goes. So I inspect files on my
> laptop before loading, and staging models are views, which cost nothing until
> queried.

---

## "Where does AI fit in Datum?"

> Workflow first. Parsing, deduping, and joining are predictable, so they're plain
> SQL — cheap, fast, identical every run. A model call comes in only where judgment
> is needed: deciding whether two slightly different names are the same company. And
> an agent only for the long tail of messy lookups, behind human review.
>
> Nothing shows to a contractor as fact until matching hits 90% on a 50-name
> hand-checked test set. I build the evaluation before the feature.

**Why it works:** shows restraint with AI — the opposite of bolting an agent onto
everything. References: *Building Effective Agents* (least autonomy that works);
Chip Huyen on evaluation (eval set first).

---

## "Tell me about a mistake you made"

> Early on I designed the staging area with one stage, subfolders, and a pattern
> filter to keep daily and quarterly files apart. It worked, but it was more moving
> parts than the problem needed. The simpler answer was one stage per file type and a
> plain COPY. I switched, and now I hold myself to a rule: the simplest correct
> solution, and complexity only for a problem I actually have — and I say which one.
>
> Smaller one: my first dbt build failed because I put template braces inside a SQL
> comment. dbt renders templates everywhere, comments included. Read the error,
> fixed it, and learned how the compile step actually works.

---

## "How does dbt authenticate to Snowflake?"

> Key-pair authentication. A private key on my laptop, outside the repo; the public
> key registered on my Snowflake user. dbt and the Snowflake CLI sign in with the key
> — no password anywhere. Credential files never go in git.

---

## "Isn't this just a side project?"

> It's a product with a launch plan: scoped to Florida and commercial clients, with
> paying users as the gate for expanding to more states. I'm doing customer discovery
> in parallel with the build. The engineering is real either way — 13 million
> records, tested models, cost controls — but the point is a contractor not getting
> stiffed.

---

## What I'd do differently

- Write the pre-load checks as a script from day one, instead of running them by hand.
- Order "newest" by the source's own date from the start, not by load time.
- Install the CLI tools (snow) before the first load instead of using the web upload.

---

## "How do you work safely with an AI coding agent?"

**Decision:** I give it rules, locks and an automatic inspector, and I keep review for the parts that matter.
- **Rules** in CLAUDE.md: the exact commands that prove work runs.
- **Locks:** deny rules and a pre-command hook block any access to secrets (API key, Snowflake key, dbt credentials).
- **Inspector:** a Stop hook runs the linter and `dbt parse` before the agent can say "done." If they fail, it has to fix them.

**Why:** rules are requests, hooks are code. Anything that must never fail goes in code. The checks are
offline and free, so they can run on every turn. I *proved* `dbt parse` doesn't connect to Snowflake by
running it against a fake account: it still succeeded.

**Tradeoff:** the secrets hook matches text, so it's a guardrail, not a security boundary. I tested it
with 13 cases and documented what it can't catch.

---

## "How do you link a lien to the right company when the record has no ID?"

**Decision:** I link on normalized name plus ZIP code, and only show a lien as fact when the link is
CONFIRMED (same name without suffixes and same ZIP, or the only company with that name). Anything weaker
shows as "possible match: verify."

**Why:** I inspected the state's lien files before building. They carry no Sunbiz document number, no tax ID
and no amount. And accusing the wrong company of an IRS lien is the most expensive error the product can make.

**Tradeoff:** coverage. Some real liens won't link, so I measure CONFIRMED coverage and hand-check
20 links, with zero wrong allowed.

