# Prompt 01: Claude Code harness (Day 1, trimmed)

Run in plan mode. Propose only; don't edit until Andres says "go ahead".

Read CLAUDE.md, docs/access/sunbiz_flr.md and the existing .claude/agents/. Then propose three changes:

1. **CLAUDE.md: add a "Commands that prove work" section.** Keep the whole file under 60 lines. Include the exact commands for:
   - activating the virtual environment: `source .venv/bin/activate`
   - running dbt from pipeline/: `cd pipeline && dbt build --select <model>`
   - running a numbered Snowflake script: `snow sql -c datum -f snowflake/NN_name.sql`
   - running pytest
   - one line saying secrets live in .env, ~/.dbt/profiles.yml, ~/.snowflake/ and *.p8 files, and must never be read, printed or edited.

2. **.claude/settings.json: block secrets.**
   - Deny rules that block Read, Edit and Write of `.env`, `~/.dbt/profiles.yml`, `~/.snowflake/**` and `**/*.p8`.
   - A PreToolUse hook on Bash that blocks (exit code 2, with a clear message) any command that mentions `.env`, `profiles.yml`, `.snowflake` or `.p8`.

3. **A Stop hook that runs cheap, offline checks only:** `ruff check src` and `dbt parse` from pipeline/.
   - No warehouse and no network.
   - Exit code 2 with the error output if either fails, so Claude must fix the problem before it can stop.
   - Check whether ruff is installed in .venv; if not, give me the install command.
   - Tell me whether `dbt parse` with the dbt Fusion engine connects to Snowflake. If it does, leave it out of the hook and say why.

Put the hook logic in `.claude/hooks/*.sh`. Comment every line of every file you propose (settings.json can't hold comments, so explain each key in the plan instead). After the plan, list the three checks I'll run to prove it works.
