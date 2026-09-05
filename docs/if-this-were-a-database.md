# If this were a database

This project has no database: the brief makes the VCF file the source of truth, and a database
would be a second copy that disagrees with the file the moment either is written. That decision
is defended in the README.

This page answers the follow-up — *what would the schema be, and what would change?* — because
the answer explains several choices in the code, and because the file-based limitations
documented in the README have exact database equivalents.

---

## The schema

Every column decision below traces to a measurement of the supplied file, not to a convention.

```sql
CREATE TABLE variant (
    id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    chrom    VARCHAR(32)     NOT NULL,
    pos      INT UNSIGNED    NOT NULL,
    rsid     VARCHAR(32)     NULL,
    ref      VARCHAR(255)    NOT NULL,
    alt      VARCHAR(255)    NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_locus (chrom, pos),
    INDEX idx_rsid  (rsid)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;
```

| decision | the measurement behind it |
|---|---|
| `rsid ... NULL` | 35,895 rows (17.7%) carry `.` — the absence of an ID, not a value. `NULL` is SQL's word for exactly that, and `WHERE rsid = '.'` then correctly matches nothing, mirroring the API's 404. |
| **no** `UNIQUE` on `rsid` | 242 rs IDs appear on more than one row. A unique constraint would reject the supplied file on import. |
| `chrom VARCHAR(32)`, not `ENUM` | 70 distinct values, including unplaced hg19 scaffolds like `chrUn_gl000225` and `chr9_gl000199_random`. An `ENUM` of the 25 canonical chromosomes would reject 3.08% of rows, and adding a value to an `ENUM` is a table alteration. |
| `ref`/`alt VARCHAR(255)`, not `CHAR(1)` | 6.1% of `REF` and 4.7% of `ALT` values are multi-base indels such as `CAG → C`. `CHAR(1)` would truncate them silently. |
| `pos INT UNSIGNED` | The maximum position in the file is 249,239,808. `MEDIUMINT` tops out at 16.7 M and would overflow; `INT UNSIGNED` reaches 4.29 B. `BIGINT` would waste four bytes per row. |
| surrogate `id` primary key | There is no natural key: `(chrom, pos)` is not unique either, since multi-allelic sites and overlapping indels share a locus. |
| `CHARSET=ascii` | Every value is ASCII. `utf8mb4` would reserve four bytes per character in index key length for nothing. |

**Rough storage**, showing the arithmetic rather than asserting a number: about 60 bytes of data
per row plus InnoDB overhead, so roughly 20 MB of table for 202,464 rows. `idx_locus` carries
`(chrom, pos)` plus the primary key, around 5 MB; `idx_rsid` similar. Call it **30 MB total** —
against a 100 MB file, because the file's bulk is the `INFO` column, which this schema does not
store.

---

## Indexing: why `?id=rs123` gets fast

**Today, without an index**, `find_by_id` reads every row of the file and checks each one:
202,464 comparisons, ~367 ms measured. It cannot stop at the first match, because 242 IDs
appear more than once.

**With `INDEX idx_rsid`**, the same lookup walks a B-tree. Depth is roughly log-base-hundreds of
the row count, so **three or four page reads** instead of 202,464 comparisons.

```sql
EXPLAIN SELECT * FROM variant WHERE rsid = 'rs62635284';
```

| | without the index | with it |
|---|---|---|
| `type` | `ALL` | `ref` |
| `key` | `NULL` | `idx_rsid` |
| `rows` | ~202464 | 1–3 |
| `Extra` | `Using where` | — |

`type: ALL` is the thing to spot in an `EXPLAIN` — it means a full table scan, and it is the
same shape as the file scan the code does now.

`idx_locus (chrom, pos)` is composite and column order matters: it serves
`WHERE chrom = 'chr1' AND pos BETWEEN 1000 AND 2000` and `WHERE chrom = 'chr1'`, but **not**
`WHERE pos > 1000` alone — a B-tree can only skip ahead on a prefix of its key. That is the
leftmost-prefix rule.

---

## Offset pagination is the same problem in both worlds

This is the strongest link between the two, and the file version is already measured in the
README.

```sql
SELECT * FROM variant ORDER BY id LIMIT 20 OFFSET 200000;
```

InnoDB walks 200,020 rows and throws away 200,000. That is exactly what `itertools.islice` does
to the file — same O(n) shape, same cause: **an offset is a count, not an address.** Nothing can
jump to "the 200,000th row" without passing the first 199,999.

Measured in this project: 0.1 ms at `offset=0`, 86 ms at `offset=200000`. A database does the
same work faster per row, but the curve is identical.

**Keyset pagination is the fix in both worlds.** Instead of counting rows, remember where you
stopped:

```sql
SELECT * FROM variant
WHERE (chrom, pos) > ('chr7', 141522)
ORDER BY chrom, pos
LIMIT 20;
```

That is an index seek — constant cost regardless of depth, because `(chrom, pos)` is an
*address*, not a count. The file equivalent is the byte-offset index described in the README:
`f.seek(byte_position)` instead of reading forward.

The trade-off is the same in both: you lose "jump to page 500", because there is no way to know
which key starts page 500 without counting. Keyset pagination gives you next and previous, which
is exactly what the brief asks for.

---

## Transactions are the database's version of the file lock

This project serialises writes with `fcntl.flock` and makes rewrites atomic with `os.replace`.
A database provides both, with more precision:

| here | database |
|---|---|
| one lock over the whole file | row-level locks; two writers touching different rows never block |
| `os.replace` — all or nothing | a transaction — `COMMIT` or `ROLLBACK`, all or nothing |
| audit log written inside the lock | the same `COMMIT` covers the row and its audit row |
| one writer at a time, globally | concurrent writers, limited only by contention on the same rows |

**Isolation levels** describe what one transaction sees of another's uncommitted work.
InnoDB's default is `REPEATABLE READ`: within a transaction, the same query returns the same
rows even if someone else commits changes meanwhile. `READ COMMITTED` sees each committed change
as it lands — cheaper, but the same query can return different results twice in one transaction.
`SERIALIZABLE` behaves as if transactions ran one after another, which is what the single file
lock here effectively achieves, at the cost of all concurrency.

The audit log's honest gap disappears too: today the file write and the log write are two
separate operations and a crash between them loses the record. In a database both are rows in
one transaction — either both land or neither does.

---

## The Django ORM, which this project does not use

Models describe tables; migrations version schema changes so any machine can rebuild the same
structure by replaying them in order.

```python
class Variant(models.Model):
    chrom = models.CharField(max_length=32)
    pos = models.PositiveIntegerField()
    rsid = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    ref = models.CharField(max_length=255)
    alt = models.CharField(max_length=255)

    class Meta:
        indexes = [models.Index(fields=["chrom", "pos"])]
```

Things worth being precise about:

**QuerySets are lazy.** `Variant.objects.filter(chrom="chr1")` runs no SQL. The query fires when
you iterate, slice or call `len()`. That laziness is what lets `.filter()` chain without a round
trip per call — and it is the same idea as this project's generators, where nothing is read until
something asks.

**The N+1 problem.** Looping over 200 rows and touching a related object on each one issues 201
queries: one for the list, one per row. `select_related` fixes it with a `JOIN` for
forward foreign keys; `prefetch_related` fixes it with a second query plus an in-Python join,
for reverse and many-to-many relations. This schema has one table and no relations, so neither
would appear here — but recognising N+1 in someone else's code is the point.

**`bulk_create`.** Importing 202,464 rows one `.save()` at a time is 202,464 round trips.
`bulk_create(objects, batch_size=1000)` makes it about 200 statements.

**`.iterator()`** streams a large result set instead of loading it into memory — the ORM's
version of the streaming reads this project does by hand.

---

## Why MariaDB rather than MySQL

They share an origin, so SQL and the wire protocol are largely interchangeable. The usual
reasons to choose MariaDB: it is community-governed rather than owned by a single vendor, fully
open-source with no proprietary enterprise tier, and it ships storage engines MySQL does not —
Aria, ColumnStore for analytical workloads, Spider for sharding.

They have diverged enough to matter: JSON is a native type in MySQL 8 but an aliased `LONGTEXT`
in MariaDB, and the two implement window functions, CTEs and invisible columns with different
histories. For a workload like this one — a single narrow table, heavy read, indexed lookups —
either would perform the same, and the choice is governance and operations rather than
performance.
