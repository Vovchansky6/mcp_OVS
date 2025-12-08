

---

````markdown
# MCP Business AI Transformation (Cloud.ru Hackathon)

Репозиторий команды: мультиагентная система на Evolution + MCP-сервер + Go-бизнес-движок.

Цель: показать **реальный бизнес-сценарий**, где AI-агент:
- понимает запрос человека,
- планирует, какие MCP-tools вызвать,
- ходит в публичные API через MCP-сервер,
- считает метрики и отдаёт **summary + рекомендации + риски**.

Решение спроектировано так, чтобы его можно было:
- запускать **локально** (для разработки/демо),
- упаковать в **контейнер** и развернуть в **Cloud.ru Evolution AI Agents**.

---

## 1. Архитектура

Высокоуровневая схема:

```text
Пользователь
   │
   ▼
Evolution (LLM, Cloud.ru)
   │  (JSON-план: какие tools вызвать)
   ▼
agent_system (Python, наш оркестратор)
   │  (MCP JSON-RPC)
   ▼
mcp_server (Python MCP-сервер)
   │  (HTTP REST)
   ▼
go-biz-engine (Go микросервис с бизнес-логикой)
   │
   ▼
Публичные API (курсы валют и др.)
````

### Компоненты репозитория

* **`mcp_server/`** — Python MCP-сервер (FastAPI)

  * реализует MCP-методы через `/mcp`:

    * `initialize`
    * `tools/list`
    * `tools/call`
    * `resources/list`
    * `resources/read`
  * хранит метаданные tools, управляет `ToolRegistry`
  * делегирует выполнение tools в Go-сервис `go-biz-engine`.

* **`go-biz-engine/`** — Go-микросервис с бизнес-логикой

  * HTTP API:

    * `GET /health`
    * `POST /execute-tool`
  * роутит вызовы по `tool_name` и считает метрики выполнения.
  * Реализовано: реальный **`financial_analyzer`**.

* **`agent_system/`** — мультиагентная Python-система

  * обёртка над **Evolution Foundation Models** (Cloud.ru)
  * оркестратор `handle_user_query`:

    * получает запрос пользователя,
    * спрашивает у Evolution **план**, какие MCP-tools вызвать,
    * по плану вызывает MCP `tools/call` (которые дальше идут в Go),
    * снова обращается к Evolution за **summary + рекомендациями + рисками**,
    * отдаёт итоговый A2A-ответ.

* **`src/`, `public/`, `Dockerfile.frontend` и т.п.** — фронтенд (Next.js), дашборд и вспомогательные вещи (можно подключать позже для визуализации).

* **`docker-compose.yml`** — оркестрация сервисов (mcp_server, БД, Redis, фронт и т.д.).

* **`init-db.sql`** — начальное наполнение БД (описания tools, схемы параметров и т.п.).

---

## 2. Что уже реализовано и работает

### 2.1. Go-сервис `go-biz-engine`

**Эндпоинты:**

* `GET /health` — здоровье сервиса.
* `POST /execute-tool` — универсальный вызов любого бизнес-tools.

**Запрос** (`POST /execute-tool`):

```json
{
  "tool_name": "financial_analyzer",
  "params": {
    "base_currency": "USD",
    "quote_currency": "EUR",
    "days": 7,
    "amount": 1000
  },
  "correlation_id": "uuid",
  "user_id": "agent-or-user-id",
  "request_ts": "2025-12-09T10:00:00Z",
  "context": {
    "source": "mcp-biz-server",
    "agent_id": "..."
  }
}
```

**Ответ**:

```json
{
  "status": "success",
  "data": {
    "rate_avg": 1.07,
    "rate_min": 1.05,
    "rate_max": 1.10,
    "volatility": 0.012,
    "raw": [
      { "date": "2025-12-01", "rate": 1.06 },
      ...
    ]
  },
  "error": null,
  "metrics": {
    "latency_ms": 123,
    "engine_time_ms": 100
  },
  "engine_version": "go-biz-engine/0.1.0"
}
```

**Реализованный бизнес-tool: `financial_analyzer`**

Принимает параметры:

* `base_currency` — базовая валюта (например `"USD"`);
* `quote_currency` — котируемая валюта (например `"EUR"`);
* `days` — период анализа в днях;
* `amount` — (опц.) сумма, на которую можно пересчитать курс.

Ходит в публичный API курсов валют, забирает исторические курсы за период и считает:

* **`rate_avg`** — средний курс,
* **`rate_min`** — минимум,
* **`rate_max`** — максимум,
* **`volatility`** — простая оценка волатильности.

---

### 2.2. MCP-сервер `mcp_server`

* Реализовано JSON-RPC API на `/mcp`:

  * `tools/list` — отдаёт список зарегистрированных tools:

    ```json
    {
      "jsonrpc": "2.0",
      "result": {
        "tools": [
          {
            "name": "financial_analyzer",
            "description": "...",
            "inputSchema": { ...JSON Schema... }
          },
          ...
        ]
      }
    }
    ```
  * `tools/call` — вызывает ToolRegistry → Go-движок → возвращает result:

    ```json
    {
      "jsonrpc": "2.0",
      "result": {
        "content": [
          {
            "type": "json",
            "json": { ...данные от Go... }
          }
        ],
        "isError": false,
        "toolName": "financial_analyzer",
        "executionTime": 0.123
      }
    }
    ```

* **`ToolRegistry.execute_tool`**:

  * проверяет, что tool зарегистрирован и `ACTIVE`;
  * собирает payload для `go-biz-engine` (`tool_name`, `params`, `correlation_id`, `user_id`, `context`);
  * делает HTTP-запрос в Go: `POST /execute-tool`;
  * по `status == "success"` кладёт `data` в `ToolExecution.result`;
  * по ошибке — заполняет `ToolExecution.error`.

* `init-db.sql` содержит описания tools (`financial_analyzer`, `api_connector`, `data_validator`, `report_generator` и др.) с JSON-схемами параметров.
  Их можно либо **подтянуть в ToolRegistry при старте**, либо зарегистрировать через REST-эндоинты.

---

### 2.3. Agent System (`agent_system`)

* Обёртка **`EvolutionProvider`** — работа с Evolution Foundation Models (Cloud.ru).
* Модели:

  * `Plan`, `ToolCall`, `ToolCallResult`, `A2AResponse` (в `agent_system/core/plan_models.py`).
* Оркестратор `handle_user_query` (в `agent_system/agents/orchestrator.py`):

  1. Делает MCP `tools/list` → получает список доступных tools и их JSON-схемы.
  2. Собирает промпт к Evolution: “вот запрос пользователя + вот доступные tools → верни JSON-план”.
  3. Evolution возвращает план: `overall_goal` + массив `tool_calls`.
  4. По плану циклом вызывает MCP `tools/call` → Go-сервис.
  5. Передаёт Evolution JSON со всеми результатами → получает `summary + recommendations + risks`.
  6. Возвращает `A2AResponse`:

     * исходный запрос;
     * цель;
     * список результатов по шагам;
     * краткое summary;
     * рекомендации;
     * риски.

---

## 3. Что ещё нужно доделать

### 3.1. Автоматическая регистрация tools

Сейчас:

* описания tools лежат в БД (`init-db.sql`),
* `ToolRegistry` хранит tools **в памяти**.

Нужно:

* либо при старте MCP-сервера подтягивать tools из БД и регистрировать в `ToolRegistry`,
* либо иметь простой скрипт (или make-таргет), который один раз шлёт `POST /api/v1/tools/register` для каждого наиболее важного tools (хотя бы `financial_analyzer`).

Пример ручной регистрации `financial_analyzer`:

```bash
curl -X POST http://localhost:8000/api/v1/tools/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "financial_analyzer",
    "description": "Финансовый анализатор: курсы валют, базовые метрики, волатильность.",
    "category": "finance",
    "input_schema": {
      "type": "object",
      "properties": {
        "base_currency": { "type": "string" },
        "quote_currency": { "type": "string" },
        "days": { "type": "integer" },
        "amount": { "type": "number" }
      },
      "required": ["base_currency", "quote_currency", "days"]
    },
    "status": "active",
    "tags": ["finance", "rates", "volatility"]
  }'
```

---

### 3.2. Контейнеризация для Cloud.ru (MCP + Evolution)

Что нужно для **боевого сценария на Cloud.ru**:

1. **Аккаунт и промокод**

   * Уже сделано: регистрация на Cloud.ru и ввод промокода.
   * Результат: есть возможность работать с **Evolution Foundation Models** и AI Agents.

2. **Получить Evolution API Key**

   * В личном кабинете Cloud.ru:

     * создать проект / workspace для Evolution,
     * сгенерировать **API-ключ** для Evolution (это потребуется нашему `agent_system` или MCP-серверу, если он напрямую ходит в Evolution),
     * сохранить ключ как `EVOLUTION_API_KEY`.

3. **Собрать Docker-образ MCP-сервера (с Go-движком внутри)**

   * Сейчас:

     * `mcp_server` и `go-biz-engine` — отдельные сервисы (локально Docker Compose может поднять их отдельно).
   * Для Cloud.ru Evolution Agent нам нужен **один образ**, который:

     * поднимает `go-biz-engine` (например, отдельным процессом в entrypoint),
     * поднимает `mcp_server` (FastAPI/uvicorn),
     * слушает публичный порт MCP (обычно 8000 или другой),
     * внутри использует `GO_BIZ_ENGINE_URL=http://localhost:8080`.

   Пример концепции (упростить и собрать потом нормально):

   * Базовый образ: `python:3.11-slim`.
   * Устанавливаем Go или заранее собираем бинарник `go-biz-engine` и копируем в образ.
   * Стартовый скрипт:

     ```bash
     #!/bin/sh
     ./go-biz-engine-binary &
     uvicorn app.main:app --host 0.0.0.0 --port 8000
     ```

   Это **TODO**: сейчас MCP и Go запускаются раздельно; для Cloud надо их объединить в один Docker.

4. **Залить образ в реестр Cloud.ru**

   * В Cloud.ru:

     * создать Container Registry (если ещё нет),
     * залогиниться в него через `docker login`,
     * выполнить:

       ```bash
       docker build -t cr.cloud.ru/<project>/<repo>/mcp-biz-engine:latest .
       docker push cr.cloud.ru/<project>/<repo>/mcp-biz-engine:latest
       ```
   * Важно: указать правильный адрес реестра и namespace из консоли Cloud.ru.

5. **Создать MCP-based Agent в Cloud.ru Evolution AI Agents**

   * В интерфейсе платформы Evolution:

     * создать новый **AI Agent**,
     * выбрать тип **MCP Agent** (или аналогичный пункт),
     * в качестве backend указать:

       * Наш образ из реестра `cr.cloud.ru/.../mcp-biz-engine:latest`,
       * Порт контейнера, где слушает MCP (`/mcp` на 8000),
       * Переменные окружения:

         * `EVOLUTION_API_KEY` — ключ от Evolution,
         * `GO_BIZ_ENGINE_URL=http://localhost:8080`,
         * `DATABASE_URL`, `REDIS_URL` — при необходимости (если нужны БД/кэш),
         * `DEBUG=false`.

   * После запуска:

     * MCP-сервер внутри контейнера будет доступен Evolution как MCP endpoint;
     * инструменты, зарегистрированные в `ToolRegistry`, станут видны модели как MCP-tools.

6. **Файл `tools.json`**

   * Для того чтобы агент легко включался в каталог Evolution AI Agents, желательно иметь **описание shared-tools** в виде `tools.json` в корне репозитория.
   * В нём можно описать:

     * список MCP-tools, которые наш сервер поддерживает;
     * их описания;
     * типы аргументов.
   * Это **ещё один TODO**, но его легко собрать на основе того, что уже есть в БД и в `tools/list`.

---

### 3.3. Улучшения по бизнес-функционалу

Сейчас:

* Реальный бизнес-tool: **`financial_analyzer`** (Go + публичный API курсов).
* Остальные tools (`api_connector`, `data_validator`, `report_generator`) — в основном заглушки/скелеты.

План по доработке:

1. **`api_connector`**

   * научить подключаться к произвольному REST API (URL + headers + query),
   * возвращать нормализованный JSON.

2. **`data_validator`**

   * принимать JSON-данные,
   * валидировать по заданным правилам (например, обязательные поля, типы, диапазоны),
   * возвращать список ошибок/варнингов.

3. **`report_generator`**

   * принимать результаты других tools,
   * собирать сводный отчёт (например, по валютным рискам),
   * генерировать summary в текстовом виде плюс структурированные данные.

---

## 4. Как запускать локально (для команды)

### 4.1. Быстрый старт (без Docker)

#### Go-сервис

```bash
cd go-biz-engine
go mod tidy
go run ./cmd/go-biz-engine
# слушает http://localhost:8080
```

#### MCP-сервер

```bash
cd mcp_server
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt

# В .env или окружении:
# GO_BIZ_ENGINE_URL=http://localhost:8080

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# MCP endpoint: http://localhost:8000/mcp
```

#### Проверка связки MCP → Go

**Список tools:**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

**Вызов `financial_analyzer`:**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "financial_analyzer",
      "arguments": {
        "base_currency": "USD",
        "quote_currency": "EUR",
        "days": 7,
        "amount": 1000
      },
      "agent_id": "manual-test"
    }
  }'
```

Ожидаем в `result.content[0].json` данные по курсам и метрикам.

---

### 4.2. Agent System + Evolution (локально)

```bash
cd agent_system
python -m venv venv
source venv/bin/activate             # Windows: venv\Scripts\activate
pip install -r requirements.txt

# В окружении:
# EVOLUTION_API_KEY=... (ключ из Cloud.ru)
# MCP_SERVER_URL=http://localhost:8000
```

Дальше можно написать небольшой скрипт (например, `run_orchestrator_demo.py`), который:

* просит у пользователя текст запроса,
* создаёт `EvolutionProvider`,
* вызывает `handle_user_query` и печатает:

  * summary,
  * рекомендации,
  * риски,
  * сырые результаты tools.

(Скелет такого скрипта у нас уже есть — его легко восстановить по коду оркестратора.)

---

## 5. Резюме для коллег

1. **Что уже есть**

   * Рабочий Go-движок `go-biz-engine` с реальным tool `financial_analyzer`.
   * MCP-сервер `mcp_server`, который:

     * реализует MCP `tools/list` и `tools/call`,
     * ходит в Go-сервис по HTTP и прокидывает результат клиентам.
   * Agent System на Evolution:

     * умеет по запросу строить план вызова tools,
     * выполнять план через MCP,
     * формировать итоговый A2A-ответ (summary + рекомендации + риски).

2. **Что нужно для Cloud.ru**

   * Есть аккаунт и промокод — ✓.
   * Надо:

     * получить `EVOLUTION_API_KEY`,
     * собрать **единый Docker-образ** с MCP-сервером и Go-движком,
     * залить образ в реестр Cloud.ru,
     * создать MCP-agent в Evolution и указать:

       * образ,
       * порт MCP,
       * переменные окружения (`EVOLUTION_API_KEY`, `GO_BIZ_ENGINE_URL`, и т.п.),
     * при необходимости — добавить `tools.json` для совместимости с каталогом Evolution AI Agents.

3. **Куда развиваться дальше**

   * Доделать остальные tools (`api_connector`, `data_validator`, `report_generator`).
   * Прокачать бизнес-сценарий (конкретный кейс: управление валютными рисками, отчётность для финансового директора и т.д.).
   * Добавить UI (фронт на Next.js) для красивой демонстрации (дашборд, визуализация курсов, алерты).




