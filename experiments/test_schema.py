from schemas.document import (
    Document,
    DocumentBlock,
    BBox,
    TableBlock,
    TableRow,
    TableCell,
)
table = TableBlock(
        rows=[
            TableRow(
                cells=[
                    TableCell(
                        content="Item",
                        is_header=True,
                    ),
                    TableCell(
                        content="Qty",
                        is_header=True,
                    ),
                    TableCell(
                        content="Price",
                        is_header=True,
                    ),
                ]
            ),
            TableRow(
                cells=[
                    TableCell(content="Apple"),
                    TableCell(content="2"),
                    TableCell(content="$10"),
                ]
            ),
            TableRow(
                cells=[
                    TableCell(content="Banana"),
                    TableCell(content="3"),
                    TableCell(content="$15"),
                ]
            ),
        ],
        bbox=BBox(
            x1=100,
            y1=300,
            x2=900,
            y2=700,
        ),
    )
document = Document(
    page_width=1000,
    page_height=1400,
    blocks=[
        DocumentBlock(
            block_type="Page-Header",
            content="INVOICE",
            bbox=BBox(
                x1=100,
                y1=50,
                x2=900,
                y2=120,
            ),
        ),

        DocumentBlock(
            block_type="Text",
            content="Invoice No: INV-001",
            bbox=BBox(
                x1=100,
                y1=180,
                x2=500,
                y2=230,
            ),
        ),

        DocumentBlock(
            block_type="Table",
            table=table,
        ),

        DocumentBlock(
            block_type="Footnote",
            content="* Prices include tax.",
            bbox=BBox(
                x1=100,
                y1=1200,
                x2=900,
                y2=1250,
            ),
        ),
    ],
)

print(document)
