#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAPSHOT_DIR="$PROJECT_DIR/snapshots"

if [[ $# -ne 1 ]]; then
    echo "Использование:"
    echo "  ./restore.sh <название>"
    echo
    echo "Пример:"
    echo "  ./restore.sh before_wan"
    exit 1
fi

NAME="$1"
SNAPSHOT_FILE="$SNAPSHOT_DIR/$NAME.txt"

if [[ ! -f "$SNAPSHOT_FILE" ]]; then
    echo "Ошибка: snapshot '$NAME' не найден."
    echo
    echo "Доступные snapshots:"
    ls -1 "$SNAPSHOT_DIR"/*.txt 2>/dev/null \
        | sed 's|.*/||; s|\.txt$||' \
        || echo "  Нет snapshots."
    exit 1
fi

cd "$PROJECT_DIR"

TMP_CURRENT=$(mktemp)
TMP_SNAPSHOT=$(mktemp)

trap 'rm -f "$TMP_CURRENT" "$TMP_SNAPSHOT"' EXIT

find . \
    -type f \
    ! -path './snapshots/*' \
    ! -path './.git/*' \
    -printf '%P\n' \
    | sort > "$TMP_CURRENT"

sort "$SNAPSHOT_FILE" > "$TMP_SNAPSHOT"

# Файлы, которые существуют сейчас, но отсутствовали
# во время создания snapshot.
mapfile -t EXTRA_FILES < <(
    comm -13 "$TMP_SNAPSHOT" "$TMP_CURRENT"
)

echo "========================================"
echo " RESTORE: $NAME"
echo "========================================"
echo

if [[ ${#EXTRA_FILES[@]} -eq 0 ]]; then
    echo "Новых файлов не обнаружено."
    echo "Удалять нечего."
    exit 0
fi

echo "Будут удалены следующие файлы:"
echo

for file in "${EXTRA_FILES[@]}"; do
    echo "  $file"
done

echo
echo "Всего файлов к удалению: ${#EXTRA_FILES[@]}"
echo

read -r -p "Введите YES для удаления: " CONFIRM

if [[ "$CONFIRM" != "YES" ]]; then
    echo
    echo "Отмена. Ничего не удалено."
    exit 0
fi

echo
echo "Удаляю..."

for file in "${EXTRA_FILES[@]}"; do
    if [[ -f "$PROJECT_DIR/$file" ]]; then
        rm -- "$PROJECT_DIR/$file"
    fi
done

# Удаляем пустые директории, которые могли остаться
# после удаления файлов.
find "$PROJECT_DIR" \
    -type d \
    ! -path "$PROJECT_DIR" \
    ! -path "$PROJECT_DIR/.git*" \
    ! -path "$PROJECT_DIR/snapshots*" \
    -empty \
    -delete 2>/dev/null || true

echo
echo "========================================"
echo " Восстановление завершено"
echo "========================================"
