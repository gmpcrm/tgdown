#!/bin/bash
# filepath: /home/nstepankov/Projects/tgdown/run.sh

# Telegram Chat Downloader - Run Script
# ====================================

# Конфигурация
# =============
DEFAULT_SOURCE_DIR="source/ChatExport_2025-06-08"
DEFAULT_TARGET_DIR="results-algo-rag"
VENV_PATH="~/venv/bin/activate"

# Активация виртуального окружения
source $VENV_PATH

echo "🚀 Telegram Chat Downloader"
echo "=========================="
echo ""

# Показать справку по использованию
show_help() {
    echo "📋 Доступные флаги:"
    echo ""
    echo "  --download          📥 Реально скачивает файлы (по умолчанию: выключено)"
    echo "  --links            📝 Собирает ссылки в links.txt (по умолчанию: включено)" 
    echo "  --no-links         🚫 Отключает сбор ссылок"
    echo ""
    echo "  --source_file      📄 Путь к JSON файлу с экспортом"
    echo "  --source_dir       📁 Директория где искать result.json"
    echo "  --target_dir       💾 Целевая директория (по умолчанию: results)"
    echo ""
    echo "📊 Результаты:"
    echo "  links.txt          - Все найденные ссылки"
    echo "  skipped.txt        - Пропущенные ссылки (YouTube, Telegram)"
    echo "  errors.txt         - Ссылки с ошибками скачивания"
    echo ""
    echo "🗂️  Организация файлов:"
    echo "  YYYY-MM/           - Группировка по месяцам"
    echo "  file.pdf           - Оригинальное имя"
    echo "  file (01).pdf      - Автонумерация дубликатов"
    echo ""
}

# Примеры использования
show_examples() {
    echo "💡 Примеры использования:"
    echo ""
    echo "1️⃣  Только сбор ссылок (по умолчанию):"
    echo "   python downloader.py --source_dir $DEFAULT_SOURCE_DIR"
    echo ""
    echo "2️⃣  Только скачивание файлов:"
    echo "   python downloader.py --download --no-links --source_dir $DEFAULT_SOURCE_DIR"
    echo ""
    echo "3️⃣  И ссылки, и скачивание:"
    echo "   python downloader.py --download --source_dir $DEFAULT_SOURCE_DIR"
    echo ""
    echo "4️⃣  Кастомные пути:"
    echo "   python downloader.py --download --source_file /путь/к/result.json --target_dir /моя/папка"
    echo ""
}

# Проверка аргументов
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    show_examples
    exit 0
fi

# Основные конфигурации
# ===================

echo "🔧 Выберите режим работы:"
echo ""
echo "1) Только сбор ссылок (быстро)"
echo "2) Только скачивание файлов" 
echo "3) И ссылки, и скачивание (полный режим)"
echo "4) Кастомная команда"
echo "5) Показать справку"
echo ""
read -p "Выберите опцию (1-5): " choice

case $choice in
    1)
        echo "📝 Режим: Только сбор ссылок"
        python downloader.py --source_dir $DEFAULT_SOURCE_DIR --target_dir $DEFAULT_TARGET_DIR
        ;;
    2) 
        echo "📥 Режим: Только скачивание файлов"
        python downloader.py --download --no-links --source_dir $DEFAULT_SOURCE_DIR --target_dir $DEFAULT_TARGET_DIR
        ;;
    3)
        echo "🚀 Режим: Полный (ссылки + скачивание)"
        python downloader.py --download --source_dir $DEFAULT_SOURCE_DIR --target_dir $DEFAULT_TARGET_DIR
        ;;
    4)
        echo "⚙️  Кастомная команда:"
        echo "Введите путь к source (или нажмите Enter для $DEFAULT_SOURCE_DIR):"
        read -p "Source: " source_path
        source_path=${source_path:-"$DEFAULT_SOURCE_DIR"}
        
        echo "Введите target директорию (или нажмите Enter для $DEFAULT_TARGET_DIR):"
        read -p "Target: " target_path  
        target_path=${target_path:-"$DEFAULT_TARGET_DIR"}
        
        echo "Скачивать файлы? (y/n, по умолчанию n):"
        read -p "Download: " download_choice
        
        cmd="python downloader.py --source_dir $source_path --target_dir $target_path"
        if [ "$download_choice" = "y" ] || [ "$download_choice" = "Y" ]; then
            cmd="$cmd --download"
        fi
        
        echo "🔄 Выполняю: $cmd"
        eval $cmd
        ;;
    5)
        show_help
        show_examples
        ;;
    *)
        echo "❌ Неверный выбор. Используйте --help для справки."
        exit 1
        ;;
esac

echo ""
echo "✅ Готово! Проверьте результаты в директории $DEFAULT_TARGET_DIR/"
echo ""
echo "📋 Сгенерированные файлы:"
echo "  📝 links.txt    - Все найденные ссылки"  
echo "  🚫 skipped.txt  - Пропущенные ссылки"
echo "  ❌ errors.txt   - Ссылки с ошибками"
echo ""