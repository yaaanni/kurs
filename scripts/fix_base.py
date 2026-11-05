# -*- coding: utf-8 -*-
import copy, re, docx
from docx.shared import Pt, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = 'k.docx'
DST = 'out.docx'
d = docx.Document(SRC)
P = d.paragraphs

# ---------------------------------------------------------------- helpers
def body_delete(p):
    p._p.getparent().remove(p._p)

def new_par_after(ref_p, text, style=None, first_line=None, align=None, keep_next=False):
    """Clone the formatting of a plain body paragraph and insert after ref_p."""
    newp = OxmlElement('w:p')
    ref_p._p.addnext(newp)
    par = docx.text.paragraph.Paragraph(newp, ref_p._parent)
    if style:
        par.style = d.styles[style]
    pPr = newp.get_or_add_pPr()
    if first_line is not None:
        ind = OxmlElement('w:ind'); ind.set(qn('w:firstLine'), str(first_line)); ind.set(qn('w:left'), '0')
        pPr.append(ind)
    if align is not None:
        jc = OxmlElement('w:jc'); jc.set(qn('w:val'), align); pPr.append(jc)
    if keep_next:
        pPr.append(OxmlElement('w:keepNext'))
    if text:
        par.add_run(text)
    return par

# ---------------------------------------------------------------- 1. notes
# remove the teacher's remarks block on the СОДЕРЖАНИЕ page (paragraphs 41..45)
for i in range(45, 40, -1):
    body_delete(P[i])

# ---------------------------------------------------------------- 2. drop last intro paragraph
P = d.paragraphs
for i, p in enumerate(P):
    if p.text.startswith('Программа должна измерять время выполнения каждого метода'):
        body_delete(p); break

# ---------------------------------------------------------------- 3. текстовые правки
REPL = [
    ('Руководитель курсовой работы',   'Руководитель курсового проекта'),
    ('к курсовой работе',              'к курсовому проекту'),
    ('Курсовая работа представлена',   'Курсовой проект представлен'),
    ('Целью курсовой работы',          'Целью курсового проекта'),
    ('задачи курсовой работы',         'задачи курсового проекта'),
    ('настоящей курсовой работе',      'настоящем курсовом проекте'),
    ('данной курсовой работе',         'данном курсовом проекте'),
    ('в курсовой работе',              'в курсовом проекте'),
    ('выполнения курсовой работы',     'выполнения курсового проекта'),
    ('курсовой работы',                'курсового проекта'),
    ('курсовой работе',                'курсовом проекте'),
    ('курсовая работа',                'курсовой проект'),
    ('Курсовая работа',                'Курсовой проект'),
    # прочие правки
    ('на результаты сравнения производительности процессоров: единственным различием '
     'при компиляции разрабатываемой программы на системах с процессорами Intel и AMD '
     'является используемый флаг целевой микроархитектуры (-march), тогда как остальные '
     'параметры оптимизации остаются идентичными.',
     'на результаты сравнения производительности процессоров. Сборка программного средства '
     'выполняется однократно с ключами -O2 -march=x86-64 -mtune=generic, при которых '
     'компилятор формирует машинный код, не содержащий инструкций, специфичных для '
     'конкретной микроархитектуры, и не выполняет настройку планирования команд под одно '
     'из семейств процессоров. Полученный исполняемый файл запускается на обеих '
     'вычислительных системах без повторной компиляции, что гарантирует полную '
     'идентичность исполняемого машинного кода и сопоставимость результатов измерений.'),
    ('сложностью O(), создающим',      'сложностью O(2ⁿ), создающим'),
]

_TOK = re.compile(r'[-/]?[A-Za-z0-9_]+(?:[-._+~/*][A-Za-z0-9_]+)*')
_HAS_LAT = re.compile(r'[A-Za-z]')

class LAT:
    @staticmethod
    def finditer(s):
        return (m for m in _TOK.finditer(s) if _HAS_LAT.search(m.group(0)))

def rebuild(par, italicize, do_repl=True):
    """Apply text replacements; optionally re-split runs so Latin tokens are italic."""
    runs = par.runs
    if not runs:
        return
    text = ''.join(r.text for r in runs)
    new = text
    if do_repl:
        for a, b in REPL:
            new = new.replace(a, b)
    if new == text and not italicize:
        return
    rPr_tpl = runs[0]._r.find(qn('w:rPr'))
    # wipe existing runs (and stray proofErr markers)
    p_el = par._p
    for child in list(p_el):
        if child.tag in (qn('w:r'), qn('w:proofErr'), qn('w:bookmarkStart'), qn('w:bookmarkEnd')):
            if child.tag == qn('w:r') and child.find(qn('w:br')) is not None:
                continue            # keep page breaks
            p_el.remove(child)

    def emit(chunk, italic):
        if not chunk:
            return
        r = OxmlElement('w:r')
        if rPr_tpl is not None:
            r.append(copy.deepcopy(rPr_tpl))
        if italic:
            rPr = r.find(qn('w:rPr'))
            if rPr is None:
                rPr = OxmlElement('w:rPr'); r.insert(0, rPr)
            for tag in ('w:i', 'w:iCs'):
                if rPr.find(qn(tag)) is None:
                    rPr.append(OxmlElement(tag))
        t = OxmlElement('w:t'); t.set(qn('xml:space'), 'preserve'); t.text = chunk
        r.append(t)
        p_el.append(r)

    if not italicize:
        emit(new, False)
        return
    pos = 0
    for m in LAT.finditer(new):
        emit(new[pos:m.start()], False)
        emit(m.group(0), True)
        pos = m.end()
    emit(new[pos:], False)

P = d.paragraphs
# титульный лист (по строку «Минск 2026» включительно) не правим вообще:
# ни замен «работа -> проект», ни курсива латиницы
idx_titul = next(i for i, p in enumerate(P) if p.text.strip() == 'Минск 2026')
idx_vved = next(i for i, p in enumerate(P) if p.text.strip() == 'ВВЕДЕНИЕ')
for i, p in enumerate(P):
    rebuild(p, italicize=(i >= idx_vved), do_repl=(i > idx_titul))

# ---------------------------------------------------------------- 4. нумерация подразделов раздела 1
SUB1 = {
    'Структура и архитектура вычислительной системы':      '1.1 ',
    'История, версии и достоинства':                       '1.2 ',
    'Обоснование выбора вычислительной системы':           '1.3 ',
    'Анализ выбранной системы для написания программы':    '1.4 ',
}
for p in d.paragraphs:
    t = p.text.strip()
    if t in SUB1:
        pPr = p._p.get_or_add_pPr()
        for tag in ('w:numPr', 'w:ind'):
            el = pPr.find(qn(tag))
            if el is not None:
                pPr.remove(el)
        ind = OxmlElement('w:ind')
        ind.set(qn('w:left'), '0'); ind.set(qn('w:firstLine'), '709')
        pPr.append(ind)
        p.runs[0].text = SUB1[t] + p.runs[0].text

# ---------------------------------------------------------------- 5. единый отступ заголовков
for p in d.paragraphs:
    if p.style.name in ('Босс 1', 'No Spacing') and re.match(r'^\d+(\.\d+)?\s+\S', p.text.strip()):
        pPr = p._p.get_or_add_pPr()
        el = pPr.find(qn('w:ind'))
        if el is not None:
            pPr.remove(el)
        ind = OxmlElement('w:ind')
        ind.set(qn('w:left'), '0'); ind.set(qn('w:firstLine'), '709')
        pPr.append(ind)

# ---------------------------------------------------------------- 6. таблица 1.1
def set_borders(tbl):
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement('w:' + edge)
        e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), '4')
        e.set(qn('w:space'), '0'); e.set(qn('w:color'), '000000')
        borders.append(e)
    tblPr.append(borders)

ROWS = [
    ('Характеристика', 'Intel Core i7-8565U', 'AMD Ryzen 7 7840HS'),
    ('Микроархитектура', 'Whiskey Lake', 'Zen 4'),
    ('Год выпуска', '2018', '2023'),
    ('Технологический процесс, нм', '14', '4'),
    ('Число физических ядер', '4', '8'),
    ('Число логических потоков', '8', '16'),
    ('Базовая тактовая частота, ГГц', '1,8', '3,8'),
    ('Максимальная тактовая частота, ГГц', '4,6', '5,1'),
    ('Кэш-память первого уровня (L1), КиБ', '256', '512'),
    ('Кэш-память второго уровня (L2), МиБ', '1', '8'),
    ('Кэш-память третьего уровня (L3), МиБ', '8', '16'),
    ('Расчётная тепловая мощность, Вт', '15', 'От 35 до 54'),
    ('Расширения системы команд', 'SSE4.2, AVX2', 'SSE4.2, AVX2, AVX-512'),
    ('Тип оперативной памяти', 'DDR4-2400, LPDDR3-2133', 'DDR5-5600, LPDDR5x-7500'),
]

anchor = next(p for p in d.paragraphs if p.text.startswith('В свою очередь, процессор AMD Ryzen 7 7840HS базируется'))
ref = new_par_after(anchor,
    'Основные технические характеристики рассматриваемых процессоров, определяющие их '
    'вычислительные возможности, приведены в таблице 1.1.',
    first_line=709, align='both')
blank1 = new_par_after(ref, '', first_line=0)
cap = new_par_after(blank1, 'Таблица 1.1 – Основные характеристики сравниваемых процессоров',
                    first_line=0, align='left', keep_next=True)

tbl = d.add_table(rows=0, cols=3)
set_borders(tbl)
tbl.autofit = False
tblPr = tbl._tbl.tblPr
# ширина таблицы = ширине текста (165 мм = 9355 твипов)
COLS_DXA = (3969, 2693, 2693)
tw = tblPr.find(qn('w:tblW'))
if tw is None:
    tw = OxmlElement('w:tblW'); tblPr.append(tw)
tw.set(qn('w:type'), 'dxa'); tw.set(qn('w:w'), str(sum(COLS_DXA)))
for gc, w in zip(tbl._tbl.find(qn('w:tblGrid')).findall(qn('w:gridCol')), COLS_DXA):
    gc.set(qn('w:w'), str(w))
widths = (Mm(70), Mm(47.5), Mm(47.5))

for ri, row in enumerate(ROWS):
    r = tbl.add_row()
    trPr = r._tr.get_or_add_trPr()
    trPr.append(OxmlElement('w:cantSplit'))
    if ri == 0:
        trPr.append(OxmlElement('w:tblHeader'))
    for ci, val in enumerate(row):
        cell = r.cells[ci]
        cell.width = widths[ci]
        par = cell.paragraphs[0]
        pPr = par._p.get_or_add_pPr()
        ind = OxmlElement('w:ind'); ind.set(qn('w:firstLine'), '0'); ind.set(qn('w:left'), '0')
        pPr.append(ind)
        sp = OxmlElement('w:spacing')
        sp.set(qn('w:before'), '20'); sp.set(qn('w:after'), '20')
        sp.set(qn('w:line'), '240'); sp.set(qn('w:lineRule'), 'auto')
        pPr.append(sp)
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER if (ci > 0 or ri == 0) else WD_ALIGN_PARAGRAPH.LEFT
        pos = 0
        for m in LAT.finditer(val):
            if m.start() > pos:
                par.add_run(val[pos:m.start()])
            run = par.add_run(m.group(0)); run.italic = True
            pos = m.end()
        if pos < len(val):
            par.add_run(val[pos:])
        for run in par.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(14)
            if ri == 0:
                run.bold = False
        vAlign = OxmlElement('w:vAlign'); vAlign.set(qn('w:val'), 'center')
        cell._tc.get_or_add_tcPr().append(vAlign)

# заголовок и таблицу пробельной строкой не разделяют (СТП 2.6.3)
cap._p.addnext(tbl._tbl)
# пробельная строка после таблицы
blank2 = OxmlElement('w:p')
pr = OxmlElement('w:pPr')
ind = OxmlElement('w:ind'); ind.set(qn('w:firstLine'), '0'); pr.append(ind)
blank2.append(pr)
tbl._tbl.addnext(blank2)

# ---------------------------------------------------------------- 7. абзацы-подытоживания
SUMMARIES = [
    ('Разработанная программа переносится на систему AMD без изменения исходного кода',
     'Таким образом, в разделе рассмотрены структура и архитектура вычислительной системы, '
     'изучены история развития, версии и достоинства микроархитектур Whiskey Lake и Zen 4, '
     'обоснован выбор двух вычислительных систем архитектуры x86-64 и проанализирована система, '
     'используемая для написания программы. Установлено, что сравниваемые процессоры при полной '
     'совместимости по системе команд существенно различаются числом вычислительных ядер, '
     'организацией кэш-памяти и допустимым уровнем энергопотребления, что и позволяет использовать '
     'их в качестве объектов сравнительного исследования производительности.'),
    ('Во время проведения тестирования на обеих вычислительных системах режим энергопотребления',
     'Таким образом, в разделе рассмотрены структура и архитектура программной платформы, изучены '
     'история развития, версии и достоинства операционной системы Ubuntu, обоснован её выбор и '
     'проанализированы средства, используемые при написании программы. Установлено, что операционная '
     'система Ubuntu 24.04 LTS предоставляет полный набор механизмов, необходимых для корректного '
     'измерения времени выполнения программы и для создания одинакового программного окружения на '
     'обеих вычислительных системах, что обеспечивает сопоставимость результатов тестирования.'),
]
for anchor_start, text in SUMMARIES:
    a = next(p for p in d.paragraphs if p.text.startswith(anchor_start))
    new_par_after(a, text, first_line=709, align='both')

d.save(DST)
print('saved', DST)
