#!/bin/bash
# run_on_amd.sh - проведение измерений на второй вычислительной системе.
#
# Запускать на машине со вторым сравниваемым процессором под управлением Linux:
#     ./run_on_amd.sh            - метка результатов amd (по умолчанию)
#     ./run_on_amd.sh имя        - произвольная метка, например ryzen5
#
# Скрипт последовательно: проверяет пригодность системы и исполняемого файла,
# предупреждает о посторонней нагрузке, переключает режим энергопотребления
# в performance, проводит измерения, при наличии графической среды снимает
# копии экрана и упаковывает результаты в архив для переноса обратно.

set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
LABEL="${1:-amd}"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
warn() { printf '\033[33m!! %s\033[0m\n' "$*"; }
die()  { printf '\033[31m!! %s\033[0m\n' "$*"; exit 1; }
ask()  { read -r -p "$1 [Д/н] " a; case "${a:-д}" in [нНnN]*) return 1;; *) return 0;; esac; }

# ------------------------------------------------------------------ 1. система
say "Шаг 1 из 6. Проверка вычислительной системы"
CPU=$(awk -F': ' '/model name/{print $2; exit}' /proc/cpuinfo)
echo "   Процессор: $CPU"
echo "   Ядер/потоков: $(grep -c '^processor' /proc/cpuinfo) логических"
echo "   Система: $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
echo "   Ядро: $(uname -r),  архитектура: $(uname -m)"

[ "$(uname -m)" = "x86_64" ] || die "Требуется архитектура x86-64."
case "$CPU" in
    *7840HS*) : ;;
    *) warn "Ожидался процессор AMD Ryzen 7 7840HS, обнаружен другой."
       warn "Измерения будут проведены, но в пояснительной записке"
       warn "необходимо указать фактическую модель процессора."
       ask "   Продолжить?" || exit 1 ;;
esac

# ------------------------------------------------- 2. исполняемый файл
say "Шаг 2 из 6. Проверка исполняемого файла"
[ -x ./fibbench ] || die "Файл fibbench не найден или не исполняемый."
if [ -f fibbench.sha256 ]; then
    if [ "$(sha256sum fibbench | awk '{print $1}')" = "$(cat fibbench.sha256)" ]; then
        echo "   Контрольная сумма совпадает: машинный код тот же, что на первой системе."
    else
        warn "Контрольная сумма не совпадает с эталонной."
    fi
fi
if ldd ./fibbench >/dev/null 2>&1; then
    warn "Файл скомпонован динамически и может не запуститься."
else
    echo "   Компоновка статическая, внешние библиотеки не требуются."
fi
if ./fibbench --help >/dev/null 2>&1; then
    echo "   Запуск выполняется успешно."
else
    warn "Исполняемый файл не запускается на этой системе."
    ask "   Пересобрать из исходного кода? (машинный код будет отличаться
   от первой системы, о чём нужно указать в пояснительной записке)" || exit 1
    command -v gcc >/dev/null || die "Компилятор GCC не установлен: sudo apt install build-essential"
    make clean && make || die "Сборка не удалась."
fi

# ------------------------------------------------------------ 3. нагрузка
say "Шаг 3 из 6. Проверка условий эксперимента"
LOAD=$(cut -d' ' -f1 /proc/loadavg)
echo "   Средняя загрузка системы: $LOAD"
HEAVY=$(ps -eo pcpu,comm --sort=-pcpu | awk 'NR>1 && $1>5 {printf "      %5.1f%%  %s\n", $1, $2}' | head -5)
if [ -n "$HEAVY" ]; then
    warn "Процессы, заметно нагружающие процессор:"
    echo "$HEAVY"
    echo "   Закройте среду разработки, браузер и прочие программы:"
    echo "   посторонняя нагрузка искажает результат даже при привязке"
    echo "   процесса к отдельному логическому ядру."
    ask "   Продолжить?" || exit 1
fi
if [ -d /sys/class/power_supply/BAT0 ]; then
    ST=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null)
    [ "$ST" = "Discharging" ] && warn "Ноутбук работает от батареи: подключите питание,
   иначе процессор будет работать на пониженной частоте."
fi

# ------------------------------------------------- 4. режим энергопотребления
say "Шаг 4 из 6. Переключение режима энергопотребления"
GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "недоступен")
echo "   Текущий режим: $GOV"
SUDO=""
if [ "$GOV" != "performance" ]; then
    if command -v pkexec >/dev/null && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        SUDO="pkexec"
        echo "   Сейчас появится диалог с запросом пароля администратора."
    elif command -v sudo >/dev/null; then
        SUDO="sudo"
        echo "   Потребуется пароль администратора."
    else
        warn "Нет ни pkexec, ни sudo: измерения пройдут в режиме $GOV."
        warn "Укажите этот режим в таблице характеристик стендов."
    fi
fi

# ----------------------------------------------------------- 5. измерения
say "Шаг 5 из 6. Измерения (около одной минуты)"
if [ -n "$SUDO" ]; then
    $SUDO "$ROOT/scripts/run_bench.sh" "$LABEL" || die "Прогон завершился с ошибкой."
else
    ./scripts/run_bench.sh "$LABEL" || die "Прогон завершился с ошибкой."
fi
[ -s "results/$LABEL.csv" ] || die "Файл результатов не создан."

# ------------------------------------------------------------ 6. копии экрана
say "Шаг 6 из 6. Копии экрана и упаковка результатов"
if [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ] && command -v gnome-terminal >/dev/null \
   && python3 -c 'import gi, PIL' 2>/dev/null; then
    if ask "   Снять копии экрана этой системы (откроются окна терминала)?"; then
        python3 scripts/shoot.py "$LABEL" || warn "Снять копии экрана не удалось."
    fi
else
    echo "   Графическая среда или нужные пакеты отсутствуют, копии экрана пропущены."
    echo "   При необходимости снимите их вручную: вывод lscpu и results/$LABEL.log"
fi

OUT="fibbench-$LABEL-results.tar.gz"
FILES="results/$LABEL.csv results/$LABEL.log"
for f in figures/screen_lscpu_$LABEL.png figures/screen_conditions_$LABEL.png \
         figures/screen_run_$LABEL.png figures/screen_run_${LABEL}_2.png; do
    [ -f "$f" ] && FILES="$FILES $f"
done
tar -czf "$OUT" $FILES

say "Готово"
echo "   Результаты: $ROOT/$OUT"
echo
echo "   Перенесите архив на первую систему, например:"
echo "       scp $OUT пользователь@адрес:~/abc/kursovaya/fibbench/"
echo "   и выполните там:"
echo "       ./scripts/unpack_amd.sh $OUT"
