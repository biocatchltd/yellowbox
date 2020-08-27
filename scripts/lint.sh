# run various linters
python -m poetry run flake8 --max-line-length 120 yellowbox/ tests/
python -m poetry run pytype --keep-going yellowbox