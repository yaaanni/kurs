#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_plots.py - построение графиков сравнения производительности процессоров.

Графики выполняются по правилам подраздела 3.11 СТП 01-2024 (Р50-77-88):
оси со шкалами и координатной сеткой, единицы измерения в конце шкалы,
зависимости различаются типом линии и маркером, а не цветом, так как
пояснительная записка печатается в чёрно-белом исполнении.

Использование: python3 scripts/make_plots.py [results/*.csv]
"""
import csv
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
FIGDIR = os.path.join(ROOT, "figures")

# подписи и стили линий для каждой вычислительной системы
CPU_LABEL = {
    "intel": "Intel Core i7-8565U",
    "amd":   "AMD Ryzen 7 7840HS",
}
CPU_STYLE = {
    "intel": dict(linestyle="-",  marker="s", color="black", markerfacecolor="white"),
    "amd":   dict(linestyle="--", marker="o", color="black", markerfacecolor="black"),
}

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "DejaVu Serif", "Times New Roman"],
    "font.size": 11,
    "axes.linewidth": 1.0,
    "lines.linewidth": 1.6,
    "lines.markersize": 5,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


def load(paths):
    """Чтение CSV-файлов в структуру data[method][cpu] = [(param, median_s, extra)]."""
    data = defaultdict(lambda: defaultdict(list))
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                data[r["method"]][r["cpu"]].append(
                    (float(r["param"]), float(r["median_s"]), float(r["extra"]))
                )
    for m in data:
        for c in data[m]:
            data[m][c].sort()
    return data


def new_axes(figsize=(6.1, 4.0)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.grid(True, which="major", linestyle=":", linewidth=0.6, color="0.45")
    ax.grid(True, which="minor", linestyle=":", linewidth=0.4, color="0.7")
    ax.tick_params(direction="in", top=True, right=True)
    return fig, ax


def finish(fig, ax, xlabel, ylabel, name, legend_loc="best"):
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc=legend_loc, frameon=True, edgecolor="black", framealpha=1.0)
    os.makedirs(FIGDIR, exist_ok=True)
    path = os.path.join(FIGDIR, name)
    fig.savefig(path)
    plt.close(fig)
    print("  сохранён", os.path.relpath(path, ROOT))


def plot_xy(data, method, name, xlabel, ylabel, logy=False, scale=1e3):
    if method not in data:
        return
    fig, ax = new_axes()
    for cpu in ("intel", "amd"):
        rows = data[method].get(cpu)
        if not rows:
            continue
        xs = [r[0] for r in rows]
        ys = [r[1] * scale for r in rows]
        ax.plot(xs, ys, label=CPU_LABEL.get(cpu, cpu), **CPU_STYLE.get(cpu, {}))
    if logy:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ScalarFormatter())
    finish(fig, ax, xlabel, ylabel, name)


def plot_speedup(data, name):
    if "parallel" not in data:
        return
    fig, ax = new_axes()
    maxt = 1
    for cpu in ("intel", "amd"):
        rows = data["parallel"].get(cpu)
        if not rows:
            continue
        xs = [r[0] for r in rows]
        ys = [r[2] for r in rows]
        maxt = max(maxt, int(max(xs)))
        ax.plot(xs, ys, label=CPU_LABEL.get(cpu, cpu), **CPU_STYLE.get(cpu, {}))
    ax.plot([1, maxt], [1, maxt], linestyle="-.", linewidth=1.0, color="0.5",
            label="Идеальное ускорение")
    finish(fig, ax, "Число потоков", "Ускорение, раз", name, legend_loc="upper left")


def plot_ratio(data, name):
    """Столбиковая диаграмма: во сколько раз AMD быстрее Intel по каждому методу."""
    titles = {
        "recursive": "Наивная\nрекурсия",
        "iterative": "Итерационный\nметод",
        "bignum":    "Длинная\nарифметика",
        "parallel":  "Многопоточный\nрежим",
    }
    names, vals = [], []
    for m, title in titles.items():
        i = {r[0]: r[1] for r in data.get(m, {}).get("intel", [])}
        a = {r[0]: r[1] for r in data.get(m, {}).get("amd", [])}
        if m == "parallel":
            # сравниваются наилучшие достигнутые времена
            if not i or not a:
                continue
            ratio = min(i.values()) / min(a.values())
        else:
            common = sorted(set(i) & set(a))
            if not common:
                continue
            p = common[-1]          # наибольшее значение параметра
            ratio = i[p] / a[p]
        names.append(title)
        vals.append(ratio)
    if not names:
        print("  диаграмма ускорения пропущена: нет данных обеих систем")
        return
    fig, ax = new_axes(figsize=(6.1, 3.6))
    bars = ax.bar(names, vals, width=0.5, color="white", edgecolor="black",
                  hatch="///", linewidth=1.2)
    ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.05, "%.2f" % v,
                ha="center", va="bottom")
    ax.set_ylim(0, max(vals) * 1.25)
    ax.grid(axis="x", visible=False)
    finish(fig, ax, "", "Ускорение AMD относительно Intel, раз", name)


def main():
    paths = sys.argv[1:]
    if not paths:
        paths = [os.path.join(RESULTS, f)
                 for f in sorted(os.listdir(RESULTS)) if f.endswith(".csv")]
    if not paths:
        print("Не найдено ни одного файла результатов в", RESULTS)
        return 1
    print("Исходные данные:", ", ".join(os.path.basename(p) for p in paths))
    data = load(paths)

    plot_xy(data, "recursive", "fig_recursive.png",
            "Порядок вычисляемого числа n",
            "Время выполнения t, мс", logy=True)
    plot_xy(data, "iterative", "fig_iterative.png",
            "Порядок вычисляемого числа n",
            "Время выполнения t, мс")
    plot_xy(data, "bignum", "fig_bignum.png",
            "Порядок вычисляемого числа n",
            "Время выполнения t, мс")
    plot_speedup(data, "fig_parallel.png")
    plot_ratio(data, "fig_ratio.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
