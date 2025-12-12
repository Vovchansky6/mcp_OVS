
---
````markdown
# MCP Business AI Transformation (Cloud.ru Hackathon)

Прототип решения для хакатона Cloud.ru: MCP-сервер + набор бизнес-инструментов, которые вызываются из Evolution AI Agents через протокол Model Context Protocol (MCP).

Решение показывает, как:
- оборачивать внешние сервисы / бизнес-логику в MCP-tools;
- подключать MCP-сервер к Evolution AI Agents;
- работать с ним в интерфейсе Cloud.ru.

---

## 1. Архитектура решения

В репозитории реализованы следующие компоненты:

- **`mcp_server/`** – основной MCP-сервер на FastAPI:
  - `/health`, `/api/v1/health` – health-чек сервера;
  - `/mcp` – MCP-endpoint (JSON-RPC 2.0) с методами:
    - `initialize`
    - `tools/list`
    - `tools/call`
    - `resources/list` (пока заглушка)
    - `resources/read` (пока заглушка);
  - `app/api/v1/tools.py` – объявление MCP-инструментов и `tool_registry`.

- **`agent_system/`** – заготовка многоагентной системы (орchestrator, агенты и т.д.).  
  Для хакатона основное внимание на **MCP-сервере**; агентную систему можно развивать дальше.

- **`src/`** – фронтенд на Next.js (UI-панель).  
  Для проверки решения на Cloud.ru не обязателен, но показывает, как можно визуализировать работу.


## 2. Быстрый старт локально (Windows / macOS / Linux)

### 2.1. Предварительные требования

- Python 3.11+
- Git
- (опционально) Docker, если нужен запуск в контейнере

### 2.2. Клонирование репозитория

```
---
git clone https://github.com/<ВАШ_АККАУНТ>/<ВАШ_РЕПОЗИТОРИЙ>.git
cd mcp-biz-master
---
````

### 2.3. Настройка переменных окружения

Создаём `.env` из примера:

```
---
cp .env.example .env
---
```

Минимальный набор для запуска MCP-сервера:

```
---
EVOLUTION_API_KEY=ВАШ_КЛЮЧ_ОТ_CLOUD_RU
SECRET_KEY=любая_длинная_строка_для_подписи
---
```

Все остальные переменные могут остаться как в `.env.example` – они используются вспомогательными сервисами, которые для демо не критичны.

> В репозиторий коммитится только `.env.example`. Файл `.env` должен быть в `.gitignore`.

### 2.4. Установка зависимостей и запуск MCP-сервера

```
---
cd mcp_server

python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt

# запуск MCP-сервера
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
---
```

После старта сервер доступен по адресу `http://localhost:8000`.

---

## 3. Проверка работы локально

Открыть новый терминал (сервер оставить запущенным).

### 3.1. Health-чек

```
---
curl http://localhost:8000/api/v1/health
---
```

Ожидаемый ответ:

```
---
{
  "status": "ok",
  "version": "...",
  "app": "..."
}
---
```

То же самое будет по `http://localhost:8000/health`.

### 3.2. MCP `tools/list`

```
---
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
---
```

Ответ – JSON с перечнем доступных MCP-tools:

```
---
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "...",
        "description": "...",
        "inputSchema": { ... }
      }
    ]
  }
}
---
```

### 3.3. MCP `tools/call` (пример)

Пример общего вида запроса (конкретные имена и параметры смотрите в `app/api/v1/tools.py`):

```
---
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "SOME_TOOL_NAME",
      "arguments": {
        "param1": "value1"
      }
    }
  }'
---
```

---

## 4. Переменные окружения (.env)

Полный перечень переменных – в `.env.example`.
Ключевые для запуска MCP-сервера:

| Переменная          | Обязательна | Назначение                                             |
| ------------------- | ----------: | ------------------------------------------------------ |
| `EVOLUTION_API_KEY` |            | API-ключ Cloud.ru Foundation Models / Agents           |
| `SECRET_KEY`        |            | Секрет для подписи токенов / внутреннего использования |

Остальные (`DATABASE_URL`, `REDIS_URL`, `POSTGRES_*`, `RABBITMQ_*`, `GF_SECURITY_*` и т.д.) используются для расширенной инфраструктуры (БД, кэш, очереди, мониторинг). Для базового демонстрационного запуска их можно оставить как в примере.

---

## 5. Деплой MCP-сервера в Cloud.ru (Artifact Registry + Container Apps)

### 5.1. Сборка Docker-образа

```
---
cd mcp_server
docker build -t mcp-biz-server:latest .
---
```

### 5.2. Публикация образа в Artifact Registry

1. В личном кабинете Cloud.ru создать Docker / Artifact Registry.

2. Выполнить `docker login` по инструкции Cloud.ru:

```
---
   docker login <registry_name>.cr.cloud.ru -u <user_or_key> -p <password>
---
```

3. Протегировать и отправить образ:

```
---
   docker tag mcp-biz-server:latest <registry_name>.cr.cloud.ru/mcp-biz-server:latest
   docker push <registry_name>.cr.cloud.ru/mcp-biz-server:latest
---
```

### 5.3. Создание Container App

1. В разделе Artifact Registry открыть загруженный образ и выбрать «Создать Container App».
2. Указать:

   * порт контейнера: **8000**;
   * переменные окружения: минимум `EVOLUTION_API_KEY` и `SECRET_KEY` (значения – как в локальном `.env`).
3. Дождаться запуска и запомнить публичный URL контейнера, например:

```
---
   https://mcp-biz-server.containers.cloud.ru
---
```

Проверка:

```
---
curl https://mcp-biz-server.containers.cloud.ru/api/v1/health
---
```

---

## 6. Подключение MCP-сервера к Evolution AI Agents

1. В Cloud.ru открыть **AI Factory → AI Agents → MCP-серверы**.
2. Нажать **«Создать MCP-сервер»**.
3. Указать:

   * название (например, `Biz MCP Server`);
   * описание (кратко: «MCP-сервер для бизнес-инструментов»);
   * URL: `https://mcp-biz-server.containers.cloud.ru/mcp` (или ваш реальный адрес).
4. Сохранить и дождаться статуса «Готов».

---

## 7. Создание агента в Evolution AI Agents

1. В разделе **AI Factory → AI Agents → Агенты** нажать **«Создать агента»**.
2. Выбрать модель из Evolution Foundation Models.
3. В разделе **Инструменты / MCP** выбрать созданный MCP-сервер `Biz MCP Server`.
4. Сохранить агента.

Дальше можно тестировать в веб-интерфейсе Cloud.ru:

* задать вопрос в свободной форме («Покажи, какие инструменты у тебя есть»);
* агент через LLM вызовет `tools/list` и вернёт список инструментов;
* затем можно запускать конкретные `tools/call` по смыслу запроса.

---

## 8. Что реализовано сейчас и что планируется

**Реализовано в MVP:**

* MCP-сервер на FastAPI (`mcp_server/`):

  * health-эндпоинты `/health` и `/api/v1/health`;
  * MCP-endpoint `/mcp` с методами `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`;
  * интеграция с реестром инструментов `tool_registry` (см. `app/api/v1/tools.py`).
* Возможность локального запуска и деплоя в Docker/Container Apps на Cloud.ru.
* Подключение MCP-сервера к Evolution AI Agents.

**Планы развития (после хакатона):**

* полноценная реализация `resources` (подключение к внешним источникам данных);
* расширенный набор бизнес-инструментов;
* включение продвинутых мидлварей (аутентификация, rate limiting, корреляция запросов, метрики);
* развитие `agent_system/` в сторону полноценной многоагентной платформы;
* UI-дашборд (папка `src/`) для бизнес-пользователей (визуализация сценариев, алёрты и т.д.).


```
---