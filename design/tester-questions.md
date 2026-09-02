# What to ask a tester

Referenced from `HANDOVER.md` as "the four questions in task #12", which had
been lost. Written down 30 August so that the next person to send this out has
them.

---

## The principle

**Ask about their corpus, not about the tool.** A tester asked "how did you
find CorpusPrep?" reports on CorpusPrep, and their answer is bounded by what
they think you want to hear. A tester asked "what is in your files that you
need removed?" reports on the world, and the answer contains rules nobody has
thought of yet.

Every rule in this package came from a real text that broke something. The
questions exist to find the next one.

---

## The four

**1. What is your corpus, concretely?**

How many files. What format they arrived in. Roughly how large. Where they came
from — scanned, downloaded, exported, scraped, transcribed.

*Why:* every measured number here comes from single files, and the tool reads
one text at a time. If the answer is "about four hundred Word documents", the
next thing to build is obvious and nobody has to guess at it. This is also the
only way to learn whether "a corpus" means ten files or ten thousand.

**2. What is in your files that you need removed, but is not language?**

In their words, with two or three real examples pasted in.

*Why:* this is where new rules come from. Interface furniture exists because
one tester's corpus was 45% URL and then 3% `Like` and `Reply`. Ask it openly
enough and the answer may be timestamps, speaker labels, page banners,
translation notices, or something nobody here has seen.

**3. Take one file through it. What did it remove that it should have kept, or
keep that it should have removed?**

Ask for the log file, not a summary. Ask which variant they used.

*Why:* this is the only precision and recall figure that will ever come from
material this project did not write. Two rules — interface furniture and
non-English headings — are currently marked *Experimental* purely because no
such evidence exists. One real answer upgrades them or corrects them.

**4. Where did you stop, hesitate, or expect something that did not happen?**

Not "what went wrong". Wrong things announce themselves. Hesitations do not,
and they evaporate within a minute of being felt.

*Why:* seven of the twelve faults found on 28–29 August were interface faults,
and none was found by a test. The recent-files list never threw an error — it
was a pause and a "why isn't this doing anything". Ask for the pauses.

---

## One more, if they are willing

**What did you do with the output afterwards, and did anything break?**

CorpusPrep is the stage before AntConc and WordSmith. Whether its output loads
cleanly into the next tool is a claim nobody here has tested.

---

## How to ask

Short message, one link, no attachments. Say how long it will take and mean it.
Say plainly that a report of "I could not work out what to do" is the most
useful reply they can send, because otherwise nobody sends it.

Give a deadline that is a fortnight away rather than none, and ask for a reply
even if they never got round to opening it — a tester who went quiet is data
about the first five minutes, and the commonest reason for silence is that
something was confusing and they were embarrassed to say so.
