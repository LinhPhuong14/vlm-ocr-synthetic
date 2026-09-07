Not yet wired to any schema this repository validates against -- see the note
at the top of `agent/prompts/layout.md`. Kept here, in English, as the source
a future prompt composes from once a layout's sections can name a region, so
translating it does not have to happen twice under time pressure.

Vietnamese original, with the measurements this was built from: `samples/
label-axes/*.html` + the guideline docstring above `agent/layout_schema.py`
(or ask the person who wired this in where it now lives).

---

# Three-axis region labelling

Every run of text on a page belongs to exactly one **region** (what it IS in
the document), carries a **role** (what it DOES inside that region), and is
printed with an **ink** (how it got onto the paper). Keep the three separate:

> Ask what a piece of text DOES in the document. Not what it looks like.
> Not where it sits on the page.

Every mislabel seen so far was one of these three, mistaking:
- **position** for role (a letterhead at the top margin is not a repeating
  Page-Header just because it sits at the top -- it is Text, page-specific);
- **material** for role (a stamp with legible words is Text + ink=stamp, not
  Image -- calling it Image tells a reader not to read words it needs to
  read);
- **presentation** for role (a reversed-colour banner is still a
  Section-Header -- what it contains is a heading, not a new region called
  "Mark"). If you find yourself wanting to put "reversed", "handwritten",
  "stamped", or "monospace" into the region axis, stop: those belong to ink.

## Region (18 page-level classes, plus one whole-page property)

Try the narrower class before the general one.

**Page-Header** / **Page-Footer** -- a line that repeats at the SAME margin
on every page (page number, a standard's code). NOT a letterhead, an issuer
block, or a document's own title -- those appear once. Each distinct item is
its own region; a header split into two unrelated fields is two regions, not
one box spanning the gap between them.

**Title** -- the document's own name. Appears once, largest type, usually
centred.

**Section-Header** -- the name of one part of the document. Its own line,
often numbered, often bold; what follows it can be pulled out as one block.
NOT a lead-in sentence ending in a colon (see the Section-Header/Text test
below).

**Text** -- running prose, and the default for anything that fits no
narrower class -- but not a wastebasket: try every narrower class first.

**List-Group** -- a bulleted or numbered list. Its box includes the bullet or
number glyph. A list's own heading sits outside it.

**Table** -- a grid with rows, columns, and column headers. Box follows the
ruled lines.

**Table-Of-Contents** -- entries, leader dots, page numbers.

**Form** -- a region meant to be FILLED IN: a labelled cell still waiting for
a value. Test: *on a blank, never-used copy of this page, is this spot
empty?* A colon does not make a line a form -- that distinction is the role
axis's job (key vs value), not this one's.

**Code-Block** -- source code or a command, monospaced, usually with a
background or border. Box takes the whole background panel.

**Formula** -- a mathematical OR chemical expression set as a line: centred,
with sub/superscripts, sometimes numbered. (Chemical reactions and equations
share this one class on purpose -- see "why classes get merged" below.) NOT a
DRAWN chemical structure (a benzene ring, bonds) -- that is a Diagram.

**Caption** -- the caption of a table, figure, or diagram; above or below the
thing it captions.

**Footnote** -- pointed to by a MARK in the body (¹, *, †), at the foot of
the page under a rule.

**Bibliography** -- a reference list, pointed to by a CITATION CODE ([1],
(Smith 2019)) rather than a body-text mark. Hanging indent, italic titles.

**Image** -- raster content with NO legible text: a logo, a photo, a
barcode, a QR code. This INCLUDES a logo or barcode rendered as an inline SVG
or with a barcode font rather than a bitmap -- what makes it Image is that a
reader is not meant to read it character by character, not what technology
drew it. NOT a stamp with words a reader needs to read (that is Text +
ink=stamp).

**Figure** -- an image PLUS its caption, counted as one block. A Caption
nested inside it is declared, valid nesting. Do not also tag the image inside
a Figure as Image -- two different classes covering the same pixels is two
conflicting targets for the model reading this later.

**Diagram** -- structure drawn to be read AS structure: a flowchart, a block
diagram, a chemical structure with bonds. Nodes carry text, relationships,
and an order that means something.

**Complex-Block** -- only when the ENCLOSING FRAME itself carries meaning
("this is one unit") and splitting it loses exactly that meaning (e.g. a
boxed classified ad: headline, body, phone number, small logo, one frame --
split apart, it is no longer legibly "one ad"). NOT for a table with a
caption above and a footnote below -- that splits cleanly into Caption +
Table + Footnote every time. Reaching for this class because nothing else
fits is itself the sign of a wrong choice: it becomes a second wastebasket in
the seat Text already holds.

**Blank-Page** -- a PAGE property, not a box: a blank page has no boxes to
label at all. Record it on the page, never inside its list of regions.

## Role (13 values) -- what a run DOES inside its region

`key` / `value` -- a field's label / the value that fills it (Form, Text).
`heading` / `subheading` -- a region's own title / subtitle (Title,
Section-Header).
`colhdr` / `rowhdr` -- a column title / a row title or row number (Table).
`cell` -- a data cell (Table). `total` -- a summary cell (Form, Table).
`body` -- running prose (Text, Formula, Code-Block).
`item` -- one list entry (List-Group, Bibliography, Table-Of-Contents).
`caption` (Caption). `note` -- a small aside (Footnote, Text).
`mark` -- a stamp, logo, barcode glyph (Image, or Text for a legible stamp).

## Ink (6 values) -- how the mark got onto the paper, measured at draw time

`print` -- ordinary print. `hand` -- handwriting. `stamp` -- a stamp impression.
`dotmatrix` -- dot-matrix printer. `thermal` -- thermal paper, faint ink.
`reversed` -- light text on a dark fill.

This axis carries everything about MATERIAL and PRESENTATION. If an
observation about how something looks makes you want to change the region,
the region choice was wrong, not the ink one.

## The two hard disambiguations seen most often

**Form vs Text**: would this spot be empty on an unused blank copy of the
page? Yes -> Form. A printed, already-filled value in a letterhead (a tax ID
printed at the top) is Text, not Form, even though it looks like a
labelled field -- it was never going to be blank.

**Section-Header vs Text**: remove the line. Does the document lose a named
PART, or only a sentence? A lead-in ending in a colon, in sentence case,
naming no section, is Text.

## Why a class gets merged rather than split

Test before adding or splitting any region class: **does anything downstream
treat the two differently?** If not, merge them. Equation and chemical-
reaction notation were once two classes; nothing downstream extracted,
displayed, or processed them differently, so they are one class, Formula,
now. Splitting a class that has no downstream difference only gives
labellers a class boundary they cannot apply consistently.

## What a region's box covers

The ink inside it PLUS whatever shape the region draws for itself -- not the
convex hull of the text (a table's hull sits inside its own ruled lines) and
not the box of whatever container tag happens to hold it (a full-width
heading `<div>` around centred text is not the heading's box). A decorative
frame added only so a person can see the block at a glance must not appear
in a page that is meant to look real -- if the frame is not on the real
paper, it is not in the box either.

## Never invent content to fill a class with zero examples

A region class with no example yet is a gap to DECLARE, not a reason to
fabricate a paragraph shaped like one. Content invented to satisfy a label is
exactly what corrupts a training set: a future reader trusts that a Code-
Block region is real code, not a paragraph translated from a chemistry
standard because "something had to be Code-Block."
