/* report.c - реализация вывода результатов измерений */
#include <string.h>
#include "report.h"

/* Число печатных символов в строке UTF-8 (кириллица занимает два байта,
   поэтому спецификатор ширины printf к ней неприменим). */
static int utf8_width(const char *s)
{
    int n = 0;
    while (*s != '\0') {
        if ((*s & 0xC0) != 0x80)
            n++;
        s++;
    }
    return n;
}

/* Вывод строки, дополненной пробелами до заданной ширины.
   align < 0 - по левому краю, align > 0 - по правому, 0 - по центру. */
static void put_cell(const char *s, int width, int align)
{
    int pad = width - utf8_width(s);
    int left, right;

    if (pad < 0)
        pad = 0;
    if (align < 0)       { left = 0;           right = pad; }
    else if (align > 0)  { left = pad;         right = 0;   }
    else                 { left = pad / 2;     right = pad - left; }
    printf("%*s%s%*s", left, "", s, right, "");
}

#define LINE "+----------------+--------------+--------------+--------------+--------------+"

void report_sysinfo(const sysinfo_t *info, double tmr_res)
{
    printf("================================================================================\n");
    printf("  ИЗМЕРЕНИЕ ПРОИЗВОДИТЕЛЬНОСТИ ПРОЦЕССОРА НА ВЫЧИСЛЕНИИ ЧИСЕЛ ФИБОНАЧЧИ\n");
    printf("================================================================================\n");
    printf("  Процессор ............ %s\n", info->cpu_model);
    printf("  Ядер / потоков ....... %d / %d\n", info->cores, info->threads);
    printf("  Максимальная частота . %.0f МГц\n", info->freq_max_mhz);
    printf("  Режим частоты ........ %s\n", info->governor);
    printf("  Операционная система . %s\n", info->os_name);
    printf("  Версия ядра .......... %s\n", info->kernel);
    printf("  Компилятор ........... %s\n", info->compiler);
    printf("  Разрешение таймера ... %.0f нс (CLOCK_MONOTONIC_RAW)\n", tmr_res * 1e9);
    printf("================================================================================\n\n");
}

void report_table(const char *title, const char *param_name,
                  const char *extra_name,
                  const report_row_t *rows, int count)
{
    int i;

    printf("%s\n", title);
    printf("%s\n", LINE);
    printf("| ");  put_cell(param_name,    14, 0);
    printf(" | ");  put_cell("Медиана, мс",  12, 0);
    printf(" | ");  put_cell("Минимум, мс",  12, 0);
    printf(" | ");  put_cell("СКО, мс",      12, 0);
    printf(" | ");  put_cell(extra_name,     12, 0);
    printf(" |\n");
    printf("%s\n", LINE);
    for (i = 0; i < count; i++) {
        printf("| %14.0f | %12.3f | %12.3f | %12.3f | %12.2f |\n",
               rows[i].param,
               rows[i].st.median  * 1e3,
               rows[i].st.minimum * 1e3,
               rows[i].st.stddev  * 1e3,
               rows[i].extra);
    }
    printf("%s\n\n", LINE);
}

int report_csv_open(const char *path, FILE **out)
{
    *out = fopen(path, "w");
    if (*out == NULL)
        return -1;
    fprintf(*out, "method,cpu,param_name,param,median_s,min_s,mean_s,stddev_s,runs,extra_name,extra\n");
    return 0;
}

void report_csv_rows(FILE *out, const char *method, const char *cpu,
                     const char *param_name, const char *extra_name,
                     const report_row_t *rows, int count)
{
    int i;

    if (out == NULL)
        return;
    for (i = 0; i < count; i++)
        fprintf(out, "%s,%s,%s,%.0f,%.9f,%.9f,%.9f,%.9f,%zu,%s,%.6f\n",
                method, cpu, param_name, rows[i].param,
                rows[i].st.median, rows[i].st.minimum,
                rows[i].st.mean, rows[i].st.stddev, rows[i].st.count,
                extra_name, rows[i].extra);
}
