#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAPSHOT_DIR="$PROJECT_DIR/snapshots"

if [[ $# -ne 1 ]]; then
    echo "Использование:"
    echo "  ./snapshot.sh <название>"
    echo
    echo "Пример:"
    echo "  ./snapshot.sh before_wan"
    exit 1
fi

NAME="$1"
SNAPSHOT_FILE="$SNAPSHOT_DIR/$NAME.txt"

mkdir -p "$SNAPSHOT_DIR"

if [[ -e "$SNAPSHOT_FILE" ]]; then
    echo "Ошибка: snapshot '$NAME' уже существует:"
    echo "$SNAPSHOT_FILE"
    exit 1
fi

echo "Создаю snapshot: $NAME"
echo "Проект: $PROJECT_DIR"

cd "$PROJECT_DIR"

find . \
    -type f \
    ! -path './snapshots/*' \
    ! -path './.git/*' \
    -printf '%P\n' \
    | sort > "$SNAPSHOT_FILE"

COUNT=$(wc -l < "$SNAPSHOT_FILE")

echo
echo "Snapshot создан."
echo "Файлов сохранено: $COUNT"
echo "Файл: $SNAPSHOT_FILE"
