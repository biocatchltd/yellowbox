# run various linters
python -m poetry run flake8 --max-line-length 120 yellowbox tests
python -c "import sys; sys.exit(sys.version_info >= (3,8,0))" &&
 python -m poetry run pytype --keep-going yellowbox