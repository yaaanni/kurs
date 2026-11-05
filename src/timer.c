/* timer.c - реализация высокоточного таймера на основе POSIX clock_gettime */
#define _POSIX_C_SOURCE 200809L
#include <time.h>
#include "timer.h"

#ifndef CLOCK_MONOTONIC_RAW
#define CLOCK_MONOTONIC_RAW CLOCK_MONOTONIC
#endif

double timer_now(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

double timer_resolution(void)
{
    struct timespec ts;
    if (clock_getres(CLOCK_MONOTONIC_RAW, &ts) != 0)
        return 0.0;
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}
