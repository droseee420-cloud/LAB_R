import re
import struct
import warnings
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import olefile
from defusedxml import ElementTree
from PIL import Image
from pypdf import PdfReader

from .validation import BriefError

MIMES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf",
    ".doc": "application/msword", ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
Image.MAX_IMAGE_PIXELS = 25_000_000


def filename_extension(name: str) -> str:
    if not name or len(name) > 240 or len(name.encode("utf-8")) > 960 or name != name.strip() or any(ord(c) < 32 for c in name) or re.search(r'[\\/:<>"|?*\x7f]', name) or name.startswith("."):
        raise BriefError("Invalid attachment filename.")
    ext = Path(name).suffix.lower()
    if ext not in MIMES:
        raise BriefError("Accepted attachments: JPG, PNG, WebP, GIF, PDF, DOC/DOCX and XLS/XLSX.")
    return ext


def check_ooxml(path: Path, ext: str):
    part, root, content_type = (
        ("word/document.xml", "document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
        if ext == ".docx" else
        ("xl/workbook.xml", "workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    )
    namespace = "http://schemas.openxmlformats.org/" + ("wordprocessingml/2006/main" if ext == ".docx" else "spreadsheetml/2006/main")
    with ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 2048 or sum(m.file_size for m in members) > 80 * 1024 * 1024:
            raise ValueError("Container too large")
        names = [m.filename for m in members]
        if len({n.lower() for n in names}) != len(names):
            raise ValueError("Duplicate parts")
        for member in members:
            name = member.filename
            if "\\" in name or name.startswith("/") or ".." in PurePosixPath(name).parts or ":" in name or "\x00" in name:
                raise ValueError("Invalid part path")
            if any(x in name.lower() for x in ("vba", "macro", "activex", "embeddings/")) or member.flag_bits & 1:
                raise ValueError("Active or encrypted content")
            if member.file_size > 32 * 1024 * 1024 or member.file_size > max(member.compress_size, 1) * 200:
                raise ValueError("Container expansion limit")
            # Stream every entry to verify CRC and declared lengths, without extracting it.
            with archive.open(member) as stream:
                count = 0
                while chunk := stream.read(64 * 1024):
                    count += len(chunk)
                    if count > 32 * 1024 * 1024:
                        raise ValueError("Container expansion limit")
        def xml(name: str):
            if archive.getinfo(name).file_size > 16 * 1024 * 1024:
                raise ValueError("XML part too large")
            return ElementTree.fromstring(archive.read(name))
        types = xml("[Content_Types].xml")
        if any("macro" in str(e.attrib).lower() or "vba" in str(e.attrib).lower() for e in types):
            raise ValueError("Macro content type")
        if not any(e.get("PartName") == "/" + part and e.get("ContentType") == content_type for e in types):
            raise ValueError("Wrong Office content type")
        if xml(part).tag != f"{{{namespace}}}{root}":
            raise ValueError("Wrong document root")
        relationships = xml("_rels/.rels")
        if not any(e.get("Type", "").endswith("/officeDocument") and e.get("Target", "").lstrip("/") == part and e.get("TargetMode") != "External" for e in relationships):
            raise ValueError("Missing main relationship")


def check_ole(path: Path, ext: str):
    with olefile.OleFileIO(path, raise_defects=olefile.DEFECT_INCORRECT) as ole:
        names = ["/".join(p).lower() for p in ole.listdir()]
        if len(names) > 1024 or any(any(s in name for s in ("vba", "macros", "_vba_project", "encryptedpackage")) for name in names):
            raise ValueError("Unsupported OLE content")
        if ext == ".doc":
            with ole.openstream("WordDocument") as stream:
                fib = stream.read(32)
            if len(fib) != 32 or fib[:2] != b"\xec\xa5":
                raise ValueError("Missing Word FIB")
            version, flags = struct.unpack_from("<H", fib, 2)[0], struct.unpack_from("<H", fib, 10)[0]
            if version < 0xC1 or flags & 0x8100 or not ole.exists("1Table" if flags & 0x0200 else "0Table"):
                raise ValueError("Unsupported Word document")
        else:
            stream_name = "Workbook" if ole.exists("Workbook") else "Book"
            with ole.openstream(stream_name) as stream:
                data = stream.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024 or len(data) < 12 or data[:2] != b"\x09\x08" or data[4:8] != b"\x00\x06\x05\x00":
                raise ValueError("Missing Excel workbook BOF")
            pos, found_eof = 0, False
            while pos + 4 <= len(data):
                record, size = struct.unpack_from("<HH", data, pos)
                if size > 8224 or pos + 4 + size > len(data) or record in {0x002F, 0x00D3}:
                    raise ValueError("Invalid, encrypted or macro workbook")
                if record == 0x0085 and size >= 6 and data[pos + 9] in {1, 6}:
                    raise ValueError("Macro sheet")
                found_eof |= record == 0x000A
                pos += 4 + size
            if not found_eof:
                raise ValueError("Incomplete workbook")


def validate_file(path: Path, filename: str) -> str:
    ext = filename_extension(filename)
    try:
        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as img:
                    if img.format != {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".gif": "GIF", ".webp": "WEBP"}[ext]:
                        raise ValueError("Image format mismatch")
                    img.verify()
        elif ext == ".pdf":
            with path.open("rb") as stream:
                if not stream.read(8).startswith(b"%PDF-"):
                    raise ValueError("Missing PDF header")
                stream.seek(0)
                reader = PdfReader(stream, strict=True)
                if reader.is_encrypted or reader.trailer["/Root"]["/Type"] != "/Catalog" or "/Pages" not in reader.trailer["/Root"]:
                    raise ValueError("Unsupported PDF")
        elif ext in {".docx", ".xlsx"}:
            check_ooxml(path, ext)
        else:
            check_ole(path, ext)
    except Exception:
        raise BriefError("An attachment is damaged, unsupported or does not match its extension.") from None
    return MIMES[ext]
