/*
 * main.c - программа сравнения производительности процессоров
 *          на основе вычисления чисел Фибоначчи.
 *
 * Курсовой проект по дисциплине «Архитектура вычислительных систем».
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "fib.h"
#include "timer.h"
#include "stats.h"
#include "sysinfo.h"
#include "report.h"

#define MAX_RUNS   64
#define MAX_ROWS   64

/* Параметры эксперимента, задаваемые из командной строки. */
typedef struct {
    int  runs;          /* число учитываемых прогонов в серии */
    int  warmup;        /* число прогонов прогрева (отбрасываются) */
    int  rec_from;      /* диапазон n для рекурсивного метода */
    int  rec_to;
    long iter_repeats;  /* число повторов итерационного метода */
    long big_from;      /* диапазон n для длинной арифметики */
    long big_to;
    long big_step;
    int  par_n;         /* порядок числа для многопоточного режима */
    int  pin_cpu;       /* логическое ядро для однопоточных измерений */
    int  par_tasks;     /* общее число задач (одинаково на обеих системах) */
    char label[64];     /* метка вычислительной системы в CSV */
    char csv[256];      /* путь к файлу результатов */
} config_t;

/* Тип измеряемой функции: выполняет полезную работу и возвращает
   контрольное значение, которое не позволяет оптимизатору удалить вызов. */
typedef uint64_t (*payload_fn)(void *ctx);

static uint64_t g_sink;   /* накопитель контрольных значений */

/* Одно измерение: время выполнения одного вызова полезной нагрузки, с. */
static double measure_once(payload_fn f, void *ctx)
{
    double t0, t1;

    t0 = timer_now();
    g_sink += f(ctx);
    t1 = timer_now();
    return t1 - t0;
}

/* Серия измерений с прогревом и статистической обработкой. */
static stats_t run_series(payload_fn f, void *ctx, int warmup, int runs)
{
    double v[MAX_RUNS];
    int i;

    if (runs > MAX_RUNS)
        runs = MAX_RUNS;
    for (i = 0; i < warmup; i++)
        (void)measure_once(f, ctx);          /* прогрев: результат отбрасывается */
    for (i = 0; i < runs; i++)
        v[i] = measure_once(f, ctx);
    return stats_compute(v, (size_t)runs);
}

/* ----------------------- контексты полезной нагрузки ---------------------- */

typedef struct { int n; }                        ctx_rec_t;
typedef struct { int n; long repeats; }          ctx_iter_t;
typedef struct { long n; bignum_t a, b, c; }     ctx_big_t;
typedef struct { int n, tasks, threads; }        ctx_par_t;

static uint64_t pay_rec(void *p)
{
    ctx_rec_t *c = (ctx_rec_t *)p;
    return fib_recursive(c->n);
}

static uint64_t pay_iter(void *p)
{
    ctx_iter_t *c = (ctx_iter_t *)p;
    return fib_iterative_repeat(c->n, c->repeats);
}

static uint64_t pay_big(void *p)
{
    ctx_big_t *c = (ctx_big_t *)p;
    return (uint64_t)fib_bignum(c->n, &c->a, &c->b, &c->c);
}

static uint64_t pay_par(void *p)
{
    ctx_par_t *c = (ctx_par_t *)p;
    return fib_parallel(c->n, c->tasks, c->threads);
}

/* --------------------------- проверка корректности ------------------------ */

/* Сверка результатов разных методов между собой и с контрольными значениями. */
static int verify(void)
{
    static const struct { int n; uint64_t f; } ref[] = {
        { 10, 55ULL }, { 20, 6765ULL }, { 30, 832040ULL },
        { 50, 12586269025ULL }, { 93, 12200160415121876738ULL }
    };
    uint64_t table[128];
    size_t k;
    int n, ok = 1;

    for (k = 0; k < sizeof(ref) / sizeof(ref[0]); k++) {
        n = ref[k].n;
        if (fib_iterative(n) != ref[k].f)      ok = 0;
        if (fib_memo(n, table) != ref[k].f)    ok = 0;
        if (n <= 30 && fib_recursive(n) != ref[k].f) ok = 0;
    }
    return ok;
}

/* ------------------------------ режимы работы ----------------------------- */

static void bench_recursive(const config_t *cfg, FILE *csv)
{
    report_row_t rows[MAX_ROWS];
    ctx_rec_t ctx;
    int n, cnt = 0;

    for (n = cfg->rec_from; n <= cfg->rec_to && cnt < MAX_ROWS; n++, cnt++) {
        ctx.n = n;
        rows[cnt].param = (double)n;
        rows[cnt].st = run_series(pay_rec, &ctx, cfg->warmup, cfg->runs);
        /* число рекурсивных вызовов равно 2*F(n+1) - 1 */
        rows[cnt].extra = (2.0 * (double)fib_iterative(n + 1) - 1.0)
                          / rows[cnt].st.median * 1e-6;   /* млн вызовов в секунду */
    }
    report_table("МЕТОД 1. Наивная рекурсия, сложность O(2^n)",
                 "Порядок n", "Млн выз./с", rows, cnt);
    report_csv_rows(csv, "recursive", cfg->label, "n", "mcalls_per_s", rows, cnt);
}

static void bench_iterative(const config_t *cfg, FILE *csv)
{
    report_row_t rows[MAX_ROWS];
    ctx_iter_t ctx;
    int n, cnt = 0;

    ctx.repeats = cfg->iter_repeats;
    for (n = 10; n <= 90 && cnt < MAX_ROWS; n += 10, cnt++) {
        ctx.n = n;
        rows[cnt].param = (double)n;
        rows[cnt].st = run_series(pay_iter, &ctx, cfg->warmup, cfg->runs);
        /* число выполненных сложений */
        rows[cnt].extra = (double)(n - 1) * (double)cfg->iter_repeats
                          / rows[cnt].st.median * 1e-6;   /* млн сложений в секунду */
    }
    report_table("МЕТОД 2. Итерационный метод, сложность O(n)",
                 "Порядок n", "Млн слож./с", rows, cnt);
    report_csv_rows(csv, "iterative", cfg->label, "n", "madds_per_s", rows, cnt);
}

static void bench_bignum(const config_t *cfg, FILE *csv)
{
    report_row_t rows[MAX_ROWS];
    ctx_big_t ctx;
    long n;
    size_t cap;
    int cnt = 0;

    /* ёмкость массива с запасом: F(n) содержит около 0,695*n двоичных разрядов */
    cap = (size_t)(cfg->big_to * 0.695 / 64.0) + 8;
    if (bignum_init(&ctx.a, cap) != 0 ||
        bignum_init(&ctx.b, cap) != 0 ||
        bignum_init(&ctx.c, cap) != 0) {
        fprintf(stderr, "Ошибка: недостаточно оперативной памяти\n");
        return;
    }
    for (n = cfg->big_from; n <= cfg->big_to && cnt < MAX_ROWS;
         n += cfg->big_step, cnt++) {
        ctx.n = n;
        rows[cnt].param = (double)n;
        rows[cnt].st = run_series(pay_big, &ctx, cfg->warmup, cfg->runs);
        /* объём рабочего набора: три числа по 0,695*n/8 байт */
        rows[cnt].extra = 3.0 * (double)n * 0.695 / 8.0 / 1024.0;   /* КиБ */
    }
    report_table("МЕТОД 3. Длинная арифметика, растущий рабочий набор",
                 "Порядок n", "Набор, КиБ", rows, cnt);
    report_csv_rows(csv, "bignum", cfg->label, "n", "workset_kib", rows, cnt);

    bignum_free(&ctx.a);
    bignum_free(&ctx.b);
    bignum_free(&ctx.c);
}

static void bench_parallel(const config_t *cfg, FILE *csv, int max_threads)
{
    static double v[MAX_ROWS][MAX_RUNS];
    report_row_t rows[MAX_ROWS];
    ctx_par_t ctx;
    double t1 = 0.0;
    int t, k, cnt;

    if (max_threads > MAX_ROWS)
        max_threads = MAX_ROWS;
    cnt = max_threads;
    ctx.n = cfg->par_n;
    ctx.tasks = cfg->par_tasks;   /* объём работы не зависит от числа потоков */

    /* Измерения для разных значений числа потоков чередуются: за время
       прогона процессор разогревается и снижает тактовую частоту, и если
       выполнять серии последовательно, то разогрев вносил бы в результаты
       систематическую погрешность, зависящую от номера серии. */
    for (k = 0; k < cfg->warmup + cfg->runs; k++) {
        for (t = 1; t <= cnt; t++) {
            double dt;
            ctx.threads = t;
            dt = measure_once(pay_par, &ctx);
            if (k >= cfg->warmup)
                v[t - 1][k - cfg->warmup] = dt;
        }
    }

    for (t = 1; t <= cnt; t++) {
        rows[t - 1].param = (double)t;
        rows[t - 1].st = stats_compute(v[t - 1], (size_t)cfg->runs);
        if (t == 1)
            t1 = rows[0].st.median;
        rows[t - 1].extra = t1 / rows[t - 1].st.median;
    }
    report_table("МЕТОД 4. Многопоточный режим, масштабируемость по потокам",
                 "Потоков", "Ускорение", rows, cnt);
    report_csv_rows(csv, "parallel", cfg->label, "threads", "speedup", rows, cnt);
}

/* -------------------------------- интерфейс ------------------------------- */

static void usage(const char *prog)
{
    printf("Использование: %s [параметры]\n\n", prog);
    printf("  -l, --label ИМЯ      метка вычислительной системы (intel | amd)\n");
    printf("  -o, --csv ФАЙЛ       файл результатов в формате CSV\n");
    printf("  -r, --runs N         число учитываемых прогонов в серии (по умолчанию 11)\n");
    printf("  -w, --warmup N       число прогонов прогрева (по умолчанию 3)\n");
    printf("      --rec A B        диапазон порядка n для рекурсивного метода\n");
    printf("      --iter-repeats N число повторов итерационного метода\n");
    printf("      --big A B S      диапазон и шаг n для длинной арифметики\n");
    printf("      --par N T        порядок n и общее число задач\n");
    printf("      --pin N          логическое ядро для однопоточных измерений\n"
           "  -q, --quick          укороченный прогон для проверки работоспособности\n");
    printf("  -h, --help           вывод настоящей справки\n");
}

int main(int argc, char **argv)
{
    config_t cfg;
    sysinfo_t info;
    FILE *csv = NULL;
    double t_start, t_total;
    int i, max_threads;

    /* значения параметров по умолчанию */
    cfg.runs = 11;
    cfg.warmup = 3;
    cfg.rec_from = 25;
    cfg.rec_to = 38;
    cfg.iter_repeats = 1000000L;
    cfg.big_from = 20000L;
    cfg.big_to = 200000L;
    cfg.big_step = 20000L;
    cfg.par_n = 30;
    cfg.pin_cpu = 2;
    cfg.par_tasks = 128;
    snprintf(cfg.label, sizeof(cfg.label), "%s", "cpu");
    snprintf(cfg.csv, sizeof(cfg.csv), "%s", "results.csv");

    for (i = 1; i < argc; i++) {
        if ((!strcmp(argv[i], "-l") || !strcmp(argv[i], "--label")) && i + 1 < argc)
            snprintf(cfg.label, sizeof(cfg.label), "%s", argv[++i]);
        else if ((!strcmp(argv[i], "-o") || !strcmp(argv[i], "--csv")) && i + 1 < argc)
            snprintf(cfg.csv, sizeof(cfg.csv), "%s", argv[++i]);
        else if ((!strcmp(argv[i], "-r") || !strcmp(argv[i], "--runs")) && i + 1 < argc)
            cfg.runs = atoi(argv[++i]);
        else if ((!strcmp(argv[i], "-w") || !strcmp(argv[i], "--warmup")) && i + 1 < argc)
            cfg.warmup = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--rec") && i + 2 < argc) {
            cfg.rec_from = atoi(argv[++i]);
            cfg.rec_to = atoi(argv[++i]);
        } else if (!strcmp(argv[i], "--iter-repeats") && i + 1 < argc)
            cfg.iter_repeats = atol(argv[++i]);
        else if (!strcmp(argv[i], "--big") && i + 3 < argc) {
            cfg.big_from = atol(argv[++i]);
            cfg.big_to = atol(argv[++i]);
            cfg.big_step = atol(argv[++i]);
        } else if (!strcmp(argv[i], "--par") && i + 2 < argc) {
            cfg.par_n = atoi(argv[++i]);
            cfg.par_tasks = atoi(argv[++i]);
        } else if (!strcmp(argv[i], "--pin") && i + 1 < argc)
            cfg.pin_cpu = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-q") || !strcmp(argv[i], "--quick")) {
            cfg.runs = 3; cfg.warmup = 1;
            cfg.rec_from = 25; cfg.rec_to = 30;
            cfg.iter_repeats = 100000L;
            cfg.big_from = 20000L; cfg.big_to = 60000L; cfg.big_step = 20000L;
            cfg.par_n = 28; cfg.par_tasks = 32;
        } else if (!strcmp(argv[i], "-h") || !strcmp(argv[i], "--help")) {
            usage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "Неизвестный параметр: %s\n", argv[i]);
            usage(argv[0]);
            return 1;
        }
    }
    if (cfg.runs < 1 || cfg.runs > MAX_RUNS) {
        fprintf(stderr, "Ошибка: число прогонов должно быть от 1 до %d\n", MAX_RUNS);
        return 1;
    }

    sysinfo_collect(&info);
    max_threads = info.threads;
    report_sysinfo(&info, timer_resolution());

    printf("  Проверка корректности вычислений ... %s\n\n",
           verify() ? "пройдена" : "НЕ ПРОЙДЕНА");
    printf("  Серия: %d прогонов прогрева + %d учитываемых прогонов\n\n",
           cfg.warmup, cfg.runs);

    if (report_csv_open(cfg.csv, &csv) != 0)
        fprintf(stderr, "Предупреждение: не удалось открыть файл %s\n", cfg.csv);

    /* Предварительный разогрев: вывод процессора из состояния пониженного
       энергопотребления на установившуюся тактовую частоту. Без него первые
       измерения серии оказываются завышенными. */
    {
        double t_warm = timer_now();
        while (timer_now() - t_warm < 0.5)
            g_sink += fib_recursive(24);
    }

    t_start = timer_now();

    /* Однопоточные методы измеряются на одном закреплённом логическом ядре. */
    if (cpu_pin(cfg.pin_cpu) == 0)
        printf("  Процесс привязан к логическому ядру %d\n\n", cfg.pin_cpu);
    else
        printf("  Предупреждение: привязка к ядру недоступна\n\n");
    bench_recursive(&cfg, csv);
    bench_iterative(&cfg, csv);
    bench_bignum(&cfg, csv);

    /* Многопоточный режим требует доступа ко всем логическим ядрам. */
    cpu_unpin();
    max_threads = cpu_available();
    printf("  Привязка снята, доступно логических ядер: %d\n\n", max_threads);
    bench_parallel(&cfg, csv, max_threads);

    t_total = timer_now() - t_start;

    if (csv != NULL) {
        fclose(csv);
        printf("  Результаты сохранены в файл %s\n", cfg.csv);
    }
    printf("  Общее время тестирования: %.1f с\n", t_total);
    printf("  Контрольная сумма: %llu\n",
           (unsigned long long)g_sink);
    return 0;
}
