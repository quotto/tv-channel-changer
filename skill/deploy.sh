#!/bin/bash

rm function.zip
cd .venv/lib/python3.8/site-packages
zip -r9 ${OLDPWD}/function.zip . >/dev/null 2>&1
cd ${OLDPWD}
zip -g function.zip lambda_function.py utils.py certificate/*
aws lambda update-function-code --function-name tv-search --zip-file fileb://function.zip --profile lambda-deployer --region ap-northeast-1