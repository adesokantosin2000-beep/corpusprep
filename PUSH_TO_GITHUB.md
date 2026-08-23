# Pushing this repository to GitHub

The repository is initialised, committed and tagged `v0.2.0`. What remains
needs your GitHub account, so it has to be done by you rather than for you.

Fifteen minutes, once.

---

## 1. Create the repository on GitHub

Go to [github.com/new](https://github.com/new).

| Field | Value |
|---|---|
| Repository name | `corpusprep` |
| Description | Corpus preparation for linguists |
| Visibility | **Public** (required for free GitHub Pages) |
| Initialise with README | **No.** One already exists here. |
| Add .gitignore or licence | **No.** Both already exist here. |

Adding any of those files at creation time will cause a conflict on the first
push, so leave all three unticked.

---

## 2. Push

In a terminal, from the `corpusprep-repo` folder:

```bash
git remote add origin https://github.com/YOUR-USERNAME/corpusprep.git
git push -u origin main
git push origin v0.2.0
```

The second push sends the tag, which is what Zenodo later turns into a DOI.
Tags are not pushed automatically.

If prompted for a password, GitHub no longer accepts account passwords over
HTTPS. Create a personal access token under **Settings, Developer settings,
Personal access tokens** and use that in place of the password. Alternatively
install the GitHub CLI and run `gh auth login`, which handles it.

---

## 3. Turn on GitHub Pages

In the repository, go to **Settings, Pages**.

- Source: **Deploy from a branch**
- Branch: **main**, folder: **/docs**
- Save

After a minute or two the application is live at:

```
https://YOUR-USERNAME.github.io/corpusprep/
```

Because it deploys from `docs/` in the repository, the page being served is
always provably the committed source. There is no upload step that can drift.

---

## 4. Replace the placeholders

Three files contain `YOUR-USERNAME`:

- `README.md`, in the "Try it" link
- `CITATION.cff`, in `repository-code`

Change both, then:

```bash
git add -A
git commit -m "Add repository URLs"
git push
```

---

## 5. Later: Zenodo and the DOI

Do this at the end of Phase 2, when you tag `v1.0`.

1. Sign in to [zenodo.org](https://zenodo.org) with your GitHub account.
2. Under **GitHub** in your Zenodo settings, switch on the `corpusprep`
   repository.
3. Create a release on GitHub. Zenodo archives it and issues a DOI.
4. Put that DOI into `CITATION.cff` and commit.

Switching Zenodo on only affects releases created *afterwards*, so enable it
before you tag `v1.0` rather than after.

---

## What was and was not committed

**Included:** the Python package, the web application, the test suite and its
fixtures, the tools, and the design documents.

**Excluded by `.gitignore`:** cleaning output, working corpora, Python cache
files, and the web application's build sources. Output is regenerated rather
than stored, and your own corpora are deliberately kept out of version control
because many are under copyright or ethical restriction.

`tests/fixtures/CBronte_Jane.txt` is committed deliberately. It is public
domain, it is 1 MB, and without it the Jane Eyre regression test silently
skips. A test that skips is not a test.

---

## A note on the folders left behind

`corpusprep-repo/` is now the authoritative copy. The originals scattered
through `Testing Cleaning` were left in place rather than deleted, so you can
confirm the repository is complete before removing them.

Once you have pushed and are satisfied, these are safe to delete:

```
corpusprep/            (now src/corpusprep/)
corpusprep_web/        (now docs/index.html, plus design/authentication.md)
tests/                 (now tests/)
check_parity.py        (now tools/)
stress_test.py         (now tools/)
fix_copy.py            (now tools/)
CorpusPrep_*.md        (now design/)
cleaned*/              generated output
corpora/, corpora_wild/  working corpora
```

Keep `CBronte_Jane.txt` wherever you like; a copy is in the repository
fixtures. Leave `adroit-learn-startup` and `adroit-tutors-live-quiz` alone,
since they are unrelated projects and were deliberately excluded.

**Work from `corpusprep-repo/` from now on.** Two copies of the source is
precisely the drift the parity harness exists to prevent, and the harness
cannot see across folders.
