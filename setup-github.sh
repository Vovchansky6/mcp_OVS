#!/bin/bash
# MCP Business AI - GitHub Setup Script
# Для аккаунта: eugizusDev

REPO_NAME="mcp-business-ai-transformation"
GITHUB_USER="eugizusDev"

echo "🚀 MCP Business AI - GitHub Setup"
echo "=================================="

# Проверка gh CLI
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) не установлен"
    echo "Установи: https://cli.github.com/"
    echo ""
    echo "Или создай репо вручную:"
    echo "1. Открой https://github.com/new"
    echo "2. Имя: $REPO_NAME"
    echo "3. Приватный или публичный"
    echo "4. НЕ добавляй README/gitignore"
    echo ""
    echo "Затем выполни:"
    echo "  git remote add origin git@github.com:$GITHUB_USER/$REPO_NAME.git"
    echo "  git push -u origin main"
    exit 1
fi

# Проверка авторизации
if ! gh auth status &> /dev/null; then
    echo "⚠️  Нужна авторизация в GitHub CLI"
    gh auth login
fi

# Создание репозитория
echo "📦 Создаю репозиторий $GITHUB_USER/$REPO_NAME..."
gh repo create $REPO_NAME --public --description "MCP Server for Business AI Transformation - Cloud.ru Evolution AI" --source=. --remote=origin --push

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Готово!"
    echo "🔗 https://github.com/$GITHUB_USER/$REPO_NAME"
else
    echo "❌ Ошибка создания репозитория"
    echo ""
    echo "Попробуй вручную:"
    echo "  gh repo create $REPO_NAME --public"
    echo "  git remote add origin git@github.com:$GITHUB_USER/$REPO_NAME.git"
    echo "  git push -u origin main"
fi
