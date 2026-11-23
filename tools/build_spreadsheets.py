"""Write tests/data/sample.xlsx and tests/data/sample.ods: two spreadsheets the page's reader is checked on.

    uv run --with openpyxl --with odfpy python tools/build_spreadsheets.py

They are written by openpyxl and by odfpy, not by this project, so that `page/js/files.js` is checked on files
it did not shape. Both hold the same two sheets: a table with a line of names and units, an empty cell and a text
among numbers; and a second sheet that starts at C3, to check that the place of a cell is read and not counted.
The two libraries are needed only to write the files again: nothing else uses them.
"""
from __future__ import annotations

from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
FIRST = [["Energy (eV)", "Counts", "Note"], [1.5, 10, "start"], [2.25, None, None], [3.0, 1234567.891, "a\tb"], [-4.5e-7, 0, "end"]]
SECOND = [["T (K)", "R (Ω)"], [4.2, 0.001], [77, 12.5], [300, 99.75]]


def excel() -> None:
    from openpyxl import Workbook

    book = Workbook()
    one = book.active
    one.title = "Spectrum"
    for row in FIRST:
        one.append(row)
    two = book.create_sheet("Résistance")
    for i, row in enumerate(SECOND):
        for j, value in enumerate(row):
            two.cell(row=3 + i, column=3 + j, value=value)
    book.create_chartsheet("A chart")                     # a sheet without cells: it is not a table
    book.save(DATA / "sample.xlsx")


def libreoffice() -> None:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableCell, TableRow
    from odf.text import P

    doc = OpenDocumentSpreadsheet()

    def cell(value: object) -> TableCell:
        if value is None:
            return TableCell()
        if isinstance(value, int | float):
            c = TableCell(valuetype="float", value=repr(float(value)))
            c.addElement(P(text=str(value)))
            return c
        c = TableCell(valuetype="string")
        c.addElement(P(text=str(value)))
        return c

    one = Table(name="Spectrum")
    for row in FIRST:
        tr = TableRow()
        for value in row:
            tr.addElement(cell(value))
        tr.addElement(TableCell(numbercolumnsrepeated=1020))            # the empty rest of the row, as LibreOffice writes it
        one.addElement(tr)
    one.addElement(TableRow(numberrowsrepeated=1048570))                # and the empty rest of the sheet
    doc.spreadsheet.addElement(one)
    two = Table(name="Résistance")
    two.addElement(TableRow(numberrowsrepeated=2))
    for row in SECOND:
        tr = TableRow()
        tr.addElement(TableCell(numbercolumnsrepeated=2))
        for value in row:
            tr.addElement(cell(value))
        two.addElement(tr)
    doc.spreadsheet.addElement(two)
    doc.save(str(DATA / "sample.ods"))


if __name__ == "__main__":
    excel()
    libreoffice()
    print("wrote", DATA / "sample.xlsx", "and", DATA / "sample.ods")
