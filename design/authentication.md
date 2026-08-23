# On login, accounts, and what would need to change

You asked for four things from login. Three of them are done now. The fourth
is a different project, and it costs more than it looks.

---

## What works now

**Save work between sessions** — done, properly. Your name, institution,
chosen preset and recent files persist in the browser's local storage. Close
the tab, come back tomorrow, everything is as you left it. No server involved.

**Looks professional** — done. There is a real sign-in screen, the user's name
appears in the header, and it is stamped onto every preprocessing log as
*"Prepared by: …"*. For a research tool that provenance line is worth more
than the login screen itself: it makes the log a document someone can cite.

**Know who's using it** — partly. You know who is using *this copy*. Counting
users across installations needs a server (see below).

---

## What does not, and why

**Restricting access genuinely requires a backend.** Everything in this page
runs on the user's machine, so any check it performs can be bypassed by
opening the file in a text editor. A login screen with no server is a
courtesy, not a lock — and it would be dishonest to present it as one.

The sign-in here is deliberately built as a courtesy: no password field, no
security claim.

---

## What a real backend would cost

| Piece | Work | Ongoing |
|---|---|---|
| Server + hosting | Days | £5–20/month, forever |
| Accounts, sessions, password reset | 1–2 weeks | Security patching |
| File upload + storage | 1 week | Storage costs, backups |
| GDPR: privacy policy, consent, deletion | Days | Legal review |
| Ethics approval for uploaded human-subject data | Weeks | Per-project |

Call it **6–10 weeks** on top of the corpus work, plus a permanent
maintenance obligation. That is roughly the whole autumn of your schedule.

---

## The part worth thinking hardest about

Right now, **texts never leave the user's machine.** That is not a technical
accident — it is arguably the single most attractive property this tool has
for its actual audience.

A corpus linguist working with interview recordings, ethnographic transcripts,
or in-copyright literary texts frequently *cannot* upload them. Their ethics
approval may forbid it. Their publisher's licence may forbid it. Their
institution's data policy may forbid it.

"Runs entirely in your browser, nothing is uploaded" is a sentence that gets a
tool approved for use with sensitive data in about ten seconds. "Create an
account and upload your corpus" starts a conversation with a data protection
officer that can take months.

Adding a backend does not merely add work. It removes the reason a cautious
researcher would choose this over a script of their own.

---

## A middle path

If what you want is **evidence of uptake** — for a grant report, a tool paper,
or a promotion case — you can have that without touching anyone's texts:

1. **Optional registration.** A "register your use" link that posts *only*
   name, institution and date to a simple form (even a Google Form). Texts
   never move. Response rate will be low but the names will be real.
2. **Anonymous ping.** One request on load recording a timestamp and nothing
   else. Gives you a usage count with no personal data and no GDPR exposure.
   Disclose it plainly in the interface.
3. **Citation ask.** The preprocessing log already carries a "Prepared by"
   line. Add a "please cite" line to it. For academic software, citations are
   a better measure of uptake than logins, and they count for more.

My recommendation: do 1 and 3 now, keep the tool serverless, and revisit
accounts only if someone actually asks to be kept out.

---

## If you do build the backend

The current split makes it a swap-in rather than a rewrite:

- `corpusprep/` (Python) already contains the whole engine and would become
  the server-side worker unchanged.
- The web page's sign-in already funnels through a single `enter(user)`
  function — point that at a real auth endpoint and the rest of the interface
  does not change.
- Keep the browser-only mode as an option. Institutions that cannot upload
  will need it, and it costs nothing to retain.
