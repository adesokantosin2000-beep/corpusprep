# Next steps

Today is Sunday 23 August 2026. Phase 2 begins Tuesday 1 September, nine days
away.

## Done, 23 August

- Repository created, pushed, tagged `v0.2.0`
- GitHub Pages live at https://adesokantosin2000-beep.github.io/corpusprep/
- Hosted application verified on a real EPUB: 29,187 tokens in, 25,700 out,
  body beginning correctly at ACT I
- Web application given a reproducible build in `build/`, replacing the
  hand-spliced page whose engine block existed nowhere else
- Duplicate copies removed; `corpusprep-repo` is now the only source

## Remaining, none urgent

- **A domain**, if you want one. See `design/operations.md`.
- **Zenodo and the DOI.** Belongs at the end of Phase 2, when you tag `v1.0`.
  Enable it *before* tagging, since it only archives releases made afterwards.
- **Send the link to one colleague** with a messy corpus. Costs a single
  message, and what they report may change which stage is worth building first.

---

## The original checklist, kept for reference

---

## Today, about thirty minutes

The work exists in one folder on one laptop and has never left it. That is the
only item here that cannot be recovered if it goes wrong, so it comes first.

**1. Create the repository.** Go to [github.com/new](https://github.com/new).
Name it `corpusprep`, set it **Public**, and add **no** README, `.gitignore` or
licence, since all three already exist here and would collide.

**2. Push.** In a terminal, in this folder:

```bash
git remote add origin https://github.com/adesokantosin2000-beep/corpusprep.git
git push -u origin main
git push origin v0.2.0
```

The second push sends the tag. Tags are not pushed automatically, and that tag
is what Zenodo later turns into a DOI.

If it asks for a password, GitHub no longer accepts account passwords over
HTTPS. Create a personal access token under **Settings, Developer settings,
Personal access tokens**, and paste that instead.

**3. Confirm it worked.** Reload the repository page. You should see 35 files
and the `v0.2.0` tag under Releases.

Stop there if you like. The rest is not urgent.

---

## One evening this week

**4. Turn on GitHub Pages.** Repository **Settings, Pages**. Source: deploy
from branch `main`, folder `/docs`. Save. A minute later the application is
live at `https://adesokantosin2000-beep.github.io/corpusprep/`.

**5. Open that URL and clean a text with it.** Confirm the hosted copy behaves
exactly like the local file. This is the first time the tool exists as
something you can send someone.

**6. Replace the placeholders.** `adesokantosin2000-beep` appears in `README.md` and
`CITATION.cff`. Then:

```bash
git add -A && git commit -m "Add repository URLs" && git push
```

**7. Delete the duplicates.** The old scattered copies in `Testing Cleaning`
are listed at the end of `PUSH_TO_GITHUB.md`. Once the repository is pushed
and the hosted page works, remove them and work only from `corpusprep-repo`.

Two copies of the source is exactly the drift the parity harness exists to
catch, and the harness cannot see across folders.

---

## Optional, and only if you want it

**8. A domain.** About £10 to £22 a year. Worth it if the tool will appear in
a paper, because the address then outlives your GitHub username and your
current institution. Buy it anywhere; point it at GitHub Pages. Check the
renewal price rather than the first-year price.

Not needed before September.

---

## Tuesday 1 September

Open `design/schedule-phase2.md` and begin Week 1.

That evening is deliberately not feature work. You will have been away a month,
so the task is to read `segment.py` end to end **without changing it** and
write a one-page summary of how a line becomes a labelled region. If the
summary and the code disagree, the summary is the thing to fix.

Thursday and Friday of that week build the measurement harness and the two
hand-marked answer keys. That is the foundation for everything after it: every
stage in Phase 2 is a detector, and a detector without a measured error rate
is an opinion.

---

## What happens without you

A check-in runs each Saturday at 10am. It reads the itinerary, works out which
week you should be in, runs the tests and the parity check, and looks at recent
commits. If nothing has been committed for a fortnight it will say so plainly.

---

## The short version

| When | What |
|---|---|
| **Today** | Push to GitHub. Thirty minutes. |
| This week | Pages, verify hosted copy, delete duplicates. |
| Optional | Domain. |
| **Tue 1 Sep** | Phase 2, Week 1, Day 1. Read the code, change nothing. |
