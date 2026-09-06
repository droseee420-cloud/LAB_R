# Windows → Ubuntu deployment

Цель: Ubuntu 22.04/24.04, root или sudo, проверенный SSH host key. Скрипт не меняет firewall и не обновляет ОС целиком. При отсутствии Docker ставит Engine/Compose из официального репозитория. Тома `refraction_postgres`/`refraction_uploads` и `COMPOSE_PROJECT_NAME=refraction` сохраняют прежние production-данные после новой структуры.

Скопируйте `scripts/deploy/config.example.json` в исключённый из Git `scripts/deploy/config.local.json`. Укажите host/auth/fingerprint. Для сервера с 1 ГБ RAM используйте `build_mode: local`; нужны Docker Desktop и linux/amd64. `remote` собирает на Ubuntu.

```powershell
.\scripts\deploy\deploy.cmd -DryRun
.\scripts\deploy\deploy.cmd
```

Dry-run проверяет config и allowlisted archive без SSH. Архив содержит `apps`, `infra`, нужные `scripts/docs` и workspace inputs; исключает `.git`, `prompt`, `.env*`, `*.local.json`, private keys, data, node_modules, venv и test artifacts. npm lock не входит.

Deployment: verified SSH → protected temp upload → unique release → Compose config → images → DB health → Alembic → services health → optional three-account stdin bootstrap → orphan/trash recovery → atomic `current`, сохранение `previous`. Пароль PostgreSQL и COOKIE_SECRET генерируются на сервере один раз и остаются в `shared/settings.json`/`app.env` 0600. SSH и initial admin credentials туда не попадают. Ошибка до `ready` не меняет symlink; универсального автоматического Alembic downgrade нет.

```text
/opt/refraction-lab/
  shared/       server settings, persistent secrets
  releases/     source and release.env per release
  current       latest successful release
  previous      preceding successful release
Docker volumes: refraction_postgres, refraction_uploads
```

Диагностика без публикации environment:

```sh
cd /opt/refraction-lab/current
docker compose --project-directory . --env-file release.env -f infra/compose/compose.yaml ps
docker compose --project-directory . --env-file release.env -f infra/compose/compose.yaml logs --tail 80 api admin proxy
docker compose --project-directory . --env-file release.env -f infra/compose/compose.yaml exec api python -m app.admin_cli list
```

Rollback переключает код/`release.env` на `previous`, выполняет `config --quiet`, совместимую миграцию вперёд и `up --wait`. Не используйте `down -v`, prune или случайный project name. Если новая миграция несовместима со старым кодом, подготовьте forward fix; автоматический downgrade может уничтожить данные.

Для HTTP по IP `PUBLIC_URL=http://IP`, `HTTP_TEST_MODE=true`, admin доступен `/admin` и cookie намеренно без Secure. Это тестовый режим. Для HTTPS подготовьте `fullchain.pem`/`privkey.pem`, читаемые UID/GID 101, задайте `PUBLIC_URL=https://domain`, `HTTP_TEST_MODE=false`, `TLS_CERT_DIR`. Compose автоматически добавит `infra/compose/https.yaml`: HTTP redirect, TLS 1.2/1.3, HSTS и Secure cookies. DNS/subdomain admin описан в [admin operations](admin.md).

Production `refraction.info` использует сертификат Certbot/Let's Encrypt для apex и `www`. Certbot хранит оригиналы в `/etc/letsencrypt/live/refraction.info`; hooks из `scripts/deploy/tls` копируют их с ограниченными правами в `/opt/refraction-lab/shared/tls` и перезапускают только proxy. HTTP и `www` перенаправляются на `https://refraction.info`. Проверка продления: `certbot renew --dry-run --no-random-sleep-on-renew`.

История фактических production-проверок сохранена в [verification](verification.md).
