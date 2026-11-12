# ARCHEAN TECHNOLOGIES: twenty years of capital, rebuilt from its filings

Submission for the Takeovers **Actes** challenge (Data / ML Engineer track), SIREN 480489707.
`results.json` is at the root and validates against the official schema.

## The problem

A French company never files a statement of who owns it. It files minutes, each one a change to a state
that only the previous minutes describe. The task is to replay those changes from 17 scanned filings
(2005 to 2025) and to show, for every figure, the page and the box it was read from.

## The result

13 cap-table states, 39 events, 12 holders over the life of the company.

| # | as of | capital (EUR) | shares x nominal | holders | status |
|---|---|---|---|---|---|
| S01 | 2004-12-15 | 37 000 | 370 x 100 | Blanco Marina 155 (41.89 %), Aumont 155 (41.89 %), Gicquel 60 (16.22 %) | CONFIRMED |
| S02 | 2005-05-17 | 150 000 | 1 500 x 100 | Aumont, Blanco Marina, Gicquel, Guellati, Leroux, Roujean: counts not documented | UNRESOLVED |
| S03 | 2005-08-16 | 150 000 | 1 500 x 100 | Blanco Marina 823 (54.87 %), Aumont 617 (41.13 %), Gicquel 60 (4 %) | UNRESOLVED |
| S04 | 2006-10-20 | 150 000 | 1 500 x 100 | Blanco Marina 803 (53.53 %), Aumont 637 (42.47 %), Gicquel 60 (4 %) | CONFIRMED |
| S05 | 2006-10-20 | 200 000 | 2 000 x 100 | Aumont 967 (48.35 %), Blanco Marina 953 (47.65 %), Gicquel 80 (4 %) | CONFIRMED |
| S06 | 2006-10-20 | 200 000 | 2 000 x 100 | Blanco Marina 953 (47.65 %), Aumont 742 (37.1 %), Capgras 225 (11.25 %), Gicquel 80 (4 %) | SUPPORTED |
| S07 | 2007-09-07 | 200 000 | 2 000 x 100 | Blanco Marina 953 (47.65 %), HADEAN 822 (41.1 %), Capgras 225 (11.25 %) | SUPPORTED |
| S08 | 2008-04-30 | 200 000 | 2 000 x 100 | HADEAN 1 047 (52.35 %), Blanco Marina 953 (47.65 %) | SUPPORTED |
| S09 | 2008-06-27 | 200 000 | 2 000 x 100 | HADEAN 2 000 (100 %) | CONFIRMED |
| S10 | 2008-06-27 | 200 000 | 200 000 x 1 | HADEAN 200 000 (100 %) | CONFIRMED |
| S11 | 2008-06-27 | 368 102 | 368 102 x 1 | HADEAN 217 241 A (59.02 %), FPCI Sécurité 64 655 B (17.56 %), FPCI Financière de Brienne 43 103 B (11.71 %), Galia Venture 30 172 B (8.2 %), FIP Galia PME 4 12 931 B (3.51 %) | SUPPORTED |
| S12 | 2017-02-21 | 217 241 | 217 241 x 1 | HADEAN 217 241 (100 %) | CONFIRMED |
| S13 | 2018-03-23 | 400 000 | 400 000 x 1 | HADEAN 400 000 (100 %) | CONFIRMED |

The tax forms 2059-F for the years ended 31 December 2018 to 2024 still show HADEAN (SIREN 499979540)
with the 400 000 shares.

Each event and each state carries a `status`:

- **CONFIRMED**: stated by a filing.
- **SUPPORTED**: several concordant elements, proof incomplete.
- **UNRESOLVED**: the documents are insufficient or contradict each other.
- REFUTED is used in notes only, for a figure the documents themselves disprove.

28 events are CONFIRMED and 11 SUPPORTED. 7 states are CONFIRMED, 4 SUPPORTED, 2 UNRESOLVED. A state is
SUPPORTED as soon as one of its lines is inferred, or carried forward from an older filing, rather than
stated for that date.

## Where the documents disagree, or stop

These are in `notes` and in the `note` / `restated` fields of the states concerned. None was smoothed over.

1. **Twenty shares move with no deed (UNRESOLVED).** The meeting of 8 August 2005 records Blanco 823,
   Aumont 617, Gicquel 60, and says this table follows the share register and overrides the sale
   protocol, "which contains an error". The attendance sheet signed on 20 October 2006 says 803, 637, 60.
   Nothing filed in between explains it. I keep both states (S03, S04) and I do not invent a transfer.
   The 2007 HADEAN deed lists a single acquisition by Aumont, dated 16 August 2005, and his later 742
   shares only add up from 637 (637 + 330 - 225), so the 2005 table is the more doubtful of the two.
2. **A printed percentage is wrong (CONFIRMED).** The same 2005 table gives Gicquel 6,00 % for 60 shares
   out of 1 500, which is 4 %. Its three percentages add up to 102 %. The scan is clear: the error is in
   the document, not in the OCR.
3. **Who subscribed in May 2005 is not filed (UNRESOLVED).** 1 130 shares are issued and three people
   appear (Guellati, Leroux, Roujean), then sell everything three months later. No filing gives a count
   for any of the six holders, so S02 lists them with `shares: null`. The meeting of 4 March 2005 that
   decided the increase is not in the corpus.
4. **Blanco Marina leaves with no deed (SUPPORTED).** He holds 953 shares after October 2006. On
   27 June 2008 HADEAN decides as sole shareholder. The transfer is inferred from those two facts and
   marked `grounding: indirect`: the box cited proves the result, not the act.
5. **The 2008 investors are not named in 2008 (SUPPORTED).** The filing is an extract that skips
   resolutions 12 to 15, where the subscribers are named. The four funds come from the buy-back list of
   21 February 2017. Their counts are exactly 375 000, 250 000, 175 000 and 75 000 euros divided by the
   2008 price of 5,80 and rounded down, and they add up to the 150 861 B shares issued.
6. **185 759 or 182 759 (REFUTED).** On 23 March 2018 the sole shareholder decides an increase of
   182 759. One page later the amended article 6 says 185 759, and the updated statutes copy it.
   217 241 + 185 759 is 403 000, not 400 000. The detector finds this one on its own (see below).
7. **A sale with no deed and no date (SUPPORTED).** Aumont is authorised on 20 October 2006 to sell 225
   shares to Capgras. The page cited only authorises it. That it happened follows from two later deeds
   (Aumont contributes 742 shares in 2007, Capgras 225 in 2008). The event carries the authorisation
   date with `earliest_date` and `latest_date`.
8. **Two increases without a completion date.** The 2006 increase (set-off, subscriptions open four
   weeks) and the two 2008 increases (subscriptions open three weeks, extendable) are dated by their
   decision, as every later filing does. The certificates are not filed. For 2008 the statutes annexed to
   the decisions already show 368 102, but they were adopted subject to completion, and a report dated
   22 July 2008 still prints 200 000 in its heading. The first later filing with 368 102 is from 2010.
9. **The old shares become class A with no resolution in the file.** After the split the 200 000 shares
   are "of the same class". The statutes annexed to the same decisions count 217 241 A shares, so the
   old ones were converted. Resolution 7, which would say so, is missing from the extract.
10. **Smaller ones, with no effect on the cap table.** The 2007 HADEAN deed says Gicquel subscribed in
    May 2005, although he holds 60 shares before and after. The two reports of the commissioner for
    special benefits give different caps for the A dividend. The 2008 minutes split the B-share premium
    into two amounts that add up to the whole price plus ten cents. The 2017 buy-back excess is charged
    to the share premium by the meeting and to other reserves by the president.

## Three decisions that shape the timeline

**An entry or an exit never moves shares.** Only a capital increase, a capital decrease or a transfer
does. `SHAREHOLDER_ENTRY` and `SHAREHOLDER_END` are consequences: the replay computes who appeared and
who disappeared, and refuses a ledger that declares anything else. Each of them names its cause in
`mechanism_event_ids`. This is the rule that stops a contribution from being counted once as a transfer
and once as an entry.

**A date is the date the filing gives for the effect, never the deposit date.** When the completion
certificate is missing I use the decision date and say so in `date_precision`. The deposit date is only
ever read from the file name to order documents.

**What is not documented stays empty.** Unknown counts are `null`, percentages follow. A nominal split
has no code in the taxonomy, so S10 has no event: it carries a `corporate_action` and its own evidence.

## How it works

```
upstream/data  ->  corpus.py   inventory, registry metadata, OCR lines, 300 dpi pixels -> 0-1 boxes
                   detect.py   triage of pages, parsing of every capital sentence, cross-mentions
ledger/archean.toml            the reviewed facts: document, page, a few words copied from the OCR
                   ground.py   words -> OCR lines -> box. No match, or two, is an error
                   replay.py   deterministic replay of the ledger into cap-table states
                   validate.py official schema + business rules, on results.json alone
                   build.py    the command line
```

The ledger holds no coordinates. Each fact stores the INPI id, the page and a few words of the OCR line.
`ground.py` resolves them at build time and fails when the words are absent or ambiguous, so a box
cannot exist without the text under it. The conversion is `pixel / (page size in points x 300 / 72)`,
checked against `polygon_to_norm` from the official `tools/bbox_viewer.py`. The page size has to come
from each PDF: 7 of the 17 files declare pages of about 1 653 x 2 352 points (the scan's pixel grid
stored as points), so dividing by an assumed A4 would misplace every box in those files.

Extraction is a reviewed ledger, not an end-to-end model. With 17 documents and a cap table that must
be exact, precision matters more than automation. What is automatic, and reusable on another company,
is everything around the ledger:

- `actes detect` flags the pages worth reading (61 of 293) and the test suite checks that every page
  the ledger cites is among them.
- It also parses every sentence that states a capital change or level (49 of them), and compares each
  with the replayed timeline: 34 corroborate an event, 13 state a level the timeline goes through,
  2 contradict it. Those 2 are the 185 759 above. An unexplained sentence fails the tests.
- `validate.py` re-derives every transition from `results.json` alone and catches 20 kinds of
  corruption that the tests inject (a transfer that changes the capital, a contribution counted twice,
  a seller who keeps his shares, an ownership cycle, a pixel box, a guessed SIREN...).

## Run it

Python 3.11 or later. **No API key and no network call at run time**: `.env.example` lists one optional
variable, the path to the corpus.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
scripts/fetch_corpus.sh          # clones takeovers-ai/engineering-challenges at a705bcc into ./upstream
                                 # or: export ACTES_DATA_DIR=/path/to/engineering-challenges/data

python -m actes inventory        # the 17 actes, pages, OCR coverage, registry labels
python -m actes detect           # pages flagged, capital sentences cross-checked with the timeline
python -m actes build            # ledger -> results.json, refused if schema or invariants fail
python -m actes proofs           # every cited box drawn on its page by the official bbox_viewer.py
python -m actes lines <inpi_id> <page>   # OCR lines of a page with their normalized boxes
pytest                           # 46 tests; those that read the corpus skip without it
```

## What is verified, and how

| check | how | result |
|---|---|---|
| official schema | `jsonschema` Draft 2020-12 on `schema/results.schema.json` | pass |
| event ids unique, `caused_by` resolves, each event used by exactly one state | `validate.py` | pass |
| dates valid, chronological, no event after its state | `validate.py` | pass |
| shares add up, percentages recomputed, capital = shares x nominal | `validate.py`, 13 states | pass |
| capital only moves with a capital event, holders only change with an entry or exit | `validate.py` | pass |
| per-holder conservation across every transition | `validate.py` | pass |
| every document and page exists | 85 sources against the corpus | pass |
| each snippet is the OCR text inside its box | read back without the grounding code | pass |
| same boxes as the official viewer's conversion | every OCR line of every cited page | pass |
| each box sits on ink | box rendered from the PDF with PyMuPDF | pass |
| each party is named in the passage cited for it | entries, exits, transfers | pass, 2 declared exceptions |
| the replay on a hand-computable scenario | incorporation, entry, partial sale, total sale, increase | pass |
| boxes looked at on the rendered page (by the agent) | 36 of the 85 proof images, across scans, A4 pages and tax forms | all on target |

A valid JSON is not a correct cap table. The schema is the first line of the table, not the argument.

## Bonus: the group

Done only where the evidence was already on the table. 26 nodes, 9 edges, each edge with a box.

- HADEAN holds 100 % of ARCHEAN TECHNOLOGIES (2059-F, year ended 31 December 2024).
- ARCHEAN TECHNOLOGIES holds 100 % of ARCHEAN LABS (843071218) and of ARCHEAN MOTION, a company in
  Lisbon. The tax form's SIREN box for ARCHEAN MOTION holds 480489707, ARCHEAN TECHNOLOGIES' own
  number. A foreign company has no SIREN, so the node is `resolved: false`.
- HADEAN's attendance sheet of 28 June 2019 lists its own holders: Xavier Aumont 73.76 %,
  Michel Capgras (deceased) 10.36 %, AIR SYSTEM SERVICE (352890354) 7.93 %, CHANGE BY FIDSO 4.84 %,
  Franck Gicquel 3.11 %. Capgras' shares were bought back and cancelled on 6 April 2022.
- ARCHEAN INTERNATIONAL is named once, as the other party to an agreement: `contract_counterparty`,
  unresolved, no holding.
- The 16 other companies are nodes with `in_group: false`. That is computed, not asserted: the build
  scans every filing of all 20 companies for the SIREN and denominations of the others, and stops if
  a company marked unrelated and a group company name each other.

## Limits

- **Missing documents.** The meeting of 4 March 2005, the full minutes of 27 June 2008, the deed of
  Blanco Marina's exit and the share transfer register are not in the corpus. I did not pull them from
  INPI. Items 1, 3, 4 and 5 above would probably close with them.
- **Seven events are grounded outside the subject's folder.** The 2007 and 2008 contributions to
  HADEAN are only in HADEAN's own filings (E17 to E23 cite documents of SIREN 499979540).
- **The four funds are named as in 2017.** In 2008 they may have carried other names. The filings give
  them no legal form and no SIREN, so their `kind` is `UNKNOWN`.
- **The detector is tuned on this company.** Its patterns are French capital vocabulary and I measured
  it on one company only. It is a review aid with a recall test, not an extractor.
- **No second OCR.** The shipped OCR covers all 293 pages, mean line confidence 0.97. I read OCR text
  and looked at the rendered page whenever a figure mattered. A wrong digit in a line I did not look at
  would only be caught if it broke an invariant.
- **Group.** AIR SYSTEM SERVICE, LES IMPRESSIONS DUMAS and ETABLISSEMENTS E.PECOU have no OCR and I
  did not read their PDFs. The registry labels of AIR SYSTEM SERVICE's actes describe transfers inside
  the Dumas family; I do not assert them as edges.
- **No external source is used.** A web search found no press or registry page that names the 2008
  investors or documents the 2008 exit. Nothing in `results.json` rests on anything outside the corpus.

## Trade-offs

| choice | instead of | why |
|---|---|---|
| reviewed ledger | LLM extraction at run time | exactness on 17 documents, no key to set, reproducible byte for byte |
| anchors resolved at build time | coordinates stored by hand | a box cannot outlive or precede its text |
| shipped OCR only | Docling, OCRmyPDF, docTR | full coverage already; a second engine with no reference to compare against adds noise |
| 30 lines of standard library | NetworkX | the graph has 26 nodes; a cycle check is a few lines |
| decision date plus `date_precision` | guessing a completion date | the certificates are not filed |
| two states for 2005 and 2006 | one reconciled state | the documents disagree and I cannot tell which is right |

`docs/github-references.md` records the eight reference projects I looked at, at which commit, and
what each one changed here (one check adopted, the rest declined, with reasons).

## What I left out

- Pulling the missing filings from INPI and the BODACC notices.
- An extraction step that proposes ledger entries, behind the same grounding gate.
- Running the detector on the 19 other companies to measure its precision and recall.
- Reading the three companies that have no OCR.
- The Bilan challenge (the brief asks for one of the two).

## How I used AI

The whole submission was produced with **Claude Code** (Anthropic's coding agent) working from two
written briefs of mine.

**What I did myself.** I wrote the briefs: the scope, the evidence standard (every event checkable in
its original page, no box invented to satisfy a validator), the four statuses, the rule that an entry,
an exit and a transfer may describe one movement and must be applied once, the list of tests, the
instruction to keep contradictions instead of resolving them, and the decision to submit.

**What I delegated.** Reading the 17 filings and the related ones, the ledger, all the code, the tests,
this README, the repository and the pull request. The agent also ran sub-agents: one web search (hiring
status and press on the 2008 round, which found nothing usable), one to read the eight reference
repositories, and three independent reviewers.

**The independent review.** Three reviewer agents, read-only and with no access to the reasoning behind
the ledger, were asked to refute it: two re-read every cited page against its event, one read all 17
filings first and only then compared with `results.json`. They recomputed every count, amount and
percentage and found no wrong figure, no missing capital movement and no unsupported event. They
returned 21 findings, all accepted: statuses and dates stated more firmly than the documents allow, and
three inconsistencies the first pass had missed (items 8, 9 and the premium split in item 10).

**What was checked, and by whom.** By the agent: the 46 tests, and 36 proof images looked at one by
one. By me: I have not re-read the 17 filings line by line. Every figure here is machine-read and
machine-checked. The proof images exist so that anyone, including me, can check a box in seconds.

**Where the tool was wrong, and what caught it.**

- Its first page triage flagged 20 pages or more per copy of the statutes, on vocabulary alone. It was
  rewritten to require operative wording with figures (61 pages of 293).
- Three anchors matched two OCR lines (the attendance sheet prints each figure in two columns, and
  "Actions B" and "Actions B'" are the same string once punctuation is removed). The grounding refused
  to pick one, and the anchors were made explicit.
- It marked as CONFIRMED several facts that are only inferred: the Capgras sale, three states that
  carry a holding forward, the completion of the 2008 increases by 15 July. The reviewers caught it.
  11 events and 4 states are now SUPPORTED.
- The first group build named one company "NON RENSEIGNE" and another by a different name, taken from
  the first registry entry it met. It now uses the most frequent denomination, and the cover pages for
  the two companies the registry leaves unnamed.
- It once reported the eight reference commits as missing on GitHub: its own shell loop had not split
  its arguments. Checked one by one, they exist.
- A sub-agent advised turning on `jsonschema`'s format checker. The official schema declares no format,
  so it would have checked nothing; dates are checked by a rule in `validate.py`.

## Layout

```
results.json            the submission
ledger/archean.toml     the reviewed facts, with their anchors and notes
src/actes/              corpus, ground, replay, validate, detect, build
tests/                  replay scenario, results rules and injected faults, evidence against the corpus
schema/                 the official schema and event codes, unchanged
docs/                   github-references.md
scripts/fetch_corpus.sh
```
