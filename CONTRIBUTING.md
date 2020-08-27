Want to contribute? Great! First, read this page.

# If there is no issue, open one
Check if what you want to add/fix is documented in an issue. If not open one. Then, you can clone the repository and start hacking!

# Check the solution works
Before submitting your PR. You need to make sure it would pass some basic automation. For now that includes running the unit tests.
```shell script
#!/bin/bash
# install poetry
python -m pip install poetry # or your preferred method of installing poetry
python -m poetry update --lock
python -m poetry install -E redis -E rabbit -E kafka -E azure  # also include whatever new extras you added
python -m poetry run python -m pytest --cov-branch tests/
```
The tests should run and pass for python 3.7 and 3.8, across Windows, IOS and Linux. You should also add new tests for whatever issue or feature you fixed/added, and add it to `CHANGELOG.md`.

# Submit your PR
Submit a PR with changes. Your code should be well documented and efficient. Your code must pass the unit tests as well as receive an approval from at least one code owner.