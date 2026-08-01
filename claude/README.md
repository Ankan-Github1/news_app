# claude/ — a parallel design, for comparison only

This folder is **not** your project. Nothing here imports from `Backend/`,
nothing here runs against `news.db`, and nothing here should ever be copied
wholesale. It exists so you can see one senior-shaped way to lay this out, argue
with it, and steal the ideas that survive the argument.

If a choice here doesn't convince you, don't take it. Several of these are
opinions, and I've marked which.

---

## The structure

```
claude/
  README.md            you are here
  requirements.txt
  config.py            every tunable number and model name, one file
  embedding.py         text -> vector, and cosine. belongs to neither storage nor llm
  app.py               FastAPI entry point. creates the app, wires routes, nothing else

  web/                 NOT BUILT YET
    routes.py          HTTP only: read request, call something, return response
    identity.py        cookie token in, owner_token out
    templates/         HTML

  pipeline/            NOT BUILT YET
    ingest.py          goal text -> query -> fetch -> store articles
    rank.py            scoring, top-K, the floor
    summarize.py       article + goal -> summary

  sources/
    base.py            the shape every source must return
    newsapi.py         NewsAPI, normalised into that shape

  storage/
    db.py              connection + schema + init. nothing else
    articles.py        reads and writes for the articles table
    goals.py           reads and writes for goals
    scores.py          similarity + summaries
    embeddings.py      the vector cache

  llm/
    client.py          how to talk to a model
    prompts.py         what to say to it

  util/
    urls.py
    text.py
    dates.py
```

---

## Why each choice — argue with these

### 1. `storage/` is split by table, not one big `db.py`

Yours is one `db.py`, currently around 300 lines. Once the read functions for
the web pages land it will be 600+, and every one of those functions opens a
connection, runs one query, closes it. They have nothing to do with each other
except that they're all SQL.

Splitting by table means when you're working on goals you open `goals.py` and
see nine functions, not sixty.

**When one file is better:** while the whole thing fits on two screens.
Splitting early is over-engineering. Yours crossed that line about a month ago.

**The rule that stays the same:** still no raw SQL outside `storage/`. The
convention doesn't change, just the file count.

### 2. `config.py` exists

Right now `0.28` is typed inside `filter_logic.py`, the model names live next to
the code that uses them, `page_size=30` is inside the NewsAPI call. To answer
"what are this system's settings?" you have to grep.

One file. `TOP_K`, `SCORE_FLOOR`, `EMBED_MODEL`, `SUMMARY_MODEL`, `PAGE_SIZE`,
`LOOKBACK_DAYS`. When you deploy, this is also the file that reads environment
variables, so there's exactly one place where "what's different on the server?"
is answered.

**Opinion, not a rule.** Some people hate config files and prefer constants next
to the code that uses them. That's defensible when nothing else needs the value.
It stops being defensible once two files need the same number.

### 3. `web/` and `pipeline/` are separate folders

This is the "pipeline writes, API reads" split made physical. If someone in
`web/routes.py` imports from `pipeline/summarize.py`, the folder names make it
obvious something's wrong — you're doing slow work inside a request.

Same idea as putting your knives in a different drawer from your socks. The
separation isn't enforced by anything; it just makes the mistake visible.

### 4. `sources/base.py` exists before there's a second source

You have one source. This looks like scaffolding for a feature you don't have,
which CLAUDE.md says not to build — so here's the actual argument:

`base.py` isn't a class hierarchy or a plugin system. It's one docstring saying
"a source is a function that takes a query and returns a list of dicts with
these seven keys." That's it. Maybe fifteen lines.

The cost of not having it: `filter_logic` currently reads `article['source']
['name']` and `article['publishedAt']` — those are NewsAPI's shapes, leaking
into your pipeline. Add Hacker News later and it has neither key, so you either
fake them or write a second code path.

**Where the line is:** writing down a shape is cheap and stops leaks.
Writing an abstract base class with three registered implementations for one
source is the over-engineering CLAUDE.md warns about.

### 5. `prompts.py` is separate from `llm/client.py`

The client — how you make an HTTP call to Ollama or Gemini — changes almost
never. Prompts change every day while you're tuning them.

Things that change at different speeds belong in different files. You'll edit
`prompts.py` fifty times and `client.py` twice.

This one also pays off directly for your deployment decision: swapping Ollama
for a hosted model becomes "rewrite one file", not "find every place a model
gets called".

### 6. `app.py` does almost nothing

Create the FastAPI app, include the routes, done. Maybe twenty lines.

Entry points that grow logic become the file nobody can read, because everything
ends up there — it's the path of least resistance. Keeping it deliberately
boring forces the logic somewhere it belongs.

---

## What I did NOT do here, on purpose

- **No `models/` or ORM layer.** Plain dicts, per your conventions. SQLAlchemy
  would earn its place around the time you have relationships you can't hold in
  your head. You don't.
- **No `services/` folder.** Your `services/` currently holds fetching,
  embedding and summarising — three unrelated jobs sharing a folder because they
  were all "not storage". `services/` tends to become the drawer where anything
  that isn't obviously something else goes.
- **No `tests/`.** You should have them. But adding a test folder you never fill
  is worse than not having one, and that's a conversation, not a folder.
- **No `__init__.py` anywhere.** Namespace packages, same as yours.

---

## Honest weaknesses of this layout

- **More files to navigate.** Six storage files instead of one. For a project
  this size that is a real cost, and if you find yourself jumping between four
  files to follow one request, I was wrong.
- **`util/` is a bad name** and I used it anyway. It's the same drawer problem as
  `services/`. Everything in there is genuinely tiny and stateless, so it works
  for now — but if it ever grows past six small files, something in it deserves
  a real home.
- **The `web`/`pipeline` split assumes the pipeline stays slow.** If the demo
  path ends up running ingest inside a request (which your professor-types-a-goal
  flow needs), that boundary gets crossed on purpose and the folder names start
  lying. Worth deciding deliberately rather than drifting into.
