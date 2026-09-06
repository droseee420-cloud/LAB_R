# Synthetic fixtures

`image.png`, `document.pdf`, `document.docx`, `sheet.xlsx` were generated for these tests (3×2 image, blank PDF page and minimal OOXML containers). No submitted user data is used.

`document.doc` and `sheet.xls` are the small synthetic `simple.doc` / `Simple.xls` fixtures from Apache POI:

- https://github.com/apache/poi/blob/trunk/test-data/document/simple.doc
- https://github.com/apache/poi/blob/trunk/test-data/spreadsheet/Simple.xls

See the included Apache LICENSE and NOTICE. These files are used only by tests, excluded from release archives and Docker contexts.
