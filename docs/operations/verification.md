# Фактические проверки

Проверки выполнены 5 сентября 2026 года. Исходники не коммитились и не отправлялись в Git.

> Этот раздел сохраняет историю production-проверки предыдущего этапа. Новая админ-панель и структура проверены локально 6 сентября и на production не развёртывались.

## Автоматические проверки

| Проверка | Фактический результат |
|---|---|
| `python -m pytest -q` с отдельной PostgreSQL и временным дисковым хранилищем | 95 passed на Windows/Python 3.13; 3 Linux-only теста пропущены на Windows |
| `test_remote_pipeline.py` в Linux-контейнере | 3 passed: отказ сборки, миграции, healthcheck; сохранены указатель релиза и секреты |
| `pnpm test:e2e`, production Compose, установленный Chrome | 6 passed: оба контакта, поля всех шагов, превью/удаление, потеря ответа/повтор, блокировка storage/cookie, ровно 30 МиБ, mobile/private routes |
| `python -m scripts.verify.compose` | После пересоздания DB/API/frontend/proxy сохранены 17 синтетических заявок и 21 файл, SHA256 совпали; приватные порты, 413 и 429/Retry-After, защита forwarded headers подтверждены |
| `python -m scripts.verify.https` | Реальное TLS-соединение с доверенным временным сертификатом: Secure/HttpOnly/SameSite cookie, HSTS, HTTP redirect; HTTP-стек восстановлен |
| `python -m scripts.verify.deploy-failures` | Реальные ошибки Docker build, Alembic с отсутствующей ревизией и Docker healthcheck переданы executor как ошибки |
| SSH loopback integration | Настоящие handshake с паролем и ключом; неверный пароль/ключ и недоверенный host key отклонены; ненулевой exit status обработан |
| Специальные символы конфигурации | 5 вариантов проверены реальным Compose parser; сочетание кавычки/слеша/$ отдельно проверено внутри контейнера |
| `pnpm lint`, `pnpm typecheck`, Ruff, `git diff --check` | Пройдены |
| Docker build API/frontend | Пройдены; Next production build, TypeScript, static generation успешны |
| `scripts/deploy/deploy.cmd -DryRun` | Пройден на Windows с Python 3.14; изолированное окружение создано, архив проверен |

На этом компьютере Python 3.13 для backend-тестов запускался через локальный `.tools/python/python.exe`; Docker использовал локальный `DOCKER_CONFIG`. Это особенности проверочного окружения, не требования приложения. При недоступности стандартного pytest temp-root использовался отдельный `--basetemp .data/pytest-final-fixed`.

Найдены и исправлены в ходе реальных проверок: потеря полей предыдущих шагов, конфликт `id=contact` с footer, экранирование специальных символов dotenv. В тестовом стенде отдельно исправлены преждевременное закрытие SSH transport, сохранение cookie самим Playwright route.fetch и вытеснение большого запроса из Chromium inspector cache. Два предупреждения deprecated API в Starlette TestClient не мешают тестам; runtime API их не использует.

## Сервер

По отдельному запросу владельца выполнен фактический деплой на Ubuntu 24.04.4, `http://77.222.35.162`. Проверенный SSH-ключ использован из локального профиля; секреты в репозиторий и релиз не передавались. Docker Engine/Compose установлен через официальный Ubuntu-репозиторий. Из-за 1 ГБ памяти сервера образы собираются на Windows в Docker (`build_mode: local`) и передаются по SSH.

Первый релиз: `20260905T162712Z-e05a9547`. Все четыре сервиса healthy; наружу опубликован только Nginx на порту 80. Серверные настройки имеют права 0600. В runtime `/app` API/frontend не обнаружены `prompt`, `.env`, SSH/private key или `deploy.local.json`.

Через настоящий публичный сайт в Chrome отправлена одна заявка `Synthetic deployment test` с адресом `deployment-test@example.org` и PNG. Получен успех; ID присутствует в PostgreSQL, SHA256 приватного файла совпадает с исходным тестовым изображением. Эта явно помеченная тестовая заявка оставлена для проверки сохранности обновления.

Повторный деплой выполнен штатным Windows-скриптом, который теперь находится в `scripts/deploy/deploy.cmd`. Релиз того этапа — `20260905T164049Z-5fc2779d`; `previous` указывал на первый релиз. После обновления совпали список ID заявок, SHA256 всех файлов и хеш серверных секретов. Все сервисы healthy. Проверка публичной страницы загрузила 13 ресурсов, изображения и шрифты без ошибок браузера. На сервере оставлена одна тестовая заявка с одним PNG; локальные массовые проверки на сервер не запускались.

После проверок локальный Compose возвращён к обычным rate limits, временный отдельный PostgreSQL для pytest остановлен.

## Границы проверки

- GitHub Actions подготовлен, но удалённый CI не запускался: commit/push не выполнялись.
- На реальном сервере проверен Ubuntu 24.04; Ubuntu 22.04 и non-root sudo не проверялись на отдельной ОС. SSH password flow проверен loopback-сервером; реальный сервер использует ключ.
- Реальный сервер работает в согласованном HTTP-тестовом режиме по IP. Домен и доверенный production-сертификат не предоставлены; HTTPS проверен локально.
- Telegram отключён: bot token/chat ID не предоставлены. Успех, таймаут и ошибки Telegram проверены без обращений к реальному сервису.
- Отказы стадий проверены изолированными инъекциями и фактически неуспешными локальными Docker/Alembic командами. Рабочий сервер намеренно не выводился из строя для этих сценариев.
- Антивирус, резервные копии и автоматическое удаление принятых заявок не входили в тот этап.

## Админ-панель и реорганизация — локальная проверка 6 сентября 2026

До изменения прошли существующие lint/typecheck и 26 быстрых тестов (3 Linux-only skip). После физического переноса запущен прежний Compose project `refraction`; миграция `0003` применена к тому же PostgreSQL volume. Снимок до/после подтвердил сохранность ID и notes всех 17 существующих заявок и SHA256 всех 21 вложений. Имена volumes явно закреплены как `refraction_postgres` и `refraction_uploads`.

Итоговый `pnpm test:full` пройден полностью:

- lint и TypeScript обоих Next-приложений, Ruff, Compose config и production-сборка трёх Docker-образов прошли;
- в disposable Linux-контейнере прошли 94 API/security/integration теста; на Windows локально прошли 92, а 2 symlink-теста пропущены из-за запрета ОС на создание symlink;
- Playwright: 8 сценариев прошли через Nginx/Next/FastAPI/PostgreSQL/private volume, из них 2 для admin и 6 для публичной формы;
- admin E2E проверяет настоящий вход, URL-фильтры/refresh, detail, безопасный вывод текста, конфликт заметок, точные bytes и Unicode filename при скачивании, подтверждение и удаление файла/заявки, logout, анонимный refresh, safe redirect, error/empty/mobile и security headers;
- после пересоздания контейнеров сохранены 32 заявки и 38 файлов с теми же SHA256; runtime-образы не содержат тесты, `prompt`, `.env` и исходники соседнего Next-приложения; наружу не публикуются DB/API/web/admin;
- TLS-проверка подтвердила public cookie и admin cookie с `Secure`/`HttpOnly`, для admin также `SameSite=Strict`, `Path=/api/admin`, `no-store` и `DENY`; HSTS и HTTP→HTTPS redirect прошли;
- 25 tooling-тестов прошли, 3 Linux-only проверки server release pipeline пропущены на Windows; отдельная Linux-проверка фактическими сбоями подтвердила передачу ошибок Docker build, Alembic и healthcheck;
- deploy dry-run проверил allowlist-архив без SSH-подключения и удалённых изменений;
- первоначально реальный SSH/production deployment для этого этапа намеренно не выполнялся.

После отдельного запроса владельца 6 сентября выполнен production-деплой релиза `20260906T105344Z-ccfc5d6f` на тот же Compose project и постоянные volumes. Миграция и healthchecks прошли, три администратора созданы одноразовым stdin-bootstrap. Публичная страница `/admin` и вход всех трёх учётных записей проверены через `http://77.222.35.162`; admin API вернул сохранённую заявку предыдущего релиза. Пароли остаются только в исключённом из Git локальном deployment config.

Позднее 6 сентября по запросу владельца развёрнут релиз `20260906T111523Z-a868dce9` с английской клиентской валидацией формы, явно необязательным `Product or company link` и прямым возвратом с экрана успешной отправки. До деплоя прошли lint, typecheck, production build и 7 сценариев формы (одна исправленная проверка повторена отдельно после уточнения локатора). После деплоя два Playwright-сценария прошли непосредственно на публичном IP: английские ошибки и пустая ссылка, а также закрытие экрана `Received` менее чем за секунду. Новая production-заявка для этих проверок не создавалась.

Затем production переведён на HTTPS релизом `20260906T115129Z-5f737c8f`. Let's Encrypt выдал сертификат для `refraction.info` и `www.refraction.info` до 5 декабря 2026 года. Проверены доверенная TLS-цепочка, HTTP→HTTPS, www→apex, HSTS, Secure cookies публичной формы и админки, а также реальный admin login по HTTPS. `certbot renew --dry-run` прошёл с установленными pre/deploy/post hooks. На сервере включён UFW с 22/80/443; свежий вход root по SSH-ключу прошёл, эффективные настройки отключают password и keyboard-interactive authentication.

Два ранних admin Playwright запуска нашли ошибки только в реализации/проверке: модель query принимала `page_size` из URL неверно, затем тест имел неоднозначный Next route-announcer `role=alert` и ожидал одиночный продублированный security header. Исправлены route parsing, точные locators и Nginx header hiding; оба сценария после этого прошли. Эти неуспешные прогоны не считаются итоговым успехом.

Ограничения остаются: GitHub Actions YAML проверяется локально, но remote Actions не запускался; отдельный admin subdomain и CDN отсутствуют; backup всё ещё вне объёма, поэтому подтверждённое delete необратимо.
