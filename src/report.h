/* report.h - вывод результатов измерений */
#ifndef REPORT_H
#define REPORT_H

#include <stdio.h>
#include "stats.h"
#include "sysinfo.h"

/* Одна строка результатов: значение параметра и статистика серии. */
typedef struct {
    double  param;    /* значение изменяемого параметра (n, число потоков и т. п.) */
    stats_t st;       /* статистика серии измерений */
    double  extra;    /* дополнительная величина (производительность, ускорение) */
} report_row_t;

void report_sysinfo(const sysinfo_t *info, double tmr_res);
void report_table(const char *title, const char *param_name,
                  const char *extra_name,
                  const report_row_t *rows, int count);

/* Экспорт результатов в файл формата CSV для построения графиков. */
int  report_csv_open(const char *path, FILE **out);
void report_csv_rows(FILE *out, const char *method, const char *cpu,
                     const char *param_name, const char *extra_name,
                     const report_row_t *rows, int count);

#endif /* REPORT_H */
