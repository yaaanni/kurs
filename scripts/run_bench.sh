#!/bin/bash
# run_bench.sh - прогон измерений с фиксацией условий эксперимента.
#
# Использование:  ./scripts/run_bench.sh <метка>        [обычный прогон]
#                 sudo ./scripts/run_bench.sh <метка>   [с режимом performance]
#
# Метка: intel - для системы на базе Intel Core i7-8565U
#        amd   - для системы на базе AMD Ryzen 7 7840HS
#
# Результаты сохраняются в results/<метка>.csv, протокол - в results/<метка>.log

set -u
LABEL="${1:-cpu}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/results"
CSV="$OUT/$LABEL.csv"
LOG="$OUT/$LABEL.log"
CORE=2                      # логическое ядро, к которому привязывается процесс

mkdir -p "$OUT"
cd "$ROOT" || exit 1
[ -x ./fibbench ] || make || exit 1

GOV_OLD=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
RESTORE=0
if [ "$(id -u)" -eq 0 ]; then
    echo ">> установка режима энергопотребления performance"
    cpupower frequency-set -g performance >/dev/null 2>&1 && RESTORE=1
fi

# Контроль чистоты условий: посторонняя нагрузка на процессор искажает
# результат даже при привязке процесса к отдельному логическому ядру,
# поскольку соседний логический поток того же ядра делит с ним
# исполнительные устройства.
LOAD=$(cut -d' ' -f1 /proc/loadavg)
if [ "$(echo "$LOAD > 0.60" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
    echo "!! ВНИМАНИЕ: средняя загрузка системы $LOAD"
    echo "!! Для получения достоверных результатов закройте посторонние"
    echo "!! программы (среду разработки, браузер) и повторите прогон."
    ps -eo pcpu,comm --sort=-pcpu | sed -n '2,6p' | sed 's/^/!!   /'
    echo
fi

echo ">> условия эксперимента" | tee "$LOG"
{
    echo "дата:            $(date '+%Y-%m-%d %H:%M:%S')"
    echo "governor:        $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)"
    echo "драйвер частоты: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver 2>/dev/null)"
    echo "привязка к ядру: $CORE"
    echo "средняя загрузка: $(cut -d' ' -f1-3 /proc/loadavg)"
} >> "$LOG"

# фоновый контроль фактической тактовой частоты во время измерений
( while true; do
      awk '/cpu MHz/{if($4>m) m=$4} END{printf "%.0f\n", m}' /proc/cpuinfo
      sleep 1
  done ) > "$OUT/.freq.$LABEL" 2>/dev/null &
FREQ_PID=$!

echo ">> прогон измерений (несколько минут)"
# Привязка к ядру выполняется самой программой (см. cpu_pin/cpu_unpin),
# так как многопоточному режиму нужны все логические ядра.
#
# Планировщик реального времени (chrt -f) намеренно не применяется: при числе
# потоков, равном числу логических ядер, потоки класса SCHED_FIFO вытесняют
# служебные потоки ядра, что резко увеличивает разброс измерений. Стабильность
# результатов обеспечивается привязкой к ядру, предварительным разогревом,
# режимом performance и оценкой по медиане серии.
./fibbench --label "$LABEL" --pin "$CORE" --csv "$CSV" "${@:2}" 2>&1 | tee -a "$LOG"

kill "$FREQ_PID" 2>/dev/null
FREQ_AVG=$(awk '{s+=$1; n++} END{if(n) printf "%.0f", s/n}' "$OUT/.freq.$LABEL" 2>/dev/null)
FREQ_MAX=$(awk 'BEGIN{m=0} {if($1>m) m=$1} END{printf "%.0f", m}' "$OUT/.freq.$LABEL" 2>/dev/null)
rm -f "$OUT/.freq.$LABEL"
echo "фактическая частота нагруженного ядра: средняя ${FREQ_AVG} МГц, максимальная ${FREQ_MAX} МГц" | tee -a "$LOG"

if [ "$RESTORE" -eq 1 ] && [ -n "$GOV_OLD" ]; then
    cpupower frequency-set -g "$GOV_OLD" >/dev/null 2>&1
    echo ">> восстановлен режим $GOV_OLD"
fi

# При запуске с повышенными правами файлы результатов возвращаются
# во владение обычному пользователю, иначе их нельзя будет перезаписать.
if [ -n "${PKEXEC_UID:-}" ]; then
    chown -R "$PKEXEC_UID" "$OUT" 2>/dev/null
elif [ -n "${SUDO_UID:-}" ]; then
    chown -R "$SUDO_UID" "$OUT" 2>/dev/null
fi
echo ">> готово: $CSV"
