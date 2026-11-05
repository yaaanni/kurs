#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_chapters.py - формирование разделов 3, 4 и 5 пояснительной записки.

Использование:
    python3 scripts/build_chapters.py [исходный.docx] [результат.docx]

Разделы 3 и 4 содержат постоянный текст, раздел 5 формируется по фактическим
протоколам измерений из каталога results и изображениям из каталога figures.
Повторный запуск после получения новых данных полностью пересоздаёт разделы.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import docx
from docxkit import Builder, clear_section
import chapter3
import chapter4
import chapter5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Эталон содержит разделы 1 и 2 и пустые заголовки разделов 3-5.
DEFAULT_SRC = os.path.join(ROOT, 'base_zapiska.docx')
DEFAULT_DST = os.path.join(os.path.dirname(ROOT),
                           'Курсовой_проект_АВС_ПОПОВА_453501_процентовка2.docx')

SECTIONS = [
    ('3 ТЕОРЕТИЧЕСКОЕ ОБОСНОВАНИЕ', '4 ПРОЕКТИРОВАНИЕ', chapter3),
    ('4 ПРОЕКТИРОВАНИЕ',           '5 СРАВНЕНИЕ',      chapter4),
    ('5 СРАВНЕНИЕ',                'ЗАКЛЮЧЕНИЕ',       chapter5),
]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    dst = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DST
    if not os.path.exists(src):
        print('Не найден файл', src)
        return 1
    doc = docx.Document(src)

    for head, nxt, module in SECTIONS:
        anchor = clear_section(doc, head, nxt)
        b = Builder(doc, anchor)
        if module is chapter3:
            module.build(b)
        else:
            module.build(b, ROOT)
        print('  сформирован раздел', head.split()[0])

    doc.save(dst)
    print('Сохранено:', dst)
    return 0


if __name__ == '__main__':
    sys.exit(main())
