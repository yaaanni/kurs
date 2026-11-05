/* stats.h - статистическая обработка серии измерений */
#ifndef STATS_H
#define STATS_H

#include <stddef.h>

/* Результат обработки серии измерений, все величины в секундах. */
typedef struct {
    double median;    /* медиана - основная оценка, устойчивая к выбросам */
    double minimum;   /* минимум - оценка при наименьшем влиянии помех */
    double mean;      /* среднее арифметическое */
    double stddev;    /* среднее квадратическое отклонение */
    size_t count;     /* число учтённых измерений */
} stats_t;

/* Обработка массива v из n измерений. Массив при обработке сортируется. */
stats_t stats_compute(double *v, size_t n);

#endif /* STATS_H */
