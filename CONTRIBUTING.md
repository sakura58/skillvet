# Contributing

Thanks for taking a look. This project is deliberately small: one dependency-free package,
one test suite, no build step beyond `pip install -e .`.

## Setup

```bash
git clone https://github.com/sakura58/skillvet.git
cd skillvet
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Expectations

- Every check needs a test. A rule without a failing fixture is a guess, not a rule.
- New findings need a stable code in `RULES` (`src/skillvet/rules.py`) and a row in the
  README table.
- Keep the package dependency-free. If a check needs YAML, write the twenty lines instead of
  adding PyYAML.
- Anything arguable belongs in `warning` or `info`; only spec violations and concrete
  security problems are `error`.
- No network access, no telemetry, no writing to the scanned tree.

## Adding a rule

1. Add `CODE: (severity, description)` to `RULES`.
2. Emit a `Finding` from the relevant `_check_*` function, with a line number when possible.
3. Add a case to `tests/test_rules.py`.
4. Run `skillvet examples/release-notes --fail-on warning` and confirm the clean example stays
   clean.

## Style

`black`-compatible formatting, 88 columns, type hints on public functions. No formatter is
enforced in CI yet; keep the diff readable and you will be fine.
