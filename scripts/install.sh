# install poetry and the dev-dependencies of the project
python -m pip install poetry
python -m poetry update --lock
python -m poetry install -E redis -E rabbit -E kafka -E azure