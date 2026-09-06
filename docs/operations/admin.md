# Работа с админ-панелью

Адрес локально и при тестовом IP-деплое: `<origin>/admin`. Login возвращает только на проверенный путь внутри admin base path. После входа доступны серверный список, фильтры в URL, карточка, связанные заявки, одна заметка, download и ручное удаление. В модальном подтверждении заявки нужно ввести UUID; Escape закрывает окно, Tab остаётся внутри него. На сервере нет регистрации или reset по email.

## Три учётные записи

Команда спрашивает пароль скрыто и не принимает его аргументом:

```powershell
pnpm stack exec api python -m app.admin_cli create admin_one
pnpm stack exec api python -m app.admin_cli create admin_two
pnpm stack exec api python -m app.admin_cli create admin_three
pnpm stack exec api python -m app.admin_cli list
```

Имена нормализуются в lowercase; допустимы 3–80 ASCII letters/numbers/dot/underscore/hyphen. Пароль 12–1024 символов. `list` выводит только username и active.

```powershell
pnpm stack exec api python -m app.admin_cli disable admin_two
pnpm stack exec api python -m app.admin_cli enable admin_two
pnpm stack exec api python -m app.admin_cli reset-password admin_two
pnpm stack exec api python -m app.admin_cli cleanup-sessions
```

Disable и reset-password отзывают все сессии пользователя. Logout отзывает текущую. Enable сам пароль не меняет. Истёкшие/отозванные записи безопасно чистятся повторяемой командой.

Для первого SSH-деплоя локальный исключённый из Git `scripts/deploy/config.local.json` может содержать `initial_admins` — ровно три объекта `username/password`. Клиент отправляет JSON по SSH stdin в одноразовую команду; данные не попадают в release, `.env`, settings, process arguments или log. Bootstrap создаёт отсутствующих и никогда не меняет пароль существующего. После первого успеха удалите plaintext из локального JSON; дальнейший reset выполняйте явной CLI-командой.

## API

| Метод | Endpoint | Назначение |
|---|---|---|
| POST | `/api/admin/login` | username/password, session cookie |
| GET | `/api/admin/session` | текущий username и CSRF token |
| POST | `/api/admin/logout` | отзыв сессии, Origin + CSRF |
| GET | `/api/admin/leads` | q/page/page_size/contact_method/language/has_files/date_from/date_to/sort |
| GET | `/api/admin/leads/<uuid>` | detail, files, related |
| PATCH | `/api/admin/leads/<uuid>/notes` | notes + notes_version, конфликт 409 |
| GET | `/api/admin/files/<uuid>/download` | authenticated stream, attachment disposition |
| DELETE | `/api/admin/files/<uuid>` | необратимое удаление файла |
| DELETE | `/api/admin/leads/<uuid>` | необратимое удаление заявки и файлов |

Mutation отправляет `Origin` и `X-CSRF-Token`. Ошибки имеют `{ok:false, code, error}`. API не возвращает storage path, password/session/browser/idempotency/payload hashes. Вложения не доступны через публичный сайт.

## Отдельный поддомен

До домена оставьте `ADMIN_BASE_PATH=/admin`, `ADMIN_HOST=admin.invalid`, `ADMIN_ORIGIN` пустым: admin origin совпадает с `PUBLIC_URL`. Для будущего `admin.example.com` пересоберите admin с пустым base path, задайте `ADMIN_HOST=admin.example.com`, `ADMIN_ORIGIN=https://admin.example.com`, добавьте DNS и сертификат этого hostname. Nginx направит весь host во внутреннее admin-приложение; API останется same-origin. Проверяйте cookie Secure и TLS по [инструкции деплоя](deployment.md).
