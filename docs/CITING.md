# Citing CorpusPrep

## Cite a version, not the repository

The tool's behaviour changes between releases. Frankenstein returned 24
divisions in v0.5.0 and 28 in v0.6.0, because v0.5.0 was silently dropping
5,500 words of the novel. An analysis run against one is not reproducible
against the other.

**So the version is not a formality.** Record the one you used, and say so in
your methods section.

    corpusprep --version

## Current release

> Adesokan, T. (2026). *CorpusPrep: corpus preparation for linguists*
> (version 0.6.0) [Computer software].
> https://github.com/adesokantosin2000-beep/corpusprep

BibTeX:

```bibtex
@software{adesokan_corpusprep_2026,
  author  = {Adesokan, Tosin},
  title   = {{CorpusPrep: corpus preparation for linguists}},
  version = {0.6.0},
  year    = {2026},
  url     = {https://github.com/adesokantosin2000-beep/corpusprep}
}
```

Machine-readable metadata is in [`CITATION.cff`](../CITATION.cff). GitHub reads
it for the "Cite this repository" button, and Zenodo reads
[`.zenodo.json`](../.zenodo.json) when archiving a release.

---

## Getting a DOI

A GitHub URL is not an archival citation. The repository can be renamed,
made private or deleted, and a reviewer three years from now has no guarantee
the link resolves. A DOI is permanent and points at a frozen copy of the code.

This is a five-minute, one-time setup, and it must be done **before** the
release is created — Zenodo only sees releases published after the switch is
turned on.

1. Sign in at [zenodo.org](https://zenodo.org) with the GitHub account.
2. Go to **GitHub** in the Zenodo account menu.
3. Find `corpusprep` in the repository list and turn the toggle **on**.
4. On GitHub, go to **Releases → Draft a new release**.
5. Choose the existing tag `v0.6.0`, title it `v0.6.0 — Integration`, paste
   the release notes below, and **Publish**.
6. Zenodo archives the release within a minute or two and mints two DOIs:
   - a **version DOI** for `v0.6.0` specifically
   - a **concept DOI** that always resolves to the newest version

**Cite the version DOI in a thesis.** The concept DOI moves, which is useful
for a general reference and wrong for a methods section that has to stay true.

7. Add both to `CITATION.cff` and re-run the tests, which check that the file
   agrees with the package version:

```yaml
doi: 10.5281/zenodo.XXXXXXX      # the version DOI for 0.6.0
identifiers:
  - type: doi
    value: 10.5281/zenodo.YYYYYYY
    description: Concept DOI, always the latest version
```

8. Add the badge to the top of `README.md`:

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)
```

### If the proposal is due before this is done

Cite the repository URL with the version and the commit hash. It is weaker
than a DOI and it is honest, which matters more:

> Adesokan, T. (2026). *CorpusPrep* (version 0.6.0, commit `44ce19d`).
> https://github.com/adesokantosin2000-beep/corpusprep

A DOI can be added to the final submission; a citation that overstates what
exists cannot be quietly repaired later.

---

## What can be claimed for it

Claim only what has been measured, and the measurements are in the repository
rather than in this file, so a reviewer can check them.

**Measured.** Region labelling is 99.99% accurate over 7,654 hand-marked
content lines across five texts (`tools/measure.py`). Paragraph reflow recovers
99.5% of *Jane Eyre*'s paragraphs from a hard-wrapped copy, with the remainder
reported rather than guessed. Structural segmentation was checked against
eleven real books in `tools/integration.py`; six have an unambiguous division
count and five of those are exact.

**Not measured.** Precision and recall for the individual furniture rules on
scanned text, which rests on two scans and is too small a sample to quote.
PDF input, which is not implemented.

**Known limits**, stated in full in
[`design/integration-failures.md`](../design/integration-failures.md) and
[`design/reflow-failures.md`](../design/reflow-failures.md). Both were written
before the fixes, and the unfixed items are still listed. That is deliberate:
software whose failure log is missing is not more reliable than software whose
failure log is long.
