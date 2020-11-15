Want to contribute? Great! First, read this page.

# If there is no issue, open one
Check if what you want to add/fix is documented in an issue. If not open one. Then, you can clone the repository and start hacking!

# Check the solution works
Before submitting your PR. You need to make sure it would pass some basic automation.
```shell script
#!/bin/bash
# install poetry
sh scripts/install.sh
# IMPORTANT: If you added additional extras to the project, you must also add them to
# `scripts/install.sh`. 
# run linting, linting will only be properly performed for python 3.7 but should also pass for python 3.8
sh scripts/lint.sh
# run testing
sh scripts/unittest.sh 
```
The tests should run and pass for python 3.7 and 3.8, across Windows, macOS and Linux. You should also add new tests for whatever issue or feature you fixed/added, and add it to `CHANGELOG.md`.

# Submit your PR
Submit a PR with changes. Your code should be well documented and efficient. Your code must pass the unit tests as well as receive an approval from at least one code owner.

# Notes:
* when running tests on macOS, hostname resolution can be very slow, to fix this, run the following line on terminal:
```shell script
scutil --set HostName $(scutil --get LocalHostName)
```