# -*- coding: utf-8 -*-
"""
docxkit.py - вспомогательные средства формирования пояснительной записки
по требованиям СТП 01-2024 (разделы 2.2, 2.5, 2.6).
"""
import copy
import re

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

INDENT = 709          # абзацный отступ 1,25 см в твипах
TEXT_W_DXA = 9355     # ширина текста 165 мм в твипах

_TOK = re.compile(r'[-/]?[A-Za-z0-9_]+(?:[-._+~/*][A-Za-z0-9_]+)*')
_HAS_LAT = re.compile(r'[A-Za-z]')


def latin_spans(s):
    """Позиции подстрок с латиницей (они набираются курсивом)."""
    return [(m.start(), m.end()) for m in _TOK.finditer(s) if _HAS_LAT.search(m.group(0))]


def add_text(par, s, bold=False):
    """Добавление текста с выделением латиницы курсивом."""
    pos = 0
    for a, b in latin_spans(s):
        if a > pos:
            r = par.add_run(s[pos:a]); r.bold = bold
        r = par.add_run(s[a:b]); r.italic = True; r.bold = bold
        pos = b
    if pos < len(s):
        r = par.add_run(s[pos:]); r.bold = bold


def _set_pPr(par, first_line=INDENT, left=0, align='both', keep_next=False,
             keep_lines=False):
    pPr = par._p.get_or_add_pPr()
    for tag in ('w:ind', 'w:jc', 'w:keepNext', 'w:keepLines'):
        el = pPr.find(qn(tag))
        if el is not None:
            pPr.remove(el)
    ind = OxmlElement('w:ind')
    ind.set(qn('w:firstLine'), str(first_line))
    ind.set(qn('w:left'), str(left))
    pPr.append(ind)
    jc = OxmlElement('w:jc'); jc.set(qn('w:val'), align); pPr.append(jc)
    if keep_next:
        pPr.append(OxmlElement('w:keepNext'))
    if keep_lines:
        pPr.append(OxmlElement('w:keepLines'))


class Builder:
    """Последовательная вставка элементов записки после заданного абзаца."""

    def __init__(self, doc, anchor_p):
        self.doc = doc
        self.cursor = anchor_p._p          # элемент, после которого идёт вставка

    # ---------- низкоуровневые операции ----------
    def _attach(self, el):
        self.cursor.addnext(el)
        self.cursor = el
        return el

    def _new_par(self, style=None):
        p = OxmlElement('w:p')
        self._attach(p)
        par = docx.text.paragraph.Paragraph(p, self.doc)
        if style:
            par.style = self.doc.styles[style]
        return par

    # ---------- элементы текста ----------
    def blank(self, style='No Spacing'):
        par = self._new_par(style)
        _set_pPr(par, first_line=0, align='left')
        return par

    def heading2(self, text):
        """Заголовок подраздела: строчными с первой прописной, полужирный."""
        par = self._new_par('No Spacing')
        _set_pPr(par, first_line=INDENT, align='left', keep_next=True)
        add_text(par, text)
        return par

    def para(self, text):
        par = self._new_par()
        _set_pPr(par, first_line=INDENT, align='both')
        add_text(par, text)
        return par

    def listing(self, items, lead=None):
        """Простое перечисление: тире, точка с запятой, последний - точка."""
        if lead:
            self.para(lead)
        for i, it in enumerate(items):
            par = self._new_par()
            _set_pPr(par, first_line=INDENT, align='both')
            add_text(par, '– ' + it + ('.' if i == len(items) - 1 else ';'))

    def nlisting(self, items, lead=None):
        """Сложное перечисление: арабские цифры, с прописной буквы, точка."""
        if lead:
            self.para(lead)
        for i, it in enumerate(items, 1):
            par = self._new_par()
            _set_pPr(par, first_line=INDENT, align='both')
            add_text(par, '%d %s' % (i, it))

    # ---------- таблица ----------
    def table(self, caption, headers, rows, widths_mm, aligns=None):
        """Таблица по СТП 2.6: заголовок через тире на уровне левой границы,
        пробельная строка до заголовка и после таблицы, между заголовком
        и таблицей пробельной строки нет."""
        self.blank('Normal')
        cap = self._new_par()
        _set_pPr(cap, first_line=0, align='left', keep_next=True)
        add_text(cap, caption)

        ncol = len(headers)
        tbl = self.doc.add_table(rows=0, cols=ncol)
        self._borders(tbl)
        tbl.autofit = False
        tbl.alignment = WD_TABLE_ALIGNMENT.LEFT

        dxa = [int(round(w * TEXT_W_DXA / 165.0)) for w in widths_mm]
        dxa[-1] += TEXT_W_DXA - sum(dxa)
        tblPr = tbl._tbl.tblPr
        tw = tblPr.find(qn('w:tblW'))
        if tw is None:
            tw = OxmlElement('w:tblW'); tblPr.append(tw)
        tw.set(qn('w:type'), 'dxa'); tw.set(qn('w:w'), str(TEXT_W_DXA))
        lay = OxmlElement('w:tblLayout'); lay.set(qn('w:type'), 'fixed'); tblPr.append(lay)
        for gc, w in zip(tbl._tbl.find(qn('w:tblGrid')).findall(qn('w:gridCol')), dxa):
            gc.set(qn('w:w'), str(w))

        if aligns is None:
            aligns = ['left'] + ['center'] * (ncol - 1)

        for ri, row in enumerate([headers] + rows):
            r = tbl.add_row()
            trPr = r._tr.get_or_add_trPr()
            trPr.append(OxmlElement('w:cantSplit'))
            if ri == 0:
                trPr.append(OxmlElement('w:tblHeader'))
            for ci, val in enumerate(row):
                cell = r.cells[ci]
                cell.width = Mm(widths_mm[ci])
                par = cell.paragraphs[0]
                pPr = par._p.get_or_add_pPr()
                ind = OxmlElement('w:ind')
                ind.set(qn('w:firstLine'), '0'); ind.set(qn('w:left'), '28')
                pPr.append(ind)
                sp = OxmlElement('w:spacing')
                sp.set(qn('w:before'), '20'); sp.set(qn('w:after'), '20')
                sp.set(qn('w:line'), '240'); sp.set(qn('w:lineRule'), 'auto')
                pPr.append(sp)
                a = 'center' if ri == 0 else aligns[ci]
                par.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT,
                                 'center': WD_ALIGN_PARAGRAPH.CENTER,
                                 'right': WD_ALIGN_PARAGRAPH.RIGHT}[a]
                add_text(par, str(val))
                for run in par.runs:
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(12)
                v = OxmlElement('w:vAlign'); v.set(qn('w:val'), 'center')
                cell._tc.get_or_add_tcPr().append(v)

        self._attach(tbl._tbl)
        self.blank('Normal')
        return tbl

    @staticmethod
    def _borders(tbl):
        borders = OxmlElement('w:tblBorders')
        for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            e = OxmlElement('w:' + edge)
            e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), '4')
            e.set(qn('w:space'), '0'); e.set(qn('w:color'), '000000')
            borders.append(e)
        tbl._tbl.tblPr.append(borders)

    # ---------- рисунок ----------
    def figure(self, path, caption, width_mm=150):
        """Рисунок по СТП 2.5: по центру, отделён от текста и от подрисуночной
        подписи одной пробельной строкой, подпись по центру без точки."""
        self.blank('Normal')
        par = self._new_par()
        _set_pPr(par, first_line=0, align='center', keep_next=True)
        run = par.add_run()
        run.add_picture(path, width=Mm(width_mm))
        self.blank('Normal')
        cap = self._new_par()
        _set_pPr(cap, first_line=0, align='center')
        add_text(cap, caption)
        self.blank('Normal')


def clear_section(doc, head_text, next_head_text):
    """Удаление содержимого раздела между его заголовком и разрывом страницы
    перед следующим разделом. Удаляются элементы всех видов - и абзацы,
    и таблицы, - иначе при повторном формировании таблицы накапливаются.
    Возвращает абзац-заголовок раздела."""
    paras = doc.paragraphs
    head_p = next(p for p in paras if p.text.strip().startswith(head_text))
    next_p = next(p for p in paras if p.text.strip().startswith(next_head_text))

    body = head_p._p.getparent()
    children = list(body)
    i_head = children.index(head_p._p)
    i_next = children.index(next_p._p)

    # абзац с разрывом страницы перед следующим разделом сохраняем
    i_break = i_next
    while i_break > i_head + 1:
        el = children[i_break - 1]
        if el.tag == qn('w:p') and el.findall('.//' + qn('w:br')):
            break
        i_break -= 1

    for el in children[i_head + 1:i_break - 1 if i_break > i_head + 1 else i_next]:
        body.remove(el)
    return head_p
