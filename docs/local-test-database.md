# Local test database (portable PostgreSQL on port 5439)

The test suite requires a real PostgreSQL — `TestingConfig` rejects SQLite. On the
Windows dev box a **portable PostgreSQL** lives at `~/postgresql` and runs on
**port 5439** (not the default 5432), with user `postgres` and trust auth (no
password). These commands manage it.

> PowerShell examples below (the box's default shell). From Git Bash, call the
> executables directly, e.g. `~/postgresql/bin/pg_ctl.exe -D ~/postgresql/data status`.

## Start the server

```powershell
cd "$HOME\postgresql"
& "$PWD\bin\pg_ctl.exe" -D "$PWD\data" -l "$PWD\logfile" start
```

## Check status

```powershell
cd "$HOME\postgresql"
& "$PWD\bin\pg_ctl.exe" -D "$PWD\data" status
```

## Stop the server

```powershell
cd "$HOME\postgresql"
& "$PWD\bin\pg_ctl.exe" -D "$PWD\data" stop
```

## Connect via psql

```powershell
cd "$HOME\postgresql"
& "$PWD\bin\psql.exe" -U postgres -p 5439
```

## Create the application database

```powershell
& "$PWD\bin\psql.exe" -U postgres -p 5439 -c "CREATE DATABASE flask_app;"
```

## Troubleshooting — is the port up?

```powershell
netstat -ano | findstr :5439
```

## Key details

- **Port:** 5439 (not the default 5432)
- **User:** `postgres` (trust auth, no password)
- **App database URL:** `postgresql://postgres@localhost:5439/flask_app`

## Running the test suite against it

Tests read `TEST_DATABASE_URL` (see `tests/conftest.py`). Use a **separate**
database — `archie_test` — so a test run never touches app data:

```bash
# one-time: create the test database
~/postgresql/bin/psql.exe -U postgres -p 5439 -c "CREATE DATABASE archie_test;"

# each run
export TEST_DATABASE_URL="postgresql://postgres@127.0.0.1:5439/archie_test"
pytest -q
```

`conftest.py`'s `_schema` fixture runs `db.create_all()`, which creates only
**missing tables**. When a model gains a **column** (e.g. a new tenancy
`organization_id`), bring the test database up to the models the same way the
deploy does — run reconcile-schema against it once:

```bash
FLASK_CONFIG=testing DATABASE_URL="$TEST_DATABASE_URL" \
  python -c "from app import create_app, db; \
             app=create_app('testing'); \
             from app.commands.reconcile_schema import _reconcile; \
             app.app_context().push(); print(_reconcile(dry_run=False))"
```

Then re-run `pytest -q`.
