#!/bin/bash

echo "BUILD START"

# Install dependencies
python3 -m pip install -r requirements.txt

# Run migrations
python3 manage.py migrate --noinput

# Collect Static Files
python3 manage.py collectstatic --noinput --clear

echo "BUILD END"
