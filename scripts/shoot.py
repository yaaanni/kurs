#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shoot.py - получение копий экрана с окном терминала.

Команда выполняется в окне gnome-terminal, размер которого подобран под объём
выводимого текста; снимок экрана запрашивается через xdg-desktop-portal, после
чего изображение обрезается точно по границам окна. На время съёмки создаётся
временный профиль терминала со светлым фоном (пояснительная записка печатается
в чёрно-белом исполнении); по окончании работы профиль удаляется.

Использование: python3 scripts/shoot.py [метка-системы]
"""
import os
import subprocess
import sys
import time
import uuid

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGDIR = os.path.join(ROOT, 'figures')
TMP = '/tmp/kp-shoot'

PROFILE_NAME = 'KP-Screenshot'
PROFILE_PATH = '/org/gnome/terminal/legacy/profiles:'
BG = (0xFD, 0xFD, 0xFB)          # фон временного профиля, служит меткой окна
BG_HEX = '#FDFDFB'

CELL_W, CELL_H = 18.1, 36.3      # размер знакоместа при масштабе 1,0, пиксели
HEADER_PX = 56                   # высота заголовка окна
SCREEN_MARGIN = 90               # запас по высоте экрана
PROMPT = 'yana@%s:~/fibbench$'


# --------------------------------------------------------------- профиль
def dconf(*args):
    subprocess.run(['dconf'] + list(args), check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def dconf_read(key):
    r = subprocess.run(['dconf', 'read', key], capture_output=True, text=True)
    return r.stdout.strip()


class TempProfile:
    def __init__(self):
        self.uuid = str(uuid.uuid4())
        self.old_list = dconf_read(PROFILE_PATH + '/list')

    def __enter__(self):
        p = '%s/:%s' % (PROFILE_PATH, self.uuid)
        for key, val in (
            ('visible-name', "'%s'" % PROFILE_NAME),
            ('use-theme-colors', 'false'),
            ('background-color', "'%s'" % BG_HEX),
            ('foreground-color', "'#101010'"),
            ('bold-color-same-as-fg', 'true'),
            ('use-system-font', 'false'),
            ('font', "'DejaVu Sans Mono 11'"),
            ('audible-bell', 'false'),
            ('scrollbar-policy', "'never'"),
            ('use-transparent-background', 'false'),
            ('cursor-blink-mode', "'off'"),
        ):
            dconf('write', '%s/%s' % (p, key), val)
        cur = self.old_list
        new = "['%s']" % self.uuid if not cur or cur == '[]' \
            else cur[:-1] + ", '%s']" % self.uuid
        dconf('write', PROFILE_PATH + '/list', new)
        time.sleep(0.4)
        return self

    def __exit__(self, *exc):
        dconf('reset', '-f', '%s/:%s/' % (PROFILE_PATH, self.uuid))
        if self.old_list and self.old_list != '[]':
            dconf('write', PROFILE_PATH + '/list', self.old_list)
        else:
            dconf('reset', PROFILE_PATH + '/list')
        print('  временный профиль терминала удалён')


# --------------------------------------------------------------- снимок
def portal_screenshot(dst):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    proxy = Gio.DBusProxy.new_sync(
        bus, Gio.DBusProxyFlags.NONE, None,
        'org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop',
        'org.freedesktop.portal.Screenshot', None)
    loop = GLib.MainLoop()
    out = {}

    def on_response(conn, sender, path, iface, signal, params):
        out['code'] = params[0]
        out['uri'] = dict(params[1]).get('uri')
        loop.quit()

    sub = bus.signal_subscribe(None, 'org.freedesktop.portal.Request', 'Response',
                               None, None, Gio.DBusSignalFlags.NONE, on_response)
    proxy.call_sync(
        'Screenshot',
        GLib.Variant('(sa{sv})',
                     ('', {'handle_token': GLib.Variant('s', 'kp%s' % uuid.uuid4().hex[:8]),
                           'interactive': GLib.Variant('b', False)})),
        Gio.DBusCallFlags.NONE, -1, None)
    GLib.timeout_add_seconds(25, lambda: (loop.quit(), False)[1])
    loop.run()
    bus.signal_unsubscribe(sub)
    if out.get('code') != 0 or not out.get('uri'):
        raise RuntimeError('портал не вернул снимок экрана: %r' % out)
    src = GLib.filename_from_uri(out['uri'])[0]
    os.replace(src, dst)


def crop_window(path):
    """Обрезка снимка точно по границам окна терминала."""
    im = Image.open(path).convert('RGB')
    w, h = im.size
    px = im.load()

    xs0, ys0, xs1, ys1 = w, h, -1, -1
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if px[x, y] == BG:
                xs0 = min(xs0, x); xs1 = max(xs1, x)
                ys0 = min(ys0, y); ys1 = max(ys1, y)
    if xs1 < 0:
        raise RuntimeError('окно терминала не найдено на снимке экрана')

    # уточнение границ области текста с точностью до пикселя
    while xs0 > 0 and px[xs0 - 1, (ys0 + ys1) // 2] == BG:
        xs0 -= 1
    while xs1 + 1 < w and px[xs1 + 1, (ys0 + ys1) // 2] == BG:
        xs1 += 1
    while ys1 + 1 < h and px[(xs0 + xs1) // 2, ys1 + 1] == BG:
        ys1 += 1
    while ys0 > 0 and px[(xs0 + xs1) // 2, ys0 - 1] == BG:
        ys0 -= 1

    # заголовок окна: однородная полоса над областью текста. Образец цвета
    # берётся у левого края, где нет ни надписи, ни кнопок управления окном.
    hx = xs0 + 10
    head = px[hx, ys0 - 4]
    top = ys0
    while top > 0 and ys0 - top < HEADER_PX + 24:
        c = px[hx, top - 1]
        if sum(abs(a - b) for a, b in zip(c, head)) > 60:
            break
        top -= 1

    im = im.crop((xs0, top, xs1 + 1, ys1 + 1))
    im.save(path, dpi=(300, 300))
    return im.size


# --------------------------------------------------------------- съёмка
def geometry_for(prompt_line, body):
    """Ширина окна определяется выводом команды; длинная строка приглашения
    переносится по словам, как это происходит в настоящем терминале."""
    lines = body.rstrip('\n').split('\n')
    cols = max(60, min(96, max(len(l) for l in lines) + 3))
    wrapped = -(-len(prompt_line) // cols)          # число строк после переноса
    rows = len(lines) + wrapped + 2
    avail_h = 1440 - 37 - HEADER_PX - SCREEN_MARGIN
    zoom = min(1.45, avail_h / (rows * CELL_H), 2400.0 / (cols * CELL_W))
    return cols, rows, round(max(0.62, zoom), 2)


def shoot(name, command, title, host='intel-stand', extra_wait=0.0):
    """Запуск команды в окне терминала и получение снимка экрана."""
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(FIGDIR, exist_ok=True)
    pidfile = os.path.join(TMP, 'pid')
    outfile = os.path.join(TMP, 'out')

    # предварительный прогон команды, чтобы подобрать размер окна
    pre = subprocess.run(['bash', '-lc', 'cd %s && %s' % (ROOT, command)],
                         capture_output=True, text=True)
    body = (pre.stdout or '') + (pre.stderr or '')
    prompt_line = '%s %s' % (PROMPT % host, command)
    cols, rows, zoom = geometry_for(prompt_line, body)

    inner = (
        "cd %s && clear && printf '\\033]0;%s\\007' && "
        "printf '%%s\\n' %s && { %s ; } ; printf '\\n' ; "
        "echo $$ > %s ; read -r -t 3600"
        % (ROOT, title, _q(prompt_line), command, pidfile)
    )
    dst = os.path.join(FIGDIR, name)
    for attempt in range(1, 4):
        if os.path.exists(pidfile):
            os.remove(pidfile)
        subprocess.run(['gnome-terminal',
                        '--geometry=%dx%d+200+120' % (cols, rows),
                        '--hide-menubar', '--zoom=%s' % zoom,
                        '--profile=' + PROFILE_NAME,
                        '--', 'bash', '-lc', inner], check=False)
        # окно считается готовым, когда оболочка записала свой номер процесса
        for _ in range(60):
            if os.path.exists(pidfile):
                break
            time.sleep(0.2)
        time.sleep(1.4 + extra_wait)
        try:
            portal_screenshot(dst)
            size = crop_window(dst)
            print('  %-26s %4dx%-4d  (%dx%d, масштаб %s)'
                  % (name, size[0], size[1], cols, rows, zoom))
            break
        except RuntimeError as e:
            print('  %s: попытка %d неудачна (%s)' % (name, attempt, e))
            if attempt == 3:
                raise
        finally:
            _close(pidfile)


def _close(pidfile):
    if os.path.exists(pidfile):
        try:
            os.kill(int(open(pidfile).read().strip()), 15)
        except (ProcessLookupError, ValueError, PermissionError):
            pass
        os.remove(pidfile)
    time.sleep(0.8)


def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"


LSCPU = ("lscpu | grep -vE 'Flags|Vulnerab|BogoMIPS|Byte Order|"
         "Address sizes|op-mode|NUMA node0'")
COND = ("for f in scaling_driver scaling_governor cpuinfo_min_freq cpuinfo_max_freq; "
        "do printf '%-18s %s\\n' $f \"$(cat /sys/devices/system/cpu/cpu0/cpufreq/$f)\"; "
        "done; printf '%-18s %s\\n' loadavg \"$(cut -d' ' -f1-3 /proc/loadavg)\"; "
        "printf '%-18s %s\\n' kernel \"$(uname -r)\"; "
        "printf '%-18s %s\\n' gcc \"$(gcc --version | head -1)\"")


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'intel'
    host = {'intel': 'intel-stand', 'amd': 'amd-stand'}.get(label, label)
    log = 'results/%s.log' % label

    shots = [
        ('screen_lscpu_%s.png' % label, LSCPU, 'Конфигурация вычислительной системы'),
        ('screen_conditions_%s.png' % label, COND, 'Условия проведения эксперимента'),
        ('screen_help.png', './fibbench --help', 'Параметры запуска программы'),
    ]
    if os.path.exists(os.path.join(ROOT, log)):
        shots += [
            ('screen_run_%s.png' % label,
             "sed -n '/^=====/,/^МЕТОД 2/p' %s | head -n -2" % log,
             'Результаты измерений, часть 1'),
            ('screen_run_%s_2.png' % label,
             "sed -n '/^МЕТОД 3/,$p' %s" % log,
             'Результаты измерений, часть 2'),
        ]
    else:
        print('  протокол %s отсутствует, снимки результатов пропущены' % log)

    print('Съёмка копий экрана: на экране будут появляться окна терминала.')
    with TempProfile():
        for name, cmd, title in shots:
            shoot(name, cmd, title, host)
    print('Готово.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
