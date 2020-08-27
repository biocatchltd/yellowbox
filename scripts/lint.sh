# run various linters
flake8 --max-line-length 120 yellowbox tests
python -c "import sys; sys.exit(sys.version_info < (3,8,0))"
res=$?
if [ "$res" -eq "0" ]
  then
    echo "pytype not run, please run in python 3.7"
  else
    pytype --keep-going yellowbox
fi

