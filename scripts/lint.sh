# run various linters
python -m poetry run flake8 --max-line-length 120 yellowbox/ tests/
# disabled for now python -m poetry run mypy . --ignore-missing-imports