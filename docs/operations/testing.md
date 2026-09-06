# Разработка, quick/full проверки и CI

## Отдельные компоненты

```powershell
pnpm install --frozen-lockfile
py -3.13 -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements-dev.txt
pnpm --filter @lab/web dev       # 127.0.0.1:3000
pnpm --filter @lab/admin dev     # 127.0.0.1:3001/admin
```

API требует PostgreSQL и переменные из `.env.example`; модуль `.env` сам не читает. Из `apps/api`: `python -m alembic upgrade head`, затем `python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log`. Для web/admin dev задайте `API_INTERNAL_URL=http://127.0.0.1:8000`; полноценный same-origin путь даёт Compose.

## Канонические команды

`pnpm test:quick` запускает lint/typecheck обоих frontend, Ruff, unit/API tests без Compose/SSH и обе production-сборки. Integration tests PostgreSQL добавятся, если задан `TEST_DATABASE_URL`; имя disposable database обязано содержать `test`.

`pnpm test:full` создаёт случайный пароль трёх синтетических администраторов только в памяти процесса, поднимает production Compose, запускает все web/admin Playwright, persistence/private ports/rate/size checks, временный TLS, реальные failure injections Docker/Alembic/health и tooling pytest. Нужны Docker Desktop/Linux containers, Python dev dependencies и Playwright Chromium; локально можно задать `E2E_BROWSER_CHANNEL=chrome`.

```powershell
$env:PYTHON_BIN='apps/api/.venv/Scripts/python.exe'
$env:E2E_BROWSER_CHANNEL='chrome'  # если Playwright Chromium не установлен
pnpm test:quick
pnpm test:full
```

Backend tests покрывают auth, одинаковые login errors, Argon2id/session hash, revoke/expiry, CSRF/origin, rate limit, фильтры/пагинацию, related, notes 409, download bytes/filename, symlink rejection, отдельное/полное/idempotent/concurrent deletion, DB/disk/ambiguous commit и recovery. Fixture очищает только отдельную test-БД и использует временное хранилище. Telegram и внешние сервисы мокируются.

Playwright идёт через Nginx и реальные PostgreSQL/private volume: публичная форма, 30 МиБ, preview/retry/storage; admin login/refresh/safe redirect/search URL/detail/XSS-as-text/note conflict/download/delete confirmation/logout/mobile/empty/error. Синтетические данные автоматически не являются production cleanup.

## CI

`.github/workflows/quick.yml` запускается на pull request и push только `main`, с path filters; docs-only push его не запускает. В нём нет Docker Compose, browser и SSH. `.github/workflows/full.yml` доступен только вручную (`workflow_dispatch`) и содержит Compose/browser плюс отдельный Windows helper job. Production autodeploy отсутствует. YAML/triggers и отсутствие тяжёлых quick-команд проверяются pytest-тестом.
