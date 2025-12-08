from typing import Any, Dict, List
import json

import httpx
import structlog

from agent_system.core.plan_models import Plan, ToolCallResult, A2AResponse
from agent_system.llm.providers.evolution_provider import EvolutionProvider

logger = structlog.get_logger(__name__)

MCP_TOOLS_LIST_METHOD = "tools/list"
MCP_TOOLS_CALL_METHOD = "tools/call"


# ---------- ПРОМПТ ДЛЯ ПЛАНА ----------

PLAN_PROMPT_TEMPLATE = """
Ты — планировщик инструментов в системе MCP Business AI.

Твоя задача: по запросу пользователя и списку доступных MCP-tools
составить *пошаговый план*, какие инструменты нужно вызвать и с какими аргументами.

ДОСТУПНЫЕ TOOLS (JSON-список объектов формата:
{{ "name": ..., "description": ..., "inputSchema": ... }}):

{tools_json}

ТРЕБОВАНИЯ К ОТВЕТУ:

1. Ответ ДОЛЖЕН быть строго валидным JSON.
2. НИКАКОГО дополнительного текста, комментариев или Markdown — только JSON.
3. Формат JSON-ответа:

{{
  "overall_goal": "краткое описание цели пользователя на русском",
  "tool_calls": [
    {{
      "id": "step1",
      "tool_name": "имя_инструмента_из_списка",
      "description": "что делает этот шаг",
      "arguments": {{
        // корректные аргументы строго по inputSchema выбранного tool
      }}
    }}
  ]
}}

ПРАВИЛА:

- Используй только инструменты из списка выше.
- Если достаточно одного инструмента — сделай один шаг.
- Если необходимо несколько шагов (например, сначала получить данные, потом проанализировать) — создай несколько элементов в "tool_calls" с уникальными "id".
- Если инструменты не нужны, верни:
  "tool_calls": []
  и в "overall_goal" коротко опиши, что ты будешь отвечать без вызова инструментов.
- Подбирай аргументы строго по inputSchema:
  - соблюдай имена полей;
  - соблюдай типы (строки, числа, булевы значения);
  - не добавляй полей, которых нет в схеме, кроме очевидных необязательных.

ПОЛЬЗОВАТЕЛЬСКИЙ ЗАПРОС:

\"\"\"{user_query}\"\"\".
"""


# ---------- ПРОМПТ ДЛЯ SUMMARY ----------

SUMMARY_PROMPT_TEMPLATE = """
Ты — бизнес-аналитик.

Тебе даны:
1) исходный запрос пользователя;
2) цель плана;
3) список шагов tools и их результатов.

На основе этого верни JSON с кратким summary, рекомендациями и рисками.

Исходный запрос:
\"\"\"{user_query}\"\"\".

Цель плана:
\"\"\"{overall_goal}\"\"\".

Шаги и результаты (JSON-список объектов):
{results_json}

ТРЕБОВАНИЯ К ОТВЕТУ:
- Ответ строго в формате JSON, без лишнего текста.
- Формат:

{{
  "summary": "краткое объяснение на русском, что было сделано и к каким выводам пришли",
  "recommendations": [
    "рекомендация 1",
    "рекомендация 2"
  ],
  "risks": [
    "риск 1",
    "риск 2"
  ]
}}
"""


async def handle_user_query(
    text: str,
    evolution: EvolutionProvider,
    mcp_server_url: str,
    agent_id: str = "evolution-biz-agent-1",
) -> A2AResponse:
    """
    1) просим Evolution выдать JSON-план (какие MCP-tools вызвать),
    2) по плану вызываем MCP tools/call,
    3) агрегируем результаты,
    4) ещё раз зовём Evolution для summary / рекомендаций / рисков.
    """

    # 1. Забираем список доступных tools через MCP tools/list
    async with httpx.AsyncClient(timeout=10.0) as client:
        list_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": MCP_TOOLS_LIST_METHOD,
            "params": {},
        }
        mcp_resp = await client.post(f"{mcp_server_url}/mcp", json=list_req)
        mcp_resp.raise_for_status()
        mcp_body = mcp_resp.json()

    tools_list = (mcp_body.get("result") or {}).get("tools", [])
    tools_json = json.dumps(tools_list, ensure_ascii=False, indent=2)

    # 2. Строим промпт к Evolution для планирования
    plan_prompt = PLAN_PROMPT_TEMPLATE.format(
        tools_json=tools_json,
        user_query=text,
    )

    logger.info("Requesting plan from Evolution", agent_id=agent_id)

    plan_resp = await evolution.generate(
        prompt=plan_prompt,
        max_tokens=800,
        temperature=0.2,
    )

    # Ожидаем, что модель вернула чистый JSON
    try:
        plan_data = json.loads(plan_resp.content)
        plan = Plan(**plan_data)
    except Exception as e:
        logger.error("Failed to parse plan JSON from Evolution", error=str(e), raw=plan_resp.content)
        raise

    logger.info(
        "Tool plan generated",
        overall_goal=plan.overall_goal,
        steps=len(plan.tool_calls),
    )

    # 3. Выполняем план: tools/call → MCP → Go
    tool_results: List[ToolCallResult] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, step in enumerate(plan.tool_calls, start=1):
            request_id = idx
            rpc_req = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": MCP_TOOLS_CALL_METHOD,
                "params": {
                    "name": step.tool_name,
                    "arguments": step.arguments,
                    "agent_id": agent_id,
                },
            }

            logger.info(
                "Calling MCP tool",
                tool_name=step.tool_name,
                step_id=step.id,
                request_id=request_id,
            )

            try:
                resp = await client.post(f"{mcp_server_url}/mcp", json=rpc_req)
                resp.raise_for_status()
                body = resp.json()
            except Exception as e:
                logger.error(
                    "MCP tools/call failed",
                    tool_name=step.tool_name,
                    step_id=step.id,
                    error=str(e),
                )
                tool_results.append(
                    ToolCallResult(
                        call_id=step.id,
                        tool_name=step.tool_name,
                        arguments=step.arguments,
                        success=False,
                        result=None,
                        error=f"HTTP error calling MCP: {e}",
                    )
                )
                continue

            # JSON-RPC ошибка верхнего уровня
            if "error" in body:
                err = body["error"]
                tool_results.append(
                    ToolCallResult(
                        call_id=step.id,
                        tool_name=step.tool_name,
                        arguments=step.arguments,
                        success=False,
                        result=None,
                        error=f"JSON-RPC error {err.get('code')}: {err.get('message')}",
                    )
                )
                continue

            result_obj = body.get("result") or {}
            is_error = result_obj.get("isError", False)
            mcp_content = result_obj.get("content", [])

            # В нашей реализации tools/call мы кладём JSON в content[0].json
            tool_json_result: Any = None
            if mcp_content:
                first_item = mcp_content[0]
                if first_item.get("type") == "json":
                    tool_json_result = first_item.get("json")

            tool_results.append(
                ToolCallResult(
                    call_id=step.id,
                    tool_name=step.tool_name,
                    arguments=step.arguments,
                    success=not is_error,
                    result=tool_json_result,
                    error=result_obj.get("error") if is_error else None,
                )
            )

    # 4. Просим Evolution сделать summary / рекомендации / риски
    results_json = json.dumps(
        [tr.dict() for tr in tool_results],
        ensure_ascii=False,
        indent=2,
    )

    summary_prompt = SUMMARY_PROMPT_TEMPLATE.format(
        user_query=text,
        overall_goal=plan.overall_goal,
        results_json=results_json,
    )

    logger.info("Requesting summary from Evolution", agent_id=agent_id)

    summary_resp = await evolution.generate(
        prompt=summary_prompt,
        max_tokens=600,
        temperature=0.3,
    )

    try:
        summary_data = json.loads(summary_resp.content)
    except Exception as e:
        logger.error(
            "Failed to parse summary JSON from Evolution",
            error=str(e),
            raw=summary_resp.content,
        )
        summary_data = {
            "summary": "Не удалось автоматически сформировать summary, см. сырые результаты.",
            "recommendations": [],
            "risks": [],
        }

    # 5. Собираем итоговый A2AResponse
    a2a = A2AResponse(
        query=text,
        overall_goal=plan.overall_goal,
        tool_results=tool_results,
        summary=summary_data.get("summary", ""),
        recommendations=summary_data.get("recommendations") or [],
        risks=summary_data.get("risks") or [],
    )

    return a2a
