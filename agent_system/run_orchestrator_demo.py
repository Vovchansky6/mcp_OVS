#!/usr/bin/env python3
"""
Простой CLI-скрипт для демонстрации оркестратора:
Evolution -> MCP tools -> Go engine -> summary/recs/risks.
"""

import asyncio
import os
import sys
import json

import structlog

from agent_system.llm.providers.evolution_provider import EvolutionProvider
from agent_system.agents.orchestrator import handle_user_query

logger = structlog.get_logger(__name__)


async def main():
    # 1. Берём запрос пользователя
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        user_query = input("Введите запрос для бизнес-агента: ").strip()

    if not user_query:
        print("Пустой запрос — нечего обрабатывать.")
        return

    # 2. Настраиваем EvolutionProvider
    api_key = os.getenv("EVOLUTION_API_KEY")
    if not api_key:
        print("ERROR: не задан EVOLUTION_API_KEY в окружении.")
        print("Пример (PowerShell):  $env:EVOLUTION_API_KEY='xxx'")
        return

    evolution = EvolutionProvider(
        config={
            "api_key": api_key,
            # можно переопределить base_url и модель при желании
            # "base_url": "https://api.cloud.ru/evolution",
            # "default_model": "evolution-llm-v1",
        }
    )

    # 3. URL MCP-сервера
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    print(f"Используем MCP сервер: {mcp_server_url}")

    # 4. Запускаем наш оркестратор
    try:
        a2a = await handle_user_query(
            text=user_query,
            evolution=evolution,
            mcp_server_url=mcp_server_url,
            agent_id="evolution-biz-agent-demo",
        )
    except Exception as e:
        logger.error("handle_user_query failed", error=str(e))
        print(f"\nОшибка при обработке запроса: {e}")
        return

    # 5. Печатаем результат
    print("\n=== SUMMARY ===")
    print(a2a.summary)

    print("\n=== RECOMMENDATIONS ===")
    if a2a.recommendations:
        for i, rec in enumerate(a2a.recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("— нет рекомендаций —")

    print("\n=== RISKS ===")
    if a2a.risks:
        for i, risk in enumerate(a2a.risks, 1):
            print(f"{i}. {risk}")
    else:
        print("— нет явных рисков —")

    print("\n=== RAW TOOL RESULTS (JSON) ===")
    # Если хочешь — можно печатать более компактно
    print(
        json.dumps(
            [tr.dict() for tr in a2a.tool_results],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
