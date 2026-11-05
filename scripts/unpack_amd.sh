#!/bin/bash
# unpack_amd.sh - приём результатов со второй вычислительной системы
# и пересоздание раздела 5 пояснительной записки.
#
# Использование: ./scripts/unpack_amd.sh fibbench-amd-results.tar.gz

set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ARC="${1:-fibbench-amd-results.tar.gz}"
if [ ! -f "$ARC" ]; then
    # архив мог быть назван по другой метке вычислительной системы
    CAND=$(ls -1 fibbench-*-results.tar.gz 2>/dev/null | head -1)
    [ -n "$CAND" ] && ARC="$CAND"
fi
[ -f "$ARC" ] || { echo "Не найден архив $ARC"; exit 1; }

echo ">> распаковка $ARC"
tar -xzf "$ARC" -C "$ROOT"
echo "   принято:"
tar -tzf "$ARC" | sed 's/^/      /'

ls results/*.csv >/dev/null 2>&1 || { echo "!! В архиве нет файлов результатов"; exit 1; }
echo
echo ">> сводка по принятым данным"
python3 - <<'PY'
import csv, collections
import glob
rows = []
for f in sorted(glob.glob('results/*.csv')):
    rows += list(csv.DictReader(open(f, encoding='utf-8')))
rows = [r for r in rows if r['cpu'] != 'intel']
by = collections.Counter(r['method'] for r in rows)
for m in ('recursive', 'iterative', 'bignum', 'parallel'):
    print('      %-10s точек измерения: %d' % (m, by.get(m, 0)))
PY

echo
echo ">> построение графиков"
python3 scripts/make_plots.py
echo
echo ">> формирование разделов 3-5 пояснительной записки"
python3 scripts/build_chapters.py
echo
echo "Готово."
