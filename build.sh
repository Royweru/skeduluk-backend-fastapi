#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt && alembic upgrade head

# Run database migrations (if using Alembic)
# alembic upgrade head