"""Build small, valid PDF files in tests without extra dependencies.

A PDF is a list of numbered objects plus an `xref` table of their byte
offsets. This factory writes one Catalog, one Pages node, one font, and a
Page + Contents object pair per page, computing offsets as it goes.

Object numbering: 1=Catalog, 2=Pages, 3=Font, then (4,5), (6,7), ... for
each page's (Page, Contents) pair.
"""


def make_pdf(pages: list[str]) -> bytes:
    """Return the bytes of a PDF with one page per input string.

    Newlines in a page string become separate text lines on that page.
    An empty string produces a page with no text (like a scanned page).
    """
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}

    def add_object(number: int, body: bytes) -> None:
        offsets[number] = len(out)
        out.extend(f"{number} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")

    page_count = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(page_count))
    add_object(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    add_object(2, f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    add_object(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for i, page_text in enumerate(pages):
        parts = ["BT /F1 12 Tf 72 720 Td"]
        for j, line in enumerate(page_text.split("\n")):
            escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            if j > 0:
                parts.append("0 -14 Td")
            if escaped:
                parts.append(f"({escaped}) Tj")
        parts.append("ET")
        stream = " ".join(parts).encode()

        page_number, contents_number = 4 + 2 * i, 5 + 2 * i
        add_object(
            page_number,
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {contents_number} 0 R >>"
            ).encode(),
        )
        add_object(
            contents_number,
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        )

    total_objects = 3 + 2 * page_count
    xref_offset = len(out)
    out.extend(f"xref\n0 {total_objects + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for number in range(1, total_objects + 1):
        out.extend(f"{offsets[number]:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {total_objects + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(out)
