# VCF REST API

A REST API over a VCF (Variant Call Format) file.

**Stack**

- Python 3.12
- Django 6.1
- Django REST Framework 3.18

---

## Quick start

```bash
git clone https://github.com/Eamateli/vcf-rest-api-v1.git
cd vcf-rest-api-v1

python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# paste that into SECRET_KEY in .env

pytest                       # 204 tests
python manage.py runserver
```

```bash
curl -s "http://127.0.0.1:8000/variants?limit=2"
```

It runs against `data/sample.vcf`, a 50-row sample, so there is nothing to configure. To use
your own VCF, see below.

### With Docker

```bash
docker compose up
curl -s "http://127.0.0.1:8000/variants?limit=2"
```

## Running it against your own VCF

One environment variable. Nothing else changes.

```bash
VCF_PATH=/path/to/your.vcf python manage.py runserver
```

Or set `VCF_PATH` in `.env`. Under Docker, drop the file in `data/` and set
`VCF_PATH=/app/data/your.vcf`.

The API reads the column count from the file's `#CHROM` header at request time, so a file with
eight columns and one with twelve both work, and rows appended to either keep that file's own
width.

---

## The API

One resource, four verbs.

| Method | Request | Success | Failure |
|---|---|---|---|
| `GET` | `/variants?offset=0&limit=20` | `200`, a page of variants with `next`/`previous` links | `400` bad parameters |
| `GET` | `/variants?id=rs123` | `200`, every matching row | `404` no match |
| `POST` | `/variants` + JSON body | `201`, the stored variant | `400` invalid, `403` bad secret |
| `PUT` | `/variants?id=rs123` + JSON body | `200`, `{"updated": n}` | `400`, `403`, `404` |
| `DELETE` | `/variants?id=rs123` | `204`, no body | `400`, `403`, `404` |

**Writes require a shared secret** in the `Authorization` header, matching `VCF_API_SECRET`.

```bash
curl -X POST "http://127.0.0.1:8000/variants" \
  -H "Authorization: $VCF_API_SECRET" -H "Content-Type: application/json" \
  -d '{"CHROM":"chr1","POS":1000,"ID":"rs123","REF":"G","ALT":"A"}'
```

### Content negotiation

Content negotiation is the client telling the server which format it wants, and the server picking from what it can produce.

`Accept: application/json` or `application/xml`. Absent or `*/*` falls back to JSON. Anything
else returns `406`.

```bash
curl -H "Accept: application/xml" "http://127.0.0.1:8000/variants?limit=2"
```

### Caching

Every `GET` returns an `ETag`. Send it back as `If-None-Match` and a matching request returns
`304` **without opening the VCF at all**.

```bash
ETAG=$(curl -sI "http://127.0.0.1:8000/variants?limit=2" | grep -i etag | cut -d' ' -f2 | tr -d '\r')
curl -s -o /dev/null -w "%{http_code}\n" -H "If-None-Match: $ETAG" "http://127.0.0.1:8000/variants?limit=2"
```

---

## Design

### Layered: `vcf_core` knows nothing about HTTP

The code that understands VCF files is kept separate from the code that understands the web, so neither can break the other.

```
vcf_core/   domain logic: parsing, validation, pagination, storage. Imports no Django.
api/        a thin DRF adapter. Turns HTTP into calls on vcf_core and back.
config/     settings and URLs.
```

The rule is one-directional: `api` may import `vcf_core`; `vcf_core` may never import `api`,
`django` or `rest_framework`. `vcf_core` reports "nothing matched"; `api` decides that means
404.

That split is why the domain unit tests need no Django, no settings module and no test client,
and why the whole `vcf_core` package is reusable by a non-Django implementation unchanged.

### Permissive read, strict write

The parser accepts whatever is genuinely in the supplied file. The write validators enforce the
brief's narrower rules.

Applying the brief's rules on read would reject **6.11%** of Saphetor's own data:

| rule | rows in the supplied file it would reject |
|---|---|
| `CHROM` must be `chr1`–`chr22`, `X`, `Y`, `M` | 3.08%, unplaced scaffolds like `chrUn_gl000225` |
| `REF` must be a single `A`/`C`/`G`/`T`/`.` | 6.11%, deletions such as `CAG → C` |
| `ALT` must be a single base | 4.70%, insertions |
| `ID` must be `rs<integer>` | 0.21% |

So `tests/unit/test_parser.py` asserts `chrUn_gl000225` is **accepted** and
`tests/unit/test_validation.py` asserts it is **rejected**. Both are correct: they guard
opposite directions.

A consequence: the API cannot `POST` an indel, because the brief requires single-base alleles.
That is the brief applied as written, not an oversight.

### Round-trip fidelity

The supplied file has ten columns; the API exposes five. Each `Variant` carries the original
line verbatim in `source_line`, and reads and rewrites emit that string rather than rebuilding
a row from parsed fields. Rebuilding would silently delete QUAL, FILTER, INFO, FORMAT and the
sample genotype from every row it touched.

`tests/unit/test_round_trip.py` reads the file, writes it back and asserts the bytes are
identical. `tests/smoke/` runs the same assertion over the real 202,464-row file.

### Streaming, never slurping

`.read()` and `.readlines()` are never called on the VCF. Rows are yielded one at a time and
sliced with `itertools.islice` **before** parsing, so a page never builds objects it will
discard. Memory is constant at any file size.

### Safe writes

Every mutation takes an advisory `fcntl.flock` on a sidecar `.vcf.lock` file. The lock lives on
the sidecar rather than the VCF because `os.replace` gives the VCF a new inode, so a lock held on
the old file would protect nothing exactly when a rewrite is in flight.

`PUT` and `DELETE` rewrite the file by building a temporary file in the same directory,
`fsync`ing it, and then `os.replace`-ing it into position. That swap is atomic on POSIX: a
reader sees either the complete old file or the complete new one.

Both `PUT` and `DELETE` count matches first and return without touching the file when nothing
matched, so a 404 never rewrites 100 MB and never invalidates clients' caches.

### Audit log

Not in the brief. In clinical genomics an unlogged change to a variant record is unacceptable,
and a file-as-storage design has no history of its own: no git, no transaction log, and
`os.replace` destroys the previous version completely.

Every mutation appends one JSON object to `AUDIT_LOG_PATH`, inside the same lock, immediately
after the write succeeds:

```json
{"ts":"2026-09-06T14:03:11Z","method":"PUT","id":"rs4000001",
 "before":["chr2\t41522\trs4000001\tA\tG\t410.55\tPASS\t...\tGT:DP\t0/1:31"],
 "after":{"CHROM":"chr1","POS":1000,"ID":"rs4000001","REF":"G","ALT":"A"},
 "authenticated":true}
```

JSONL rather than a JSON array: appending costs one write instead of rewriting the file's tail,
it streams at any size, and a crash mid-write costs one record rather than corrupting the whole
document. `before` holds complete raw rows, so prior state is reconstructible.

```bash
tail -f data/audit.jsonl
jq 'select(.method=="DELETE")' data/audit.jsonl
```

---

## Security

**File-format injection is the one that matters.** The VCF is tab-separated and
newline-delimited, so a tab or newline inside a posted field would let a caller write extra
rows or destroy the column structure:

```json
{"ALT": "A\tX\tY\nchr9\t999\trs666\tT\tC"}
```

Every string field is rejected if it contains any control character, before anything reaches
the file. `tests/functional/test_injection.py` posts exactly that payload and asserts a 400 with
the file unchanged. The brief marks validation optional; this check is not.

**Constant-time secret comparison.** `hmac.compare_digest`, never `==`. `==` returns as soon as
two characters differ, so response timing leaks how many leading characters were correct, and a
secret can be recovered one character at a time.

**An unset secret refuses all writes.** `compare_digest("", "")` is `True`, so without an
explicit empty-secret check an unconfigured deployment would accept writes from anyone sending
no header at all. Misconfiguration fails closed.

**`limit` is capped at 1000**, so `?limit=99999999` cannot exhaust memory.

**XML is generated, never parsed**, so XXE does not apply.

**No secret is in source.** `SECRET_KEY` and `VCF_API_SECRET` come from the environment,
`.env` is gitignored, `.env.example` is committed.

### 403, not 401

The brief specifies `403` for a missing or wrong secret. HTTP semantics would normally use
`401` for missing credentials and `403` for insufficient permission. The brief is followed as
written.

---

## Measured performance

On the supplied 100 MB, 202,605-line file:

| request | time |
|---|---|
| `offset=0, limit=20` | 0.1 ms |
| `offset=1000` | 1.8 ms |
| `offset=100000` | 61.5 ms |
| `offset=200000` | 86.3 ms |
| `?id=rs...` (full scan) | 367 ms |
| `304` cache hit | no file access at all |

The first page reads 161 of 202,605 lines and stops.

---

## Known limitations

**Offset pagination is O(n).** `islice` still has to walk the rows it skips, so cost grows with
paging depth: 860 times between page 1 and page 10,000 above. The fix is a byte-offset index built
at startup (~1.6 MB for 202k rows, then `f.seek()`), giving O(1) access. It is not built here
because every write invalidates it, and that invalidation could not be tested properly in the
time available. A production system would use that, a tabix index, or cursor pagination keyed on
`(CHROM, POS)` rather than a row number. It is the same problem as `LIMIT 20 OFFSET 200000` in
SQL, and has the same fix.

**No `count` in the paginated response.** A total would mean a full scan per request. The brief
asks for previous/next navigation, not a total.

**The ETag can serve stale data.** The brief derives it from request parameters alone, so it
cannot notice that the file changed: `GET` a page, `POST` a variant, re-request with
`If-None-Match`, and you get a `304` with stale content. This is implemented as specified and
both behaviours are tested. One test demonstrates the stale `304`, another proves it is gone
with `ETAG_INCLUDE_FILE_MTIME=True`, which folds `os.stat().st_mtime_ns` into the hash.
`stat` reads metadata, not content, so that still satisfies "do not read data from the VCF file".
It is off by default because the brief says what it says. `mtime` has finite resolution, so two
writes within one tick can still collide; closing that fully means hashing content, which the
brief forbids.

**Quality values in `Accept` are ignored.** DRF groups accepted types by specificity and then
takes renderers in configured order, so `application/xml;q=0.9,application/json;q=0.8` returns
JSON. Strictly non-conforming to HTTP, outside the brief, and pinned by a test so it cannot
drift silently.

**One writer at a time.** All writes are serialised by a single lock on a single file. That is
the correct ceiling for this design and it does not scale horizontally.

**The audit log is not transactional.** If the log write fails after the file write succeeds,
the mutation goes unrecorded. Closing that needs write-ahead logging, out of scope at this
scale.

**The audit log records no identity.** A single shared secret carries none. It records only
that a valid secret was presented. Identity would need per-user credentials the brief does not
specify.

**POSIX only.** `fcntl.flock` does not exist on Windows. `os.replace` is atomic there too, but
the locking would need `msvcrt.locking`. This runs on Linux, in Docker and in CI.

---

## Tests

```bash
pytest                          # 204 tests
pytest --cov --cov-report=term-missing
pytest tests/smoke -v           # only if the real VCF is present
```

Coverage is 100%, with CI failing below 90%.

```
tests/unit/         vcf_core in isolation - no Django, no HTTP
tests/functional/   every endpoint through DRF's test client
tests/smoke/        the real 100 MB file, skipped when absent
```

**No test reads or writes the real VCF or `data/sample.vcf`.** Every test builds its own file in
`tmp_path` and points `settings.VCF_PATH` at it. The write tests append and delete rows. Aimed
at a committed fixture they would corrupt it, and aimed at a real dataset they would corrupt
that.

Every status code the brief names appears in an assertion: 200, 201, 204, 304, 400, 403, 404,
406. So do the concurrency case (eight threads appending, no lost or interleaved rows), the
injection case, and the byte-identical round trip.

### Why there is a sample VCF instead of the supplied one

The brief says not to ship the supplied file, so without a fixture you would clone a repo you
cannot run. The `POST`, `PUT` and `DELETE` tests mutate the file, so pointing them at the real
one would corrupt the only copy. And 50 rows run in milliseconds, so the suite runs on every
save.

The fixture mirrors the real file rather than being a clean invention: the same ten columns, a
sample column name containing spaces, unplaced scaffolds like `chrUn_gl000225`, 20% of rows with
`.` for ID, four deletions, four insertions, duplicate rs IDs, and the real file's maximum
position. Every edge case that would break a naive parser is in there.

The full suite was run against a copy of the supplied file before submission.
`tests/smoke/test_real_vcf.py` is that check, kept in the repo so it can be repeated.

---

## Configuration

| variable | default | purpose |
|---|---|---|
| `SECRET_KEY` | *required* | Django signing key. Unset raises rather than defaulting. |
| `VCF_PATH` | `data/sample.vcf` | which VCF to serve |
| `VCF_API_SECRET` | `""` | write secret. Empty refuses all writes. |
| `AUDIT_LOG_PATH` | next to the VCF | append-only mutation log |
| `DEBUG` | `False` | compared as a string, since `bool("False")` is `True` |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | comma-separated |
| `ETAG_INCLUDE_FILE_MTIME` | `False` | fold the VCF's mtime into the ETag |

---

## Not built, deliberately

Why there is no database, and what the schema would be if there were, is in
[docs/if-this-were-a-database.md](docs/if-this-were-a-database.md).

A database or ORM. Caching layers, Redis, queues. Async views, since there is no I/O concurrency
benefit for a single locked file. Rate limiting or OAuth; the brief specifies one shared secret.
Abstract base classes or plugin registries with a single implementation. A `.bak` restore, because one
backup slot means the second write destroys the first, a copy per write on a 100 MB file is
expensive, and atomic writes already prevent the truncation failure that motivates backups.
