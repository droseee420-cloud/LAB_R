# Архитектура Refraction LAB

Nginx — единственная опубликованная точка входа. `/api/*` идёт во внутренний FastAPI, `/admin*` — в отдельный Next.js admin, остальные запросы — в публичный Next.js web. PostgreSQL доступен только API. Вложения находятся в private Docker volume вне webroot; публичных URL и endpoint списка заявок нет.

```text
browser → Nginx :80/:443 ─┬→ web:3000
                           ├→ admin:3000
                           └→ api:8000 ─┬→ PostgreSQL
                                        └→ /data/uploads
```

Compose project и тома имеют стабильные имена `${COMPOSE_PROJECT_NAME}_postgres` и `${COMPOSE_PROJECT_NAME}_uploads`. Перенос Compose в `infra/compose` не создаёт новые данные. API и frontend runtime images получают только собственные исходники и runtime-файлы.

## Публичные заявки

`POST /api/brief` принимает multipart, проверяет поля и действительное содержимое JPG/PNG/WebP/GIF/PDF/DOC/DOCX/XLS/XLSX, ограничивает 6 файлов, 10 МиБ каждый и 30 МиБ суммарно. Поля собираются из React state всех трёх шагов. Signed host-only cookie ограничивает самостоятельную повторную заявку; `Idempotency-Key` делает сетевой повтор безопасным. Cookie не даёт чтения данных и не участвует в admin auth.

Запись использует транзакцию PostgreSQL и advisory locks. Файл сначала появляется в staging, затем атомарно перемещается в `objects/<lead>/<file>`, после чего коммитится БД. Ambiguous commit сохраняет байты до безопасной orphan-проверки. Telegram вызывается только после сохранения и не влияет на успех.

## Административная часть

`admins` содержит UUID, нормализованный уникальный username, Argon2id hash, active и даты. `admin_sessions` содержит только SHA256 случайного 48-байтного URL-safe token, владельца, срок и отзыв. Три аккаунта равноправны; ролей, регистрации, workflow и статусов в UI нет.

Session cookie: `HttpOnly`, `SameSite=Strict`, `Path=/api/admin`, 12 часов по умолчанию, `Secure` кроме явно включённого HTTP test mode. Login делает одинаковую Argon2id-проверку для отсутствующего и существующего username и ограничен отдельными API/Nginx rate limits. Argon2 одновременно выполняется максимум в двух потоках, чтобы малый сервер не исчерпал память. State-changing запросы требуют точный `Origin` и CSRF HMAC, связанный с session token. Приватные ответы имеют `no-store`, `nosniff`, `DENY` для frame и `no-referrer`.

Список фильтруется и пагинируется PostgreSQL. Search длиной до 200 ищет literal substring по UUID, имени, исходному/нормализованному контакту и сообщению; `%`, `_` и `\\` экранируются. Допустимы только фиксированные contact/language/sort/page sizes. Сортировка стабильна по `created_at`, затем UUID. Существующие индексы `created_at`, `(contact_method, contact_normalized)` и `lead_files.lead_id` соответствуют list/related/file-count запросам; для малого объёма отдельный полнотекстовый индекс не добавлен.

Связанные заявки вычисляются исключительно по `(contact_method, contact_normalized)`. Это не сущность клиента и не утверждение личности. Исходные поля не редактируются. `notes_version` обеспечивает optimistic concurrency; пустая заметка хранится как `NULL`, максимум 10 000 символов, HTML/Markdown не интерпретируется.

## Скачивание и удаление

Download сначала проходит auth и получает файл через `LocalStorage`; `storage_key` наружу не возвращается. UUID-структура пути, resolve и symlink checks не позволяют читать произвольный путь. Streaming держит shared advisory lock до закрытия потока.

Delete использует тот же exclusive storage lock, что upload/cleanup. Байты атомарно перемещаются в private `trash/<lead>/<file>`, затем удаляется metadata и коммитится БД. После коммита trash очищается до ответа 204. Если процесс прервался, повторяемое recovery сравнивает trash с БД: существующая metadata восстанавливает файл, отсутствующая metadata удаляет его. Поэтому заявка не исчезает, оставляя штатно доступные потерянные байты, а успешный ответ не приходит до физического удаления. Отсутствующий файл/заявка удаляются идемпотентно. Это не backup: подтверждённое удаление необратимо.

Миграции: `0001` — заявки/файлы, `0002` — notes, `0003` — notes_version, admins и sessions. `status` остаётся техническим `new` и нигде не образует workflow.
