# django-identifiers

[![PyPI version](https://img.shields.io/pypi/v/django-identifiers.svg)](https://pypi.org/project/django-identifiers/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-identifiers.svg)](https://pypi.org/project/django-identifiers/)
[![CI](https://github.com/fifoa-labs/django-identifiers/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fifoa-labs/django-identifiers/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/fifoa-labs/django-identifiers/branch/main/graph/badge.svg)](https://codecov.io/gh/fifoa-labs/django-identifiers)
[![License](https://img.shields.io/pypi/l/django-identifiers.svg)](https://github.com/fifoa-labs/django-identifiers/blob/main/LICENSE)

**Short, collision-resistant identifiers for Django with automatic generation, immutability, and bulk-create support.**

`django-identifiers` provides a small, focused identifier system for Django
models.

It handles two workflows that need different treatment:

1. normal Django model saves, where `Model.save()` can generate identifiers
   automatically; and
2. bulk insertion, where `bulk_create()` bypasses model save hooks and
   identifiers must be assigned before the insert.

The package keeps the database unique constraint as the final authority for
uniqueness, while providing generation, best-effort collision avoidance,
retry behavior, immutable identifier fields, and bulk-safe helpers.

- **PyPI:** https://pypi.org/project/django-identifiers/
- **Source:** https://github.com/fifoa-labs/django-identifiers
- **License:** MIT

```text
Identifier policy
      │
      ▼
Generate candidate
      │
      ▼
Best-effort DB check
      │
      ▼
Database write
      │
      ├── success ───────────────► done
      │
      └── IntegrityError
              │
              ▼
         regenerate / retry
```

The package solves identifier generation and lifecycle behavior.

Your application decides which models need identifiers, which fields are
managed, which patterns they use, and whether those identifiers may change.

---

## Why django-identifiers?

Short application identifiers appear everywhere:

- public codes
- order references
- opaque record identifiers
- SKUs
- account handles
- import references
- URL-safe record codes
- support references
- compact internal identifiers

Generating a random string is easy.

Making identifier behavior consistent across Django admin, APIs, scripts,
factories, background jobs, normal saves, and bulk imports is where the problem
becomes more subtle.

Common problems include:

- duplicate generation logic across models
- assuming a pre-insert `.exists()` check guarantees uniqueness
- forgetting that `bulk_create()` skips `save()`
- silently allowing identifiers to be edited after creation
- inconsistent character sets between models
- retry behavior implemented differently in every importer
- project-specific registries becoming tightly coupled to model names
- models with multiple identifiers being forced into one global pattern
- identifiers that are technically unique but awkward to read or type

`django-identifiers` provides one reusable Django-focused foundation for those
concerns.

It is intentionally small.

It does not try to become a UUID, ULID, slug, natural-key, sequence, or primary
key framework.

---

## Core Principles

### The database is the source of truth

A generated identifier may be checked before insertion:

```python
Model._default_manager.filter(code=candidate).exists()
```

That check is useful because it avoids many ordinary collisions.

It is **not** a concurrency guarantee.

Another worker can insert the same value after the check and before the current
transaction writes its row.

The only authoritative cross-process uniqueness guarantee is the database
constraint:

```python
code = models.CharField(
    max_length=64,
    unique=True,
    blank=True,
)
```

`django-identifiers` is designed around that fact.

### Normal saves and bulk inserts are different workflows

Normal model creation:

```python
obj.save()
```

runs model save behavior.

Bulk creation:

```python
Model.objects.bulk_create(objects)
```

does not call each object's `save()` method.

`AutoIdentifiersMixin` therefore handles normal model lifecycle creation, while
the bulk helpers handle pre-generation and resilient bulk insertion.

### Identifier policy belongs to the model

The package does not ship a global registry containing project model names.

Each consuming model declares its own identifier policy:

```python
AUTO_IDENTIFIERS = {
    "code": {
        "pattern": "aaaaaaaaa",
        "immutable": True,
    },
}
```

A model may manage more than one identifier field, with a different policy for
each field.

---

## Features

- Automatic identifier generation on first Django model save
- Multiple managed identifier fields per model
- Per-field generation patterns
- Per-field fallback lengths
- Optional identifier immutability
- Explicit escape hatches for controlled identifier changes
- Best-effort database collision checks
- Database-backed uniqueness as the final authority
- Retry behavior after `IntegrityError`
- Safe helper for script/factory single-object creation
- Batch identifier generation
- Guaranteed uniqueness within a generated batch
- Optional filtering of identifiers already present in the database
- In-memory assignment for objects destined for `bulk_create()`
- Resilient bulk creation with collision retry
- Recursive splitting of persistently failing bulk batches
- Django default-manager support
- String model references such as `"orders.Order"`
- Pattern literals and readable character sets
- Numeric-only identifier generation
- Fully typed package with `py.typed`
- Strict mypy validation
- 100% statement and branch coverage
- Clean-wheel installation validation

---

## Installation

Install from PyPI:

```bash
python -m pip install django-identifiers
```

With `uv`:

```bash
uv add django-identifiers
```

The package does not own database tables and does not ship migrations.

You do **not** add `django_identifiers` to `INSTALLED_APPS`.

There are no package settings required.

You only import and use the APIs you need.

---

## Quick Start

The most common use case is an automatically generated identifier that should
never change after creation.

```python
from django.db import models
from django_identifiers import AutoIdentifiersMixin


class Product(AutoIdentifiersMixin, models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
    )

    AUTO_IDENTIFIERS = {
        "code": {
            "pattern": "aaaaaaaaa",
            "immutable": True,
        },
    }
```

Create normally:

```python
product = Product(name="Milk")
product.save()

print(product.code)
```

The blank `code` field is populated during the first save.

An identifier using:

```text
aaaaaaaaa
```

contains nine characters chosen from the package's safe lowercase
alphanumeric alphabet.

If a value is supplied explicitly, the mixin preserves it:

```python
product = Product(
    name="Milk",
    code="legacy42",
)
product.save()

assert product.code == "legacy42"
```

The mixin only auto-generates fields that are blank.

---

## Recommended Model Field

For most generated identifiers:

```python
code = models.CharField(
    max_length=64,
    unique=True,
    blank=True,
)
```

Important attributes:

### `unique=True`

Strongly recommended.

The database unique constraint is the final authority for uniqueness and is
required for collision safety across concurrent writers.

### `blank=True`

Allows the field to remain blank before the mixin generates its value.

### `editable=False`

Optional.

Use it when administrators or forms should never manually assign the field:

```python
code = models.CharField(
    max_length=64,
    unique=True,
    blank=True,
    editable=False,
)
```

Whether a field is editable in a form and whether it is immutable after
creation are separate decisions.

---

## Pattern Syntax

Patterns describe how an identifier should be generated.

Supported tokens:

| Token | Meaning |
|---|---|
| `L` | uppercase letter |
| `l` | lowercase letter |
| `N` | digit `2-9` |
| `a` | lowercase letter or digit `2-9` |
| `A` | uppercase letter or digit `2-9` |

The package excludes visually ambiguous characters from generated alphabets.

Uppercase letters exclude:

```text
I L O
```

Lowercase letters exclude:

```text
i l o
```

Numeric generation excludes:

```text
0 1
```

### Examples

```python
"NNNNNN"
```

Example shape:

```text
284735
```

```python
"LNLNLNNNN"
```

Example shape:

```text
A3B7C9284
```

```python
"aaaaaaaaa"
```

Example shape:

```text
r7m2q8v4c
```

```python
"ORD-NNNNNN"
```

Example shape:

```text
ORD-734829
```

Any character that is not a recognized token is emitted literally.

That means prefixes, separators, and other fixed characters may be embedded
directly in the pattern.

---

## Pattern Length

When a pattern is supplied, the effective output length is the length of the
pattern itself.

For example:

```python
AUTO_IDENTIFIERS = {
    "code": {
        "pattern": "ORD-NNNNNN",
    },
}
```

always produces an identifier with the same total length as:

```text
ORD-NNNNNN
```

A separate `length` value is only relevant when no pattern is being used.

---

## Configuring Multiple Identifier Fields

A model may manage multiple fields independently.

```python
from django.db import models
from django_identifiers import AutoIdentifiersMixin


class Order(AutoIdentifiersMixin, models.Model):
    sku = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
    )
    code = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
    )

    AUTO_IDENTIFIERS = {
        "sku": {
            "pattern": "LL-NNNNNN",
            "immutable": True,
        },
        "code": {
            "pattern": "aaaaaaaaa",
            "immutable": False,
        },
    }
```

The two fields do not need to share the same pattern or immutability policy.

This is useful when one model needs, for example:

- a permanent external reference; and
- a mutable application-facing handle.

---

## Automatic Generation with `AutoIdentifiersMixin`

`AutoIdentifiersMixin` is an abstract Django model mixin.

Use it before `models.Model` or another concrete Django model base:

```python
class Product(AutoIdentifiersMixin, models.Model):
    ...
```

The mixin detects creation using Django's model state:

```python
self._state.adding
```

This is more reliable than checking whether `pk` is `None`, because some models
may receive primary keys before their first database save.

### Creation behavior

On the first save:

1. the mixin reads `AUTO_IDENTIFIERS`;
2. it identifies managed fields whose current value is blank;
3. it generates a value for each blank managed field;
4. it attempts the save inside `transaction.atomic()`;
5. if an `IntegrityError` occurs, generated fields are regenerated and the save
   is retried;
6. after the configured retry count, a final save is attempted and any
   persistent `IntegrityError` is allowed to propagate.

Explicitly supplied identifier values are never replaced automatically.

### Retry count

The default create retry count is:

```python
AUTO_IDENTIFIER_MAX_RETRIES = 3
```

Override it on a model when needed:

```python
class HighTrafficModel(AutoIdentifiersMixin, models.Model):
    AUTO_IDENTIFIER_MAX_RETRIES = 5

    # ...
```

Retries are a collision-recovery mechanism.

If collisions become common, increase the identifier keyspace rather than
relying on large retry counts.

---

## Identifier Immutability

Identifiers may be marked immutable:

```python
AUTO_IDENTIFIERS = {
    "code": {
        "pattern": "aaaaaaaaa",
        "immutable": True,
    },
}
```

After creation:

```python
obj.code = "different"
obj.save()
```

raises:

```text
ValueError
```

The database value remains unchanged.

This protects stable application references from accidental edits.

### Allow one intentional change

A controlled operation may explicitly allow a specific identifier field to
change:

```python
obj.code = "replacement"
obj.save(_allow_code_change=True)
```

The escape-hatch keyword follows this pattern:

```text
_allow_<field_name>_change
```

Examples:

```python
_allow_code_change=True
_allow_sku_change=True
_allow_reference_change=True
```

### Allow all identifier changes for one save

A controlled maintenance operation may allow every immutable identifier on the
model to change:

```python
obj.save(_allow_identifier_change=True)
```

These flags apply only to that save call.

They are deliberately explicit so ordinary model updates cannot silently mutate
stable identifiers.

---

## Direct Identifier Generation

You do not have to use the model mixin.

### `generate_identifier()`

Generate an identifier without a model:

```python
from django_identifiers import generate_identifier


code = generate_identifier(
    pattern="LNLNLNNNN",
)
```

Or generate using a simple length:

```python
code = generate_identifier(
    length=10,
)
```

When no pattern is supplied, the default generator uses safe uppercase letters
and digits.

### Generate for a model field

```python
code = generate_identifier(
    model_class=Product,
    field_name="code",
)
```

When a model is supplied:

1. the field's `AUTO_IDENTIFIERS` configuration is considered;
2. candidates are generated using the resolved policy;
3. existing database values are checked before a candidate is returned.

The existence check reduces ordinary collisions but does not replace the
database unique constraint.

### String model references

A model may also be referenced using Django's normal app-label syntax:

```python
code = generate_identifier(
    model_class="orders.Order",
    field_name="code",
)
```

This is resolved through Django's application registry.

Use this only after Django has been initialized.

---

## Random String Generation

The low-level generator is public:

```python
from django_identifiers import generate_random_string
```

Pattern-based:

```python
value = generate_random_string("LL-NNNN")
```

Length-based:

```python
value = generate_random_string(length=12)
```

This helper does not query the database.

Use it when you only need generation mechanics and do not need model-aware
collision checking.

---

## Numeric Identifiers

### `generate_random_number()`

Generate a numeric string using digits `2-9`:

```python
from django_identifiers import generate_random_number


number = generate_random_number(8)
```

Example:

```text
78245329
```

The value is returned as a string.

That preserves leading-width semantics and avoids converting an application
identifier into arithmetic data.

### `generate_number()`

Generate a numeric identifier with optional model-aware collision checking:

```python
from django_identifiers import generate_number


number = generate_number(
    length=8,
    model_class=Invoice,
    field_name="reference_number",
)
```

Without a model:

```python
number = generate_number(length=8)
```

Both numeric helpers exclude `0` and `1`.

---

## Single-Object Script and Factory Creation

Use `safe_generate_identifier()` when a script, factory, command, or job owns
the actual save operation and is not relying on `AutoIdentifiersMixin`.

```python
from django_identifiers import safe_generate_identifier


order = Order(
    customer=customer,
)

code = safe_generate_identifier(
    order,
    field_name="code",
)
```

The helper:

1. generates a candidate;
2. assigns it to the instance;
3. saves inside `transaction.atomic()`;
4. retries when an `IntegrityError` occurs;
5. returns the successfully saved identifier.

The default attempt count is:

```python
max_attempts=5
```

Customize it:

```python
safe_generate_identifier(
    order,
    field_name="code",
    max_attempts=8,
)
```

If all attempts fail, the helper raises:

```python
IdentifierGenerationError
```

### When not to use it

If the model already uses `AutoIdentifiersMixin` and the field is configured in
`AUTO_IDENTIFIERS`, a normal:

```python
obj.save()
```

already owns automatic generation and retry behavior.

Do not wrap every normal save in `safe_generate_identifier()` unnecessarily.

---

## Bulk Creation

Bulk creation is a major reason this package exists.

Django's:

```python
Model.objects.bulk_create(objects)
```

does **not** call each object's `save()` method.

Therefore:

```python
AutoIdentifiersMixin
```

does not run for those rows.

For bulk workflows, use the package's bulk APIs.

---

## Recommended Bulk Workflow

The simplest complete workflow is:

```python
from django_identifiers import bulk_create_with_identifiers


objects = [
    Product(name="Milk"),
    Product(name="Bread"),
    Product(name="Coffee"),
]

created = bulk_create_with_identifiers(
    model_class=Product,
    instances=objects,
    field_name="code",
)
```

The helper:

1. finds objects whose target identifier field is blank;
2. generates unique candidates in memory;
3. optionally filters candidates already present in the database;
4. inserts objects in batches;
5. catches `IntegrityError`;
6. regenerates identifiers for the failed batch;
7. retries the insert;
8. recursively splits persistently failing multi-row batches;
9. ultimately allows a persistent single-row `IntegrityError` to propagate.

The return value is the number of created objects:

```python
created = bulk_create_with_identifiers(...)
```

---

## Bulk Batch Size

The default batch size is:

```python
batch_size=1000
```

Customize it:

```python
bulk_create_with_identifiers(
    model_class=Product,
    instances=objects,
    field_name="code",
    batch_size=500,
)
```

A useful starting range for many applications is:

```text
500-1000
```

Larger batches reduce insertion overhead but increase the amount of work that
must be retried when one row causes the batch to fail.

Choose the size based on:

- database backend
- row width
- expected import volume
- identifier collision probability
- other model constraints
- transaction characteristics

---

## Bulk Retry Behavior

The default retry count per chunk is:

```python
max_retries=5
```

Override it:

```python
bulk_create_with_identifiers(
    model_class=Product,
    instances=objects,
    max_retries=3,
)
```

When a bulk insert raises `IntegrityError`, identifiers in the failed chunk are
regenerated and the entire chunk is retried.

If the configured retry limit is reached and the chunk contains multiple rows,
the chunk is split in half and each half is attempted independently.

Conceptually:

```text
1000-row chunk fails
        │
        ▼
regenerate + retry
        │
        ▼
retry limit reached
        │
        ├── 500 rows
        │      ├── 250
        │      └── 250
        │
        └── 500 rows
               ├── 250
               └── 250
```

This allows persistent non-identifier integrity failures to be isolated to
smaller groups and ultimately to a single row.

A persistent single-row `IntegrityError` is not hidden.

It propagates to the caller.

---

## Pre-Assign Identifiers Without Writing

If you want to manage `bulk_create()` yourself, use
`assign_missing_identifiers()`.

```python
from django_identifiers import assign_missing_identifiers


objects = [
    Product(name="Milk"),
    Product(name="Bread"),
]

assign_missing_identifiers(
    model_class=Product,
    instances=objects,
    field_name="code",
)

Product.objects.bulk_create(
    objects,
    batch_size=1000,
)
```

`assign_missing_identifiers()` performs no writes.

It only modifies the model instances in memory.

Existing values are preserved:

```python
objects = [
    Product(name="Milk", code="existing"),
    Product(name="Bread", code=""),
]
```

After assignment:

```text
Milk   → existing
Bread  → generated identifier
```

### Concurrency warning

This two-step workflow does **not** provide collision retry around your own
subsequent `bulk_create()`.

If multiple workers may insert concurrently and you want package-managed
recovery, prefer:

```python
bulk_create_with_identifiers(...)
```

---

## Generate a Batch Without Assigning It

Use `generate_identifiers_batch()` when you need the generated values directly.

```python
from django_identifiers import generate_identifiers_batch


codes = generate_identifiers_batch(
    model_class=Product,
    count=1000,
    field_name="code",
)
```

The function guarantees that returned values are unique **within that returned
batch**.

By default it also filters values already present in the database.

### Disable database checking

For workflows where no database check is needed:

```python
codes = generate_identifiers_batch(
    model_class=Product,
    count=1000,
    field_name="code",
    db_check=False,
)
```

This removes the best-effort existing-value query.

It does not change the fundamental concurrency rule: only a database unique
constraint can globally guarantee uniqueness.

### Generation rounds

Batch generation over-generates candidates to absorb duplicates and filters.

The default maximum number of generation rounds is:

```python
max_rounds=10
```

If the function cannot produce enough unique candidates within that limit, it
raises:

```python
IdentifierGenerationError
```

Repeated exhaustion usually indicates that the configured identifier keyspace
is too small for the requested volume.

---

## Concurrency

`django-identifiers` is designed for multiple writers.

Consider two workers:

```text
Worker A                     Worker B
--------                     --------
generate abc123              generate abc123
DB pre-check: free           DB pre-check: free
insert abc123                insert abc123
success                      unique constraint fails
                             regenerate
                             retry
```

Both workers were correct when they performed their pre-check.

The race occurred afterward.

This is why the database constraint is authoritative.

The package's retry behavior is designed to recover from these collisions.

### Recommended concurrent-write model

For normal saves:

```text
AutoIdentifiersMixin
+
unique=True
+
retry on IntegrityError
```

For bulk writers:

```text
bulk_create_with_identifiers()
+
unique=True
+
retry on IntegrityError
```

No centralized reservation service is required for ordinary workloads.

---

## Choosing Identifier Length

Collision probability depends on the number of possible identifiers in the
configured keyspace.

Longer identifiers provide more space.

Shorter identifiers are easier to display and type.

The right balance depends on table size and write volume.

General guidance:

- very small datasets may comfortably use 6-character identifiers;
- general application identifiers often benefit from 8-10 characters;
- high-volume or long-lived tables should use larger keyspaces;
- heavy concurrent creation benefits from additional keyspace;
- if retries become routine, increase the keyspace.

Do not solve frequent collisions by simply increasing retry counts.

Frequent collisions indicate that generation space is too constrained.

---

## Readability Versus Meaning

`django-identifiers` generates **opaque application identifiers**.

The package deliberately avoids visually confusing characters, which improves
readability and manual transcription.

That does not make generated identifiers semantically meaningful.

For example:

```text
r7m2q8v4c
```

is easier to read than an alphabet that freely mixes ambiguous characters, but
the value itself carries no business meaning.

If your identifier must encode business information, dates, regions, sequence
numbers, or other semantics, design that policy deliberately rather than
treating random-generation patterns as an encoding framework.

---

## Identifiers in URLs

Generated identifiers can be useful in URLs:

```python
path(
    "products/<str:code>/",
    views.product_detail,
    name="product-detail",
)
```

Lookup:

```python
product = get_object_or_404(
    Product,
    code=code,
)
```

When using identifiers publicly:

- choose sufficient keyspace;
- keep the database unique constraint;
- do not treat obscurity as authorization;
- continue to enforce normal application permissions;
- do not assume a random-looking identifier is secret.

An identifier is a reference, not an access-control mechanism.

---

## Identifier Configuration Reference

The primary model configuration is:

```python
AUTO_IDENTIFIERS
```

Example:

```python
AUTO_IDENTIFIERS = {
    "code": {
        "pattern": "aaaaaaaaa",
        "immutable": True,
    },
}
```

Supported field options:

### `pattern`

Example:

```python
"pattern": "LNLNLNNNN"
```

Defines the generation pattern.

### `length`

Example:

```python
"length": 10
```

Used when no pattern is configured.

Example:

```python
AUTO_IDENTIFIERS = {
    "code": {
        "length": 10,
        "immutable": True,
    },
}
```

### `immutable`

Example:

```python
"immutable": True
```

Prevents normal changes to the field after creation.

Default behavior when omitted is mutable:

```python
"immutable": False
```

---

## Configuration Precedence

When `generate_identifier()` is used with a model field, per-field model
configuration takes precedence over fallback arguments supplied to the function.

For example:

```python
class Product(AutoIdentifiersMixin, models.Model):
    code = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
    )

    AUTO_IDENTIFIERS = {
        "code": {
            "pattern": "NNNNNN",
        },
    }
```

Then:

```python
generate_identifier(
    model_class=Product,
    field_name="code",
    pattern="LLLLLL",
)
```

uses the model field's configured:

```text
NNNNNN
```

policy.

The model owns its declared identifier policy.

Function arguments act as fallbacks.

---

## Database Managers

`django-identifiers` uses Django's default manager rather than assuming every
model exposes a manager named:

```python
objects
```

This means custom manager naming is supported as long as Django has a valid
default manager for the model.

The package internally works through:

```python
Model._default_manager
```

Consuming applications do not need to access this private Django attribute
themselves.

---

## Transactions

Single-object safe generation and automatic create retries use:

```python
transaction.atomic()
```

Bulk insertion retries also isolate writes inside atomic blocks.

This is important because a failed database write must be rolled back before a
new candidate can be attempted safely.

Your application may still wrap higher-level workflows in its own transactions
when appropriate.

---

## IntegrityError Semantics

Identifier collision recovery is triggered by Django's:

```python
IntegrityError
```

A database may raise `IntegrityError` for reasons other than identifier
collisions, such as:

- another unique constraint
- a check constraint
- a foreign-key constraint
- another database integrity rule

The package does not attempt to parse backend-specific database error strings to
determine which constraint failed.

For single-object retry flows, an unrelated persistent integrity error will
continue to fail and eventually propagate or produce generation exhaustion
according to the API being used.

For resilient bulk creation, persistently failing chunks are recursively split
until a single-row failure can propagate.

This behavior keeps the package backend-independent.

---

## Public Python API

The supported root-package API is:

```python
from django_identifiers import (
    AutoIdentifiersMixin,
    IdentifierGenerationError,
    assign_missing_identifiers,
    bulk_create_with_identifiers,
    generate_identifier,
    generate_identifiers_batch,
    generate_number,
    generate_random_number,
    generate_random_string,
    safe_generate_identifier,
)
```

### `AutoIdentifiersMixin`

Automatic generation and optional immutability for normal Django model saves.

### `IdentifierGenerationError`

Raised when generation cannot produce the required identifier or identifiers
within the configured limits.

### `generate_identifier`

Generate a pattern- or length-based identifier, optionally with model-aware
database checking.

### `generate_random_string`

Low-level random string generation without database access.

### `generate_random_number`

Low-level numeric string generation using digits `2-9`.

### `generate_number`

Numeric identifier generation with optional model-aware database checking.

### `safe_generate_identifier`

Generate, assign, save, and retry a single model instance.

### `generate_identifiers_batch`

Generate many unique identifier candidates efficiently.

### `assign_missing_identifiers`

Assign generated identifiers to blank fields in memory without writing.

### `bulk_create_with_identifiers`

Assign identifiers and perform resilient bulk creation.

Implementation helpers outside the root public API should be treated as
internal.

---

## Import Behavior

The root package can be imported without configured Django settings:

```python
import django_identifiers
```

The Django-model-dependent:

```python
AutoIdentifiersMixin
```

is exposed lazily.

Normal Django projects may simply write:

```python
from django_identifiers import AutoIdentifiersMixin
```

after Django has been configured in the usual way.

This keeps package metadata and installation checks importable without requiring
an initialized Django application registry.

---

## What django-identifiers Does Not Do

`django-identifiers` intentionally does not:

- replace Django primary keys
- provide sequential business numbering
- provide database sequences
- provide UUID generation
- provide ULID generation
- replace slugs
- create natural keys
- encode business semantics into identifiers
- provide authorization
- treat identifiers as secrets
- require a specific user model
- require Django REST Framework
- require django-allauth
- require Celery
- require Redis
- require PostgreSQL
- own application models
- ship database migrations
- maintain a project-specific global model registry

For sequential identifiers, use a database sequence or another mechanism
designed for ordering.

For user-entered natural identifiers such as email addresses, use the domain
model's own validation and uniqueness rules.

---

## When to Use django-identifiers

Good use cases include:

```text
Product.code
Order.code
Document.reference
ImportBatch.code
SupportCase.reference
Account.public_code
Asset.sku
```

The package is especially useful when:

- the identifier should be generated automatically;
- the value should be shorter than a UUID;
- multiple processes may create rows;
- imports rely on `bulk_create()`;
- some identifiers should become immutable after creation;
- the same behavior should be shared across multiple Django projects.

---

## When Not to Use django-identifiers

Do not use this package merely because a model needs some unique field.

It is usually not appropriate for:

### Primary keys

Django and the database already provide primary-key mechanisms.

### Natural keys

Examples:

```text
email address
government-assigned identifier
externally supplied account number
```

These values come from the domain, not from random generation.

### Sequential numbering

If the business requires:

```text
INV-000001
INV-000002
INV-000003
```

use a sequence-oriented system.

Random collision-resistant identifiers do not provide ordering or
gap-free numbering.

### Secrets

Identifiers are not credentials.

Do not use them as password-reset tokens, authentication tokens, API secrets,
or authorization controls.

Use purpose-built cryptographic token systems for those workflows.

---

## Practical Model Example

```python
"""
orders/models.py

Order models.
"""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django_identifiers import AutoIdentifiersMixin


class Order(AutoIdentifiersMixin, models.Model):
    code = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        editable=False,
    )

    AUTO_IDENTIFIERS: ClassVar[dict[str, dict[str, object]]] = {
        "code": {
            "pattern": "ORD-NNNNNNNN",
            "immutable": True,
        },
    }
```

Normal creation:

```python
order = Order()
order.save()

print(order.code)
```

Example:

```text
ORD-57283462
```

The value is generated once and protected from accidental mutation.

---

## Practical Bulk Import Example

Suppose an importer builds 50,000 rows:

```python
objects = [
    ImportedRecord(
        source_id=row.source_id,
        amount=row.amount,
    )
    for row in source_rows
]
```

Use:

```python
from django_identifiers import bulk_create_with_identifiers


created = bulk_create_with_identifiers(
    model_class=ImportedRecord,
    instances=objects,
    field_name="code",
    batch_size=1000,
    max_retries=5,
)
```

The importer does not need to manually reproduce identifier-generation policy.

The model may own that policy:

```python
AUTO_IDENTIFIERS = {
    "code": {
        "pattern": "aaaaaaaaaa",
        "immutable": True,
    },
}
```

Both normal saves and bulk helpers therefore use the same model-level
identifier pattern.

---

## Practical Pre-Assignment Example

Sometimes an import must inspect or serialize generated identifiers before
writing.

```python
from django_identifiers import assign_missing_identifiers


assign_missing_identifiers(
    model_class=ImportedRecord,
    instances=objects,
    field_name="code",
)

for obj in objects:
    print(obj.code)

ImportedRecord.objects.bulk_create(
    objects,
    batch_size=1000,
)
```

Remember that this manual bulk-create pattern does not include automatic retry
around the final write.

Use `bulk_create_with_identifiers()` when package-managed collision recovery is
desired.

---

## Migration from a Project-Local Identifier Utility

A project-local system may previously contain:

```text
core/identifiers/
├── generator.py
├── mixins.py
└── registry.py
```

The recommended migration is:

1. install `django-identifiers`;
2. replace local mixin imports;
3. move model-specific generation policies onto the model;
4. replace global registry entries with `AUTO_IDENTIFIERS`;
5. replace old single-generation helpers with the package API;
6. replace bulk helper imports;
7. keep `unique=True` on generated identifier fields;
8. run application tests and migrations only if the application's model field
   definitions themselves changed;
9. delete the duplicated local identifier implementation after migration.

Example old registry policy:

```python
REGISTERED_CODE_STYLES = {
    "orders.Order": {
        "pattern": "LNLNLNNNN",
    },
}
```

becomes:

```python
class Order(AutoIdentifiersMixin, models.Model):
    AUTO_IDENTIFIERS = {
        "code": {
            "pattern": "LNLNLNNNN",
            "immutable": True,
        },
    }
```

This keeps application policy with the application model while the reusable
generation engine lives in the package.

---

## Supported Versions

| Python | Django 5.2 | Django 6.0 |
|---|---:|---:|
| 3.11 | Yes | No |
| 3.12 | Yes | Yes |
| 3.13 | Yes | Yes |
| 3.14 | Yes | Yes |

Package metadata currently allows:

```text
Python >= 3.11
Django >= 5.2, < 6.1
```

---

## Quality

`django-identifiers` is developed with the same quality standards used across
FIFOA Labs packages.

- Ruff formatting and linting
- Strict mypy validation across source and tests
- `django-stubs`
- Pytest and pytest-django
- 100% statement coverage
- 100% branch coverage
- CI across supported Python and Django combinations
- Django system checks
- Source and wheel distribution validation
- Required `py.typed` wheel-content validation
- Clean-wheel installation testing
- Root-package import smoke testing
- Typed distribution via `py.typed`
- PyPI Trusted Publishing

---

## Project Status

`django-identifiers` is suitable for integration and real-world use, but its
public API remains pre-1.0 and may continue to evolve as the package is adopted
by additional Django projects.

The initial release establishes:

- pattern-based identifier generation
- safe character alphabets
- numeric identifier generation
- model-aware best-effort collision checks
- automatic model lifecycle generation
- optional identifier immutability
- explicit immutability escape hatches
- single-object generate-and-save retries
- batch generation
- in-memory bulk assignment
- resilient bulk creation
- concurrent-writer collision recovery
- per-field model configuration
- typed public APIs

Semantic versioning is used:

- patch releases fix bugs and documentation and may refine existing behavior;
- minor `0.x` releases may add features or refine pre-1.0 APIs;
- `1.0.0` will mark a stable public compatibility commitment.

See the PyPI badge and `CHANGELOG.md` for the currently released version.

---

## Contributing

Issues and pull requests are welcome.

Before submitting changes, run:

```bash
make check
make coverage
make build
make check-dist
make install-wheel
```

For the full local release validation pipeline:

```bash
make release-check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for project guidelines.

---

## License

`django-identifiers` is released under the MIT License.

See [LICENSE](LICENSE) for the full license text.

---

Built and maintained by [FIFOA Labs](https://github.com/fifoa-labs).
