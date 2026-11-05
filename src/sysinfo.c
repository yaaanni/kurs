/* sysinfo.c - реализация сбора сведений о вычислительной системе */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sched.h>
#include <sys/utsname.h>
#include "sysinfo.h"

/* Чтение первой строки файла с удалением завершающего перевода строки. */
static int read_line(const char *path, char *buf, size_t size)
{
    FILE *f = fopen(path, "r");

    buf[0] = '\0';
    if (f == NULL)
        return -1;
    if (fgets(buf, (int)size, f) != NULL)
        buf[strcspn(buf, "\n")] = '\0';
    fclose(f);
    return 0;
}

/* Поиск в /proc/cpuinfo значения поля с заданным именем. */
static void read_cpuinfo_field(const char *key, char *buf, size_t size)
{
    FILE *f = fopen("/proc/cpuinfo", "r");
    char line[512];
    size_t klen = strlen(key);

    buf[0] = '\0';
    if (f == NULL)
        return;
    while (fgets(line, sizeof(line), f) != NULL) {
        if (strncmp(line, key, klen) == 0) {
            char *colon = strchr(line, ':');
            if (colon != NULL) {
                char *val = colon + 1;
                while (*val == ' ' || *val == '\t')
                    val++;
                val[strcspn(val, "\n")] = '\0';
                snprintf(buf, size, "%s", val);
            }
            break;
        }
    }
    fclose(f);
}

/* Подсчёт числа физических ядер по уникальным идентификаторам core id. */
static int count_physical_cores(void)
{
    FILE *f = fopen("/proc/cpuinfo", "r");
    char line[512];
    int seen[512];
    int count = 0, id, i, found;

    if (f == NULL)
        return 0;
    while (fgets(line, sizeof(line), f) != NULL) {
        if (sscanf(line, "core id : %d", &id) == 1) {
            found = 0;
            for (i = 0; i < count; i++)
                if (seen[i] == id)
                    found = 1;
            if (!found && count < (int)(sizeof(seen) / sizeof(seen[0])))
                seen[count++] = id;
        }
    }
    fclose(f);
    return count;
}

void sysinfo_collect(sysinfo_t *info)
{
    struct utsname un;
    char buf[128];

    memset(info, 0, sizeof(*info));

    read_cpuinfo_field("model name", info->cpu_model, sizeof(info->cpu_model));
    if (info->cpu_model[0] == '\0')
        snprintf(info->cpu_model, sizeof(info->cpu_model), "%s", "неизвестно");

    info->threads = (int)sysconf(_SC_NPROCESSORS_ONLN);
    info->cores = count_physical_cores();
    if (info->cores == 0)
        info->cores = info->threads;

    read_line("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
              info->governor, sizeof(info->governor));
    if (info->governor[0] == '\0')
        snprintf(info->governor, sizeof(info->governor), "%s", "недоступен");

    if (read_line("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq",
                  buf, sizeof(buf)) == 0 && buf[0] != '\0')
        info->freq_max_mhz = atof(buf) / 1000.0;   /* кГц -> МГц */

    if (uname(&un) == 0)
        snprintf(info->kernel, sizeof(info->kernel), "%s", un.release);

    read_line("/etc/os-release", buf, sizeof(buf));
    {
        char *p = strchr(buf, '"');
        if (p != NULL) {
            char *q = strrchr(buf, '"');
            if (q != NULL && q > p) {
                *q = '\0';
                snprintf(info->os_name, sizeof(info->os_name), "%s", p + 1);
            }
        } else {
            snprintf(info->os_name, sizeof(info->os_name), "%s", buf);
        }
    }

    snprintf(info->compiler, sizeof(info->compiler), "GCC %d.%d.%d",
             __GNUC__, __GNUC_MINOR__, __GNUC_PATCHLEVEL__);
}

int cpu_pin(int cpu)
{
    cpu_set_t set;

    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    return sched_setaffinity(0, sizeof(set), &set);
}

int cpu_unpin(void)
{
    cpu_set_t set;
    long i, n = sysconf(_SC_NPROCESSORS_ONLN);

    CPU_ZERO(&set);
    for (i = 0; i < n && i < CPU_SETSIZE; i++)
        CPU_SET((int)i, &set);
    return sched_setaffinity(0, sizeof(set), &set);
}

int cpu_available(void)
{
    cpu_set_t set;

    CPU_ZERO(&set);
    if (sched_getaffinity(0, sizeof(set), &set) != 0)
        return (int)sysconf(_SC_NPROCESSORS_ONLN);
    return CPU_COUNT(&set);
}
