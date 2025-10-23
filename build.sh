#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Run database migrations (if using Alembic)
# alembic upgrade head