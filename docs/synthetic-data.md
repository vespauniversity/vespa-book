# Deriving the data chapters 8, 10 and 11 need

Status: proposal, nothing built. **Ours.** Written so that there is a direction
to offer if the author has none, and so that the decision is made once rather
than three times.

## The problem

Chapters 8, 10 and 11 need users, permissions, tenants, sessions and multi-hop
questions. ESCI has none of them. It has:

```
products     id, locale, title, description, bullets, brand, color, has_description
judgements   query_id, query, product_id, esci_label (E/S/C/I), split
```

No price, no category, no stock, no timestamp, no user, no click.

The obvious response is to generate what is missing. That collides with the
project's hardest rule - nothing derived from a random number generator may
drive a ranking example - and it throws away something better. **ESCI is
behavioural data that has not been labelled as such**: 29,844 stated intents
with 613,016 human judgements attached. A query is an intent; an `E` is "this
satisfies it"; an `S` is "this is an acceptable alternative"; an `I` is a
human-verified hard negative.

So the principle is: **derive from what ESCI already encodes, invent only what
cannot be derived, and label which is which.** A chapter resting on an invented
field may demonstrate a mechanism; it may not claim a result.

---

## One tool set, not three

Chapters 8, 10 and 11 all need "who is this user and what may they see". If each
chapter derives its own, the three will disagree, and by then the disagreement
is in three manuscripts. Everything below lives in `shared/tools/` and is shared.

Common requirements for every tool here:

- **Deterministic.** Takes a seed, produces byte-identical output for the same
  build and seed, and records a content hash the way `corpus.py` does.
- **Train split only**, for anything derived from judgements. Deriving a
  document signal from every judgement leaks test labels into the index and
  inflates every number in the book with nothing to say so. The tools take a
  split argument and refuse to run without one.
- **Emits partial updates**, not documents. These fields attach to products that
  are already indexed; a partial-update feed is about three and a half minutes
  against a full re-feed of eight and a half.
- **Writes a derivation record** next to its output: which rule produced each
  field, and whether that field is derived or invented.

---

## 1. `derive_tenants.py` - who owns a listing

**Chapter 8.** A marketplace where each brand is a seller.

**Rule.** Tenant = normalised brand. Normalisation is `" ".join(s.split()).lower()`,
which merges 43,349 raw strings into 42,960 - 389 of them differ only by case or
whitespace. 5,575 products have no brand at all and become a single
marketplace-owned tenant, which is a real category rather than a dumping ground:
listings the platform owns.

**Why brand rather than a random assignment.** Chapter 8's deliverable is a
report on how *filter selectivity* affects HNSW recall and latency, and brand
gives a selectivity range spanning four orders of magnitude — **on full ESCI;
the table below is full-ESCI, not the book's 101,341-document build.** On the
build no brand reaches 1% (`nike` 0.596%), the no-brand marketplace tenant
(5.33%) is the largest tenant, and the ladder is D23's five rungs on existing
fields (`probes/q09-tenants/VERDICT.md`; the build's counts are in chapter 8's
reports, D101 補充):

| | share of the corpus (full ESCI) |
|---|---|
| largest single tenant (`nike`) | 0.55% |
| top 1% of tenants | 24.4% |
| top 10% of tenants | 50.2% |
| tenants holding exactly one product | 29,897 |

A uniform random assignment produces uniform selectivity and flattens the exact
phenomenon the chapter exists to show. This is the same failure as chapter 6's
risk: an experimental design that cannot express the effect it is looking for.

**Output.** `tenant_id` per product, as a partial update, plus a tenant registry
with each tenant's size so the chapter can pick filter targets across the range.

**Invented, and must be labelled as such:** user, group and role. They hang off
the tenant - a seller's staff - which gives them structure but not evidence.
Chapter 8 may use them to demonstrate authorization and to test for leakage; it
may not present any relevance number that depends on them.

## 2. `derive_users.py` - who is shopping

**Chapter 10.** A user is a coherent set of shopping intents.

**Rule (D25, D109; the connected-component rule Phase 1 started from gave
63–173 held-out queries, Q10, and was replaced).** Group queries by the brand of
their `E` products: every query with an `E` product of brand *b* joins user *b*,
capped at 30 queries per user (seeded). A user is therefore an interest cluster
around one brand, not a person, and one query can seed several users at once.
The pool of queries is the build's train queries plus the ESCI train-split
queries outside the build whose `E` products are in the corpus (D25 B). A user's
preferences are the brand distribution of the products they judged `E` (the
second-order profile removes the defining brand); the colour distribution is
kept for a negative result.

Preferred over clustering query embeddings because it needs no model, cannot
drift when a model is swapped, and rests on a human judgement rather than on a
similarity threshold.

**The circularity to avoid.** Building a profile from judgements and then
evaluating against judgements is a system marking its own homework. Each user's
queries are split: the earlier ones build the profile, the held-out ones are
what recommendation quality is measured against. Both halves come from the train
split; test stays untouched until the chapter reports.

**Output.** Per-user profile tensors, and a per-user evaluation set.

**Cannot be derived, and the chapter has to say so:**

- **No timestamps.** "Earlier" and "later" are an ordering we imposed, seeded
  and deterministic, not a sequence anybody performed. Heading 4's recency decay
  therefore demonstrates a mechanism and measures nothing.
- **No clicks or impressions.** Heading 7's counterfactual metrics cannot be
  done at all on this data. Better said plainly than approximated.
- **No single-user identity.** Group membership overlaps: a query whose `E`
  products span three brands seeds three users. The chapter says so wherever a
  "user" is named.

## 3. `derive_events.py` - the feed chapter 10 asks for

**Chapter 10** asks for a user-event feed and an online profile updater, which
needs events arriving in an order.

**Rule.** For each user, emit their queries and judged products in the imposed
order as `(user_id, sequence_no, query_id, product_id, action)`.

**This is the most invented of the three and the honesty is load-bearing.** A
judgement is not a purchase and not a click - it is an annotator's opinion, made
outside any shopping session. Mapping `E` to "bought" and `S` to "viewed" makes
a usable event stream and a false claim. The tool should emit a neutral
`judged_relevant` / `judged_substitute` vocabulary and let the chapter say what
it is standing in for.

What this supports honestly: partial updates arriving while queries run,
feed-to-query visibility, and a profile that changes between requests. Those are
real mechanics and worth a chapter. What it does not support is any claim about
recommendation quality improving because a user did something.

## 4. `derive_multihop.py` - questions with a verified answer

**Chapter 11**, and the best fit of the four.

The outline planned an author-generated multi-hop question set with verified
supporting passages and hard negatives. ESCI already contains both, labelled by
people: 215,434 `S` judgements are verified alternatives, 103,786 `I`
judgements are verified hard negatives, and 86.5% of queries carry both.

**Rule.** For a query `q` with a top-graded product `p`:

> "Find an alternative to *p* that is not made by *brand(p)*."

- **Oracle answer set**: products judged `S` for `q` whose brand differs from `p`.
- **Hard negatives**: products judged `I` for `q`.
- **Reject** any question whose oracle set is smaller than a threshold, so every
  question is answerable.
- **Revised at chapter 11 step 3 (D119):** the oracle is `S` **or `E`** with brand ≠
  brand(p) (an exact match by another brand is a better alternative, not a miss);
  anchors without a brand are dropped first (D27); retrieval is restricted to the
  query's judged pool, so an unjudged product never appears in an answer. Test at
  threshold 3: 872 questions (669 with `S` alone).

That makes the oracle-versus-retrieved comparison - heading 8, and the chapter's
strongest idea - rest on human labels rather than on a generated answer key.

**Output.** A question set with, per question, the query, the anchor product,
the oracle set, the hard negatives, and the hops needed to reach it.

**Cannot be derived:** genuinely multi-turn reasoning. These are two-hop
questions built from one query's judgements. A chapter claiming deep multi-hop
research behaviour would be overstating what the construction supports.

---

## How this reaches the reader

Not fabricating data is the floor, not the standard. A number computed over an
invented field prints exactly like a measurement, and a caveat three sections
away does not stop anyone quoting the table.

So the label travels with the number:

- **Derived fields** - tenant, user, oracle set - carry human judgements behind
  them and can support a measured claim.
- **Invented fields** - roles, event ordering, event vocabulary - can support a
  demonstration that a mechanism works. They cannot support a claim that
  anything got better.
- Any table resting on an invented field says so **in its caption**, not only in
  a disclosure section. "NDCG@10 over 1,240 derived users; the event order is
  imposed by us and is not a sequence anybody performed" belongs next to the
  number.

Each of these chapters also needs a reader-facing section describing the
scenario and how the data behind it was derived - the marketplace, the seller
boundary, what a "user" is here and what it is standing in for. That is not the
author-facing disclosure section chapters 1 to 7 carry; it is the chapter
telling a reader what they are looking at, before the first number.

The test: a reader who reproduces these numbers on their own catalogue, with
real users and real events, should not be surprised by what they get. If the
book's framing would surprise them, the framing is wrong even if every number in
it is real.

## What this does not solve

Price, category and stock are absent, so chapter 8's eligibility rules have to
be built from what exists: `has_description`, bullet count, whether a colour is
set. (An earlier draft also named judgement-derived `popularity` / `exact_rate`
fields; no chapter added them — D101 補充, 2026-09-27.) Those are real
product-quality signals and enough for a marketplace rule
("listings must have a description"), but they are not the commercial rules a
reader will have in mind.

## What to do first

Write the derivation record before writing any of the tools - one table naming
every synthetic field, the rule behind it, and whether it is derived or
invented. It is the part that is expensive to change later: once chapter 8 has
printed numbers against one tenant model, chapter 10 cannot pick a different
one without re-measuring chapter 8.

The tools themselves are ordinary work. The definitions are not.
