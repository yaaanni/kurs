/* fib.c - реализация алгоритмов вычисления чисел Фибоначчи */
#define _POSIX_C_SOURCE 200809L
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include "fib.h"

/* Барьер оптимизации. Сообщает компилятору, что значение x может быть
   использовано извне, что запрещает удалить вычисление как не влияющее
   на результат или вынести его из тела цикла. */
#define DO_NOT_OPTIMIZE(x) __asm__ __volatile__("" : : "r"(x) : "memory")

/* Атрибут noinline запрещает компилятору подставлять тело функции
   в точку вызова: измеряется именно стоимость рекурсивных вызовов. */
__attribute__((noinline))
uint64_t fib_recursive(int n)
{
    if (n < 2)
        return (uint64_t)n;
    return fib_recursive(n - 1) + fib_recursive(n - 2);
}

uint64_t fib_iterative(int n)
{
    uint64_t prev = 0, curr = 1, next;
    int i;

    if (n < 2)
        return (uint64_t)n;
    for (i = 2; i <= n; i++) {
        next = prev + curr;
        prev = curr;
        curr = next;
    }
    return curr;
}

uint64_t fib_iterative_repeat(int n, long repeats)
{
    uint64_t sum = 0;
    long k;

    for (k = 0; k < repeats; k++) {
        uint64_t f = fib_iterative(n);
        DO_NOT_OPTIMIZE(f);       /* вычисление выполняется на каждой итерации */
        sum += f;
    }
    return sum;
}

uint64_t fib_memo(int n, uint64_t *table)
{
    int i;

    if (n < 2)
        return (uint64_t)n;
    table[0] = 0;
    table[1] = 1;
    for (i = 2; i <= n; i++)
        table[i] = table[i - 1] + table[i - 2];
    return table[n];
}

/* ------------------------- длинная арифметика ------------------------- */

int bignum_init(bignum_t *x, size_t cap)
{
    x->limb = (uint64_t *)calloc(cap, sizeof(uint64_t));
    if (x->limb == NULL)
        return -1;
    x->len = 1;
    x->cap = cap;
    return 0;
}

void bignum_free(bignum_t *x)
{
    free(x->limb);
    x->limb = NULL;
    x->len = 0;
    x->cap = 0;
}

/* Сложение чисел произвольной длины: c = a + b. */
static void bignum_add(const bignum_t *a, const bignum_t *b, bignum_t *c)
{
    size_t n = (a->len > b->len) ? a->len : b->len;
    uint64_t carry = 0;
    size_t i;

    for (i = 0; i < n; i++) {
        uint64_t x = (i < a->len) ? a->limb[i] : 0;
        uint64_t y = (i < b->len) ? b->limb[i] : 0;
        uint64_t s = x + y;
        uint64_t c1 = (s < x) ? 1u : 0u;      /* перенос от сложения x + y */
        uint64_t t = s + carry;
        uint64_t c2 = (t < s) ? 1u : 0u;      /* перенос от прибавления переноса */
        c->limb[i] = t;
        carry = c1 + c2;
    }
    if (carry != 0 && n < c->cap)
        c->limb[n++] = carry;
    c->len = n;
}

size_t fib_bignum(long n, bignum_t *a, bignum_t *b, bignum_t *c)
{
    long i;

    memset(a->limb, 0, a->cap * sizeof(uint64_t));
    memset(b->limb, 0, b->cap * sizeof(uint64_t));
    a->limb[0] = 0; a->len = 1;    /* F(0) */
    b->limb[0] = 1; b->len = 1;    /* F(1) */

    for (i = 2; i <= n; i++) {
        bignum_add(a, b, c);
        /* циклическая перестановка: a <- b, b <- c, c <- a */
        {
            bignum_t tmp = *a;
            *a = *b;
            *b = *c;
            *c = tmp;
        }
    }
    return (n < 1) ? a->len : b->len;
}

/* --------------------------- многопоточность -------------------------- */

typedef struct {
    int       n;          /* порядок вычисляемого числа */
    int       tasks;      /* общее число задач */
    int       next;       /* номер следующей свободной задачи */
    uint64_t  result;     /* контрольная сумма, накопленная потоками */
} pool_t;

typedef struct {
    pool_t   *pool;
    uint64_t  sum;        /* частичная сумма, накопленная одним потоком */
} worker_arg_t;

/* Рабочий поток забирает задачи из общей очереди по одной.
   Динамическое распределение исключает простой потоков при неравном
   делении числа задач на число потоков. */
static void *worker(void *raw)
{
    worker_arg_t *arg = (worker_arg_t *)raw;
    pool_t *pool = arg->pool;
    uint64_t sum = 0;

    for (;;) {
        /* атомарный захват очередного номера задачи */
        int idx = __atomic_fetch_add(&pool->next, 1, __ATOMIC_RELAXED);
        if (idx >= pool->tasks)
            break;
        sum += fib_recursive(pool->n);
    }
    arg->sum = sum;
    return NULL;
}

uint64_t fib_parallel(int n, int tasks, int threads)
{
    pthread_t    *tid;
    worker_arg_t *args;
    pool_t        pool;
    uint64_t      total = 0;
    int           i;

    if (threads < 1)
        threads = 1;
    tid  = (pthread_t *)calloc((size_t)threads, sizeof(pthread_t));
    args = (worker_arg_t *)calloc((size_t)threads, sizeof(worker_arg_t));
    if (tid == NULL || args == NULL) {
        free(tid);
        free(args);
        return 0;
    }

    pool.n = n;
    pool.tasks = tasks;
    pool.next = 0;
    pool.result = 0;

    for (i = 0; i < threads; i++) {
        args[i].pool = &pool;
        args[i].sum = 0;
        pthread_create(&tid[i], NULL, worker, &args[i]);
    }
    for (i = 0; i < threads; i++) {
        pthread_join(tid[i], NULL);
        total += args[i].sum;
    }
    free(tid);
    free(args);
    return total;
}
