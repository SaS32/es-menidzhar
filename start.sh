#!/usr/bin/env bash
set -e

echo "Проверка на Python..."
if ! command -v python3 &>/dev/null; then
    echo "ГРЕШКА: python3 не е намерен. Инсталирайте Python 3.10+"
    exit 1
fi

echo "Инсталиране на зависимости..."
pip3 install -r requirements.txt --quiet

echo "Стартиране на сървъра..."
echo "Адресът се изписва по-долу (по подразбиране: http://localhost:5050)"
echo "За спиране натиснете Ctrl+C"
python3 app.py
