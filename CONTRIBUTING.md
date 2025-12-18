# Contributing to Rehoboam Rack

Thanks for helping build the rack! This guide captures the minimum workflow so fixes and features stay consistent.

## 1. Environment setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r jetson/requirements.txt
pip install -r requirements-dev.txt
```

Optional (recommended):

```bash
pip install pre-commit
pre-commit install
```

The pre-commit hook runs `ruff --fix` before each commit to catch trivial formatting issues automatically.

## 2. Running checks locally

```bash
# Lint
python -m ruff check .

# Type checks
mypy --config-file pyproject.toml jetson

# Unit tests
python -m unittest discover -s tests -v
```

The CI pipeline executes the same commands. Running them before pushing keeps GitHub green.

## 3. Generative e-ink quick start

If you are working on the new visualizer, start here:

```bash
python -m visualizers.generative_eink.examples.pi_weight_demo --backend fake
```

For details (Pi hardware, configs, milestones) see:

- [`docs/generative_eink_quickstart.md`](docs/generative_eink_quickstart.md)
- [`docs/generative_eink_visualizer_integration.md`](docs/generative_eink_visualizer_integration.md)
- [`docs/generative_eink_next_steps.md`](docs/generative_eink_next_steps.md)

## 4. Opening pull requests

1. Create a feature branch off `main` (or the active Cursor branch if pairing with the agent).
2. Make focused commits with descriptive messages.
3. Update documentation when behavior changes (README, docs/, samples/).
4. Run the checks listed above.
5. Push and open a PR that includes:
   - Summary of changes / motivation
   - Test plan (copied output of commands above)
   - Links to relevant docs or issues

Questions? Open a GitHub Discussion or file an Issue so we can keep improving the process.
