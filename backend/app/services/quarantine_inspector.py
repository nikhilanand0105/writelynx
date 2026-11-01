import math
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Dict, Any, Tuple
from fastapi import HTTPException, status
from lxml import etree
import docx

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_MAP = {"w": WORD_NAMESPACE}


class QuarantineInspector:
    @staticmethod
    def inspect_file(
        file_path: Path,
        max_file_size_bytes: int,
        max_ratio: float = 100.0,
        max_decompressed_bytes: int = 100 * 1024 * 1024,
    ) -> Dict[str, Any]:
        """Perform comprehensive cybersecurity audit of the quarantined file."""
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quarantine file not found.")

        file_size = file_path.stat().st_size
        if file_size > max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / (1024*1024):.2f} MB) exceeds your plan limit ({max_file_size_bytes / (1024*1024):.1f} MB)."
            )

        # Magic byte check: PK\x03\x04
        with open(file_path, "rb") as f:
            header = f.read(4)
            if header != b"PK\x03\x04":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid document container. File must be a valid Microsoft Word (.docx) archive."
                )

        if not zipfile.is_zipfile(file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corrupt or non-standard ZIP archive structure."
            )

        try:
            with zipfile.ZipFile(file_path, "r") as archive:
                entries = archive.infolist()
                names = [item.filename for item in entries]

                # Check membership limits
                if len(entries) > 5000 or len(set(names)) != len(names):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Archive contains excessive or duplicate entries (zip bomb signature)."
                    )

                # Required Word package files
                required_parts = {"[Content_Types].xml", "word/document.xml", "_rels/.rels"}
                if not required_parts.issubset(set(names)):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Corrupted DOCX package: missing standard Word OpenXML structures."
                    )

                total_uncompressed = 0
                for info in entries:
                    name = info.filename.replace("\\", "/")

                    # Prevent path traversal attacks
                    if name.startswith("/") or ".." in PurePosixPath(name).parts or ":" in name:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Archive contains illegal path traversal components."
                        )

                    # Reject symlinks or encrypted entries
                    if stat.S_ISLNK(info.external_attr >> 16) or (info.flag_bits & 1):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Encrypted or symlink archive members are prohibited."
                        )

                    # Macro and executable rejection
                    lower_name = name.lower()
                    if (
                        "vbaproject" in lower_name
                        or "vba" in lower_name
                        or lower_name.endswith((".exe", ".dll", ".bat", ".sh", ".cmd", ".vbs", ".bin"))
                    ):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Active macros, VBA code, and executable attachments are strictly prohibited."
                        )

                    total_uncompressed += info.file_size
                    if total_uncompressed > max_decompressed_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Decompressed document payload exceeds safe memory limits (potential zip bomb)."
                        )

                # Check compression ratio
                ratio = total_uncompressed / max(file_size, 1)
                if ratio > max_ratio:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Abnormal compression ratio ({ratio:.1f}:1). File rejected for potential decompression bomb."
                    )

                # XXE and entity expansion check
                for info in entries:
                    if not info.filename.endswith((".xml", ".rels")):
                        continue
                    data = archive.read(info)
                    upper_data = data.upper()
                    if b"<!DOCTYPE" in upper_data or b"<!ENTITY" in upper_data:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="DOCTYPE declarations and external XML entities are prohibited for security."
                        )

        except zipfile.BadZipFile:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed ZIP structure in document.")

        # Authoritative document metric extraction
        try:
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            tables_text.append(cell.text.strip())

            all_text_parts = paragraphs + tables_text
            full_text = " ".join(all_text_parts)
            character_count = len(full_text)
            word_count = len(full_text.split())

            # Explicit page breaks from document.xml
            explicit_breaks = 0
            with zipfile.ZipFile(file_path, "r") as archive:
                xml_content = archive.read("word/document.xml")
                root = etree.fromstring(xml_content)
                # Count explicit page breaks and rendered page breaks
                breaks = root.xpath("//w:br[@w:type='page'] | //w:lastRenderedPageBreak", namespaces=NS_MAP)
                explicit_breaks = len(breaks)

            # Estimate page count conservatively
            # Standard academic manuscript page ~ 400-500 words or ~ 2500-3000 chars
            derived_pages = max(
                1,
                explicit_breaks + 1,
                math.ceil(character_count / 3000),
                math.ceil(word_count / 450)
            )

            return {
                "character_count": character_count,
                "word_count": word_count,
                "page_count": derived_pages,
                "paragraph_count": len(doc.paragraphs),
                "table_count": len(doc.tables),
                "image_count": len(doc.inline_shapes),
                "explicit_breaks": explicit_breaks,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse Word document contents: {str(e)}"
            )
