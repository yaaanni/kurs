/* stats.c - реализация статистической обработки серии измерений */
#include <stdlib.h>
#include <math.h>
#include "stats.h"

static int cmp_double(const void *p, const void *q)
{
    double a = *(const double *)p;
    double b = *(const double *)q;
    return (a > b) - (a < b);
}

stats_t stats_compute(double *v, size_t n)
{
    stats_t s;
    double sum = 0.0, acc = 0.0;
    size_t i;

    s.median = s.minimum = s.mean = s.stddev = 0.0;
    s.count = n;
    if (n == 0)
        return s;

    qsort(v, n, sizeof(double), cmp_double);
    s.minimum = v[0];
    s.median = (n % 2 != 0) ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);

    for (i = 0; i < n; i++)
        sum += v[i];
    s.mean = sum / (double)n;

    if (n > 1) {
        for (i = 0; i < n; i++) {
            double d = v[i] - s.mean;
            acc += d * d;
        }
        s.stddev = sqrt(acc / (double)(n - 1));
    }
    return s;
}
