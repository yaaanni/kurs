#!/bin/bash
# pack_for_amd.sh - подготовка комплекта для прогона на второй вычислительной
# системе (AMD Ryzen 7 7840HS).
#
# Создаёт архив fibbench-amd.tar.gz, содержащий статически скомпонованный
# исполняемый файл, скрипт прогона и исходный код. Исполняемый файл
# пересобирать на второй системе НЕ НУЖНО: сравнение производительности
# требует, чтобы на обеих машинах выполнялся один и тот же машинный код.

set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

[ -x ./fibbench ] || make

if ldd ./fibbench >/dev/null 2>&1; then
    echo "!! Исполняемый файл скомпонован динамически."
    echo "!! Выполните 'make clean && make' - текущий Makefile включает -static."
    exit 1
fi

STAGE="$(mktemp -d)"
DEST="$STAGE/fibbench"
mkdir -p "$DEST/scripts" "$DEST/src" "$DEST/results"

cp fibbench                   "$DEST/"
cp Makefile                   "$DEST/"
cp ЗАПУСК.md                   "$DEST/"
cp src/*.c src/*.h            "$DEST/src/"
cp scripts/run_bench.sh       "$DEST/scripts/"
cp scripts/shoot.py           "$DEST/scripts/"
cp run_on_amd.sh              "$DEST/"
chmod +x "$DEST/fibbench" "$DEST/scripts/run_bench.sh" "$DEST/run_on_amd.sh"

sha256sum fibbench | awk '{print $1}' > "$DEST/fibbench.sha256"

tar -czf "$ROOT/fibbench-amd.tar.gz" -C "$STAGE" fibbench
rm -rf "$STAGE"

echo "Готово: $ROOT/fibbench-amd.tar.gz ($(du -h "$ROOT/fibbench-amd.tar.gz" | cut -f1))"
echo
echo "Перенесите архив на вторую систему любым способом, например:"
echo "    scp fibbench-amd.tar.gz пользователь@адрес:~/"
echo
echo "Затем на второй системе выполните:"
echo "    tar -xzf fibbench-amd.tar.gz && cd fibbench && ./run_on_amd.sh"
