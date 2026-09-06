# Refraction LAB

Монорепозиторий сайта, админ-панели и API:

```text
apps/web       публичный Next.js-сайт и форма
apps/admin     отдельная Next.js-админка
apps/api       FastAPI, SQLAlchemy, Alembic и API-тесты
infra          Compose, Nginx и Dockerfiles
scripts        локальный запуск, SSH-деплой и проверки
tests/e2e      браузерные сценарии всего стека
docs           архитектура и эксплуатация
```

`pnpm-lock.yaml` — рабочий lock-файл. Существующий локальный `package-lock.json` не используется и сохранён без изменений. `prompt/`, `.env`, `*.local.json`, данные, ключи и тестовые артефакты исключены из Git, Docker context и release archive.

## Основные команды

```powershell
pnpm install --frozen-lockfile
pnpm stack:up       # весь production-подобный стек: http://localhost:8080
pnpm stack:down     # тома PostgreSQL/uploads сохраняются
pnpm test:quick     # lint, types, pytest без внешних стендов, production builds
pnpm test:full      # Compose + web/admin Playwright + persistence/TLS/failure checks
```

Публичный сайт: `http://localhost:8080/`. Админка: `http://localhost:8080/admin`. При запуске компонентов отдельно используйте `pnpm --filter @lab/web dev`, `pnpm --filter @lab/admin dev` и команды API из [инструкции тестирования](docs/operations/testing.md).

Три администратора создаются только CLI или одноразовым stdin-bootstrap; регистрации в web нет. Пример интерактивного создания в работающем стеке:

```powershell
pnpm stack exec api python -m app.admin_cli create admin_one
pnpm stack exec api python -m app.admin_cli create admin_two
pnpm stack exec api python -m app.admin_cli create admin_three
pnpm stack exec api python -m app.admin_cli list
```

Управление учётными записями, API и необратимое удаление: [операции админки](docs/operations/admin.md). Архитектура и гарантии хранения: [описание системы](docs/architecture/system.md). Windows → Ubuntu, IP/HTTP и будущий домен/HTTPS: [деплой](docs/operations/deployment.md). Фактически выполненные проверки: [verification](docs/operations/verification.md).
