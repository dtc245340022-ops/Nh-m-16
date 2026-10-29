#!/bin/sh
set -eu

python -c "from init_db import create_database; engine = create_database(); engine.dispose()"
exec uvicorn main:app --host 0.0.0.0 --port 8001
