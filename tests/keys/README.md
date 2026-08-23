# Answer keys

Hand-marked ground truth for the measurement harness. Each key states what a
careful human reader considers the correct label for every line of a text.

**These are read from the source, not copied from the tool's output.** A key
derived from what CorpusPrep already produces would only measure consistency
with itself, which is worthless. If you extend a key, read the text.

## Format

One labelled range per line. Blank lines and `#` comments are ignored.

```
START-END   LABEL          optional note
1-19        pg_header      Gutenberg header block
82          body           ACT I
```

- Line numbers are **1-based and inclusive**, matching what
  `python -m corpusprep inspect` reports.
- A single line may be written as `82` rather than `82-82`.
- Ranges may be listed in any order and need not be contiguous.
- Any line not covered by a range is treated as **unlabelled** and excluded
  from scoring. Use this deliberately for passages you are unsure about, so
  that genuine uncertainty does not distort the figures.

Valid labels are the six region labels:

```
pg_header  pg_licence  front_matter  body  back_matter  unknown
```

## Line numbers for container formats

For `.epub`, `.docx` and `.html`, line numbers refer to the **extracted text
stream**, not the original markup. To see it:

```bash
python -m corpusprep inspect tests/fixtures/pg921-images-3.epub --all
```

Extraction is deterministic, so the numbering is stable. It would change if
the extractor changed, which is one reason the extractor has its own tests.

## Running the measurement

```bash
python tools/measure.py                       # every key
python tools/measure.py romeo_juliet          # one text
python tools/measure.py --errors              # list every misclassified line
```
