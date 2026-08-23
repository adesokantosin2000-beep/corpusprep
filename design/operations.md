# CorpusPrep: Hosting, Licensing and Release

Everything the build schedule does not cover. None of it is difficult; several
items are cheap now and expensive to change later, which is the reason to
settle them before September rather than after.

---

## 1. Hosting

Because the application is a single HTML file that runs entirely in the
browser, hosting is a solved problem and costs nothing.

| Option | Cost | Suits |
|---|---|---|
| **GitHub Pages** | Free | Recommended. Public repository, automatic deployment, no maintenance. |
| Netlify or Cloudflare Pages | Free tier | Equivalent. Choose only if already familiar. |
| University web space | Free | Institutional credibility, but you lose it when you move institution. |
| No hosting at all | Free | Distribute the file by email. Works, but nothing to cite. |

**GitHub Pages limits, as of 2026:** 1 GB published site, 100 GB bandwidth per
month, 10 builds per hour. The application is 83 KB. At that size the
bandwidth allowance is roughly 1.2 million page views per month, so the ceiling
is irrelevant.

Free hosting requires the repository to be public. If you intend to keep the
source private, budget for a paid plan or use university space.

### Recommended arrangement

```
github.com/<you>/corpusprep        source, issues, releases
<you>.github.io/corpusprep         the running application
corpusprep.org (optional)          a memorable address
```

The `docs/` folder of the repository can serve directly as the site, so the
deployed application is always the committed one. There is no build step to
break.

---

## 2. Domain name

Optional, and the only recurring cost in this entire document.

Roughly £10 to £15 per year for a `.org`, more for a `.io`. Worth it if the
tool appears in a paper, since `corpusprep.org` survives you changing
institution or GitHub username, and a URL in a published article that later
breaks is a genuine irritation.

**Register it before publishing anything.** Names are cheap now and
unobtainable once someone else has them.

---

## 3. Licence

This is the decision that is expensive to reverse, because once other people
have contributed you cannot change the licence without their agreement.

| Licence | Effect | Consider if |
|---|---|---|
| **MIT** | Anyone may use, modify and redistribute, including commercially. Attribution required. | You want the widest possible adoption. Standard for academic tools. |
| **GPL-3.0** | Same freedoms, but derivative works must also be open. | You object to a company building on this without contributing back. |
| **CC BY-NC** | Non-commercial only. | **Avoid.** Not a software licence, and "non-commercial" is legally murky enough that cautious institutions will refuse it. |
| No licence | Nobody may legally reuse it. | Never intentional, but common by omission. |

**Recommendation: MIT.** For research software, adoption and citation matter
more than controlling downstream use, and MIT removes every obstacle to a
colleague or an institution trying it.

One constraint already applies. The interface uses **PySide6-style reasoning
only in the specification**; the actual web application has no dependencies, so
nothing restricts your choice today. That changes if you add a wordlist in
week 5 of Phase 2 or a PDF library in week 13. **Check the licence of both
before you write code against them**, which is why that instruction appears in
the itinerary.

---

## 4. Citation and archiving

This is what converts a side project into something that counts
professionally, and it is free.

### Zenodo

Zenodo is operated by CERN and OpenAIRE and archives research output at no
charge. Connect it to the GitHub repository and every release automatically
receives a DOI.

Three consequences worth understanding:

1. **The code is preserved even if the repository is deleted.** Zenodo keeps
   its own copy, so the DOI does not rot.
2. **Each release gets its own DOI,** so a paper can cite the exact version
   used, which is precisely what reproducibility requires.
3. **A concept DOI** covers all versions, for when you want to cite the tool
   in general.

Set-up takes about fifteen minutes and needs doing once.

### CITATION.cff

A short file in the repository root telling people how to cite the tool.
GitHub reads it and displays a "Cite this repository" button automatically.

```yaml
cff-version: 1.2.0
title: "CorpusPrep: corpus preparation for linguists"
authors:
  - family-names: Adesokan
    given-names: Tosin
version: 1.0.0
doi: 10.5281/zenodo.XXXXXXX
date-released: 2026-12-04
url: "https://github.com/<you>/corpusprep"
```

### Software Heritage

Archives public repositories permanently and automatically. Nothing to do
beyond making the repository public, but worth knowing it exists.

---

## 5. Where to publish the tool paper

When you write it, three realistic venues:

| Venue | Character |
|---|---|
| **Journal of Open Source Software (JOSS)** | Short paper, reviews the software rather than the prose. Fast, free, indexed, well regarded for tools. The obvious first choice. |
| *Digital Scholarship in the Humanities* | Full article. Slower, more prestigious in digital humanities, expects a research contribution alongside the tool. |
| *International Journal of Corpus Linguistics* | Your actual disciplinary audience. Best for reaching the people who would use it. |

JOSS requires the software to be open source, documented, tested and archived
with a DOI. Everything in this document is on its checklist, which is a
convenient way of saying that doing this properly now makes that submission
straightforward later.

---

## 6. Version control and backup

You are working on one laptop with no repository. That is the largest
unmanaged risk in the project.

**Before 1 September:**

```
git init
git add .
git commit -m "Phase 1 complete"
git remote add origin https://github.com/<you>/corpusprep.git
git push -u origin main
```

Three months of evening work currently exists in one folder on one machine.
A single failure loses all of it, and no part of the schedule accounts for
that.

**Tag each milestone** (`v0.3`, `v0.4`, and so on, as the itinerary
specifies). Tags are what make Zenodo issue a DOI, and what let you return to
a known-good state when a week goes badly.

---

## 7. Documentation

Minimal but real. Four files, none long:

| File | Purpose |
|---|---|
| `README.md` | What it is, how to run it, one screenshot. The first thing anyone reads. |
| `CITATION.cff` | How to cite it. |
| `LICENSE` | The licence text. |
| `CHANGELOG.md` | What changed in each release. Ten minutes per release; invaluable at review time. |

The specification and the itinerary are working documents rather than
documentation, and belong in a `docs/` folder rather than at the root.

---

## 8. Support and expectations

Once the tool is public, people will write to you. Decide in advance what you
are offering, and say so in the README.

Suggested wording:

> CorpusPrep is research software maintained by one person alongside other
> work. Bug reports are welcome through GitHub issues. Feature requests will be
> read but may not be implemented. There is no guaranteed response time.

This is not discouraging; it is the difference between a tool you maintain
sustainably and an obligation you come to resent.

---

## 9. What this costs

| Item | Cost |
|---|---|
| Hosting | £0 |
| DOI and archiving | £0 |
| Version control | £0 |
| Domain name (optional) | £10 to £15 per year |
| **Total** | **Under £15 per year** |

This holds only while the tool remains serverless. Adding accounts and file
upload introduces hosting, database and data protection costs, as set out in
`corpusprep_web/AUTHENTICATION.md`. The economics of the current design are one
of its quieter advantages.

---

## 10. Sequence

**Before 1 September, two evenings:**

1. Create the repository, push everything, tag `v0.2`.
2. Choose and add a licence.
3. Enable GitHub Pages from `docs/`.
4. Write the README.
5. Register the domain if you want one.

**At the end of Phase 2, one evening:**

6. Connect Zenodo, create the `v1.0` release, obtain the DOI.
7. Add `CITATION.cff` with that DOI.

**After external validation:**

8. Write the paper. Submit to JOSS.

Steps 1 and 2 are the urgent ones. Everything else can wait; losing the work
cannot be undone.

---

## Sources

- [GitHub Pages limits](https://supadrop.host/blog/github-pages-limits/)
- [GitHub Pages free tier 2026](https://agentdeals.dev/vendor/github-pages)
- [Zenodo: GitHub and Software](https://help.zenodo.org/docs/github/)
- [Making code citable with Zenodo and GitHub, Software Sustainability Institute](https://www.software.ac.uk/blog/making-code-citable-zenodo-and-github)
- [Software citation, CodeRefinery](https://coderefinery.github.io/social-coding/software-citation/)
