# Document Scope and Vehicle Metadata Design

Documents (manuals) are **not** only dealer-specific. They are scoped by **country**, **brand**, **language**, and **vehicle metadata** (model year, model code, engine, transmission, etc.). Vehicle metadata supports **wildcard matching** so one document can apply to many vehicles (e.g. "all 2017–2019 with model code C**") and search can resolve "my vehicle: 2018 CA2, engine X" to matching documents.

---

## 1. Document scope dimensions

| Dimension   | Description | Example values |
|------------|-------------|----------------|
| **Tenant** | Access control (dealer/brand); who can see the document. | `acme-us`, `europe-dealers` |
| **Country** | Market/region the document applies to. | `US`, `DE`, `JP`, `GB` |
| **Brand** | Manufacturer or brand. | `Toyota`, `Honda`, `Ford` |
| **Language** | Document language. | `en`, `de`, `ja`, `en-US` |
| **Vehicle metadata** | Model year, model code, engine, transmission, etc., with optional **wildcards**. | See below. |

A **document** (logical manual) is uniquely identified within a tenant by scope: e.g. same title but different (country, brand, language, vehicle) = different applicability. Search and listing are filtered by these dimensions plus optional **vehicle context** (user’s current vehicle) for wildcard matching.

---

## 2. Vehicle metadata and wildcards

### 2.1 Attributes (examples)

- **model_year** — e.g. `2018`, or range `2017–2019`, or wildcard `*` (any).
- **model_code** — e.g. `CA1`, `CA2`, `CB1`; or pattern `C**` (any Cxx), `***` (any).
- **engine** — e.g. `2ZR-FE`, or `*` (any / ignore).
- **transmission** — e.g. `CVT`, `6AT`, or `*` (any / ignore).
- **body_type**, **drive**, **market**, etc. — optional; same idea: concrete value or wildcard.

### 2.2 Wildcard rules

- **`*`** (single asterisk) in a field: “any value” / “ignore this attribute” for matching.
- **`**`** (double asterisk) in a **pattern** field (e.g. model code): “any one character” in that position.
  - `C**` → matches `CA1`, `CA2`, `CB1`, `CB2`, etc. (C + any two chars).
  - `**1` → matches `CA1`, `CB1`, etc.
  - `***` → matches any model code (e.g. three chars).
- **Ranges** where applicable (e.g. year):
  - `model_year_min`, `model_year_max` → document applies to years in `[min, max]`.
  - Alternatively a single `model_year` with range syntax in metadata (e.g. `2017-2019`).

So a **document** can declare:

- “Applies to: Country=US, Brand=Toyota, Language=en, Model years 2017–2019, Model code C**, Engine=*, Transmission=*.”

A **user/request** provides **vehicle context**: e.g. country=US, brand=Toyota, language=en, model_year=2018, model_code=CA2, engine=2ZR-FE, transmission=CVT.  
The system finds documents whose scope **matches** this context (country/brand/language exact; year in range; model code `C**` matches `CA2`; engine/transmission `*` match anything).

---

## 3. Matching semantics (summary)

| Document value | User value | Match? |
|----------------|------------|--------|
| `2017` (min/max same) | `2017` | Yes |
| Min=2017, max=2019 | `2018` | Yes |
| Min=2017, max=2019 | `2020` | No |
| `C**` (pattern) | `CA2` | Yes |
| `C**` | `CA12` | Depends on pattern length (e.g. `C**` = C + 2 chars → no for CA12) |
| `***` | `CA1` | Yes (any 3 chars) |
| `*` (any) | `2ZR-FE` | Yes |
| `2ZR-FE` | `2ZR-FE` | Yes |
| `2ZR-FE` | `1NZ-FE` | No |

Pattern rules to implement:

- `*` alone in a field → matches any value.
- Pattern with `*` as “wildcard character”: e.g. `C*` = C + one char; `C**` = C + two chars; `***` = any three chars. (Glob-style: `*` = zero or more chars, or fixed-length `*` = one char—choose one and stick to it. For “model code” often **fixed-length** is used: e.g. 3 chars, so `***` = any, `C**` = C + 2 chars.)

Recommendation: **fixed-length** for model code (e.g. 3 chars). Then:

- `*` in pattern = “any single character”.
- `C**` = C + any + any → matches CA1, CA2, CB1, …
- `***` = any 3-character code.

---

## 4. Data model (proposed)

### 4.1 Option A: Scope and vehicle metadata on Book (or Edition)

Add to **Book** (or **Edition** if different editions can have different applicability):

- **country** — TEXT, nullable (NULL = “any” or “global”).
- **brand** — TEXT, nullable.
- **language** — TEXT, nullable (e.g. ISO 639-1).
- **vehicle_metadata** — JSONB, nullable. Structure per document, e.g.:

```json
{
  "model_year_min": 2017,
  "model_year_max": 2019,
  "model_code_pattern": "C**",
  "engine": "*",
  "transmission": "*"
}
```

- For “any” use `null` or `"*"` or omit key.
- **model_code_pattern**: string with `*` = one-char wildcard; length defines required length (e.g. 3 for `***`).

Indexes: (tenant_id, country, brand, language) and optionally GIN on vehicle_metadata for containment/query.

### 4.2 Option B: Separate document_scope table

- **document_scopes** — id, book_id (or edition_id), country, brand, language, vehicle_metadata JSONB, created_at.
- One document (book/edition) can have **multiple** rows (e.g. one for US 2017–2019 CA*, one for EU same). Search joins to this table and matches by scope + vehicle context.

Use Option B if the same manual logically applies to multiple (country, brand, language, vehicle) combinations with different metadata; use Option A if each book/edition has a single scope.

### 4.3 Qdrant payloads

Add to section/chunk payloads (for filtering and display):

- **country**, **brand**, **language**
- **vehicle_metadata** (same JSONB or a flattened subset, e.g. model_year_min, model_year_max, model_code_pattern)

Search/query: filter by tenant_id + country + brand + language (exact), then by vehicle context (year in range, model code pattern match, engine/transmission match or wildcard). Qdrant filter supports exact match; for range and pattern you either:

- Precompute “applicable vehicle codes” and store list in payload and use MatchAny, or
- Do vehicle filtering in the API after retrieval (tenant + country + brand + language in Qdrant; then in-app filter by vehicle metadata).

---

## 5. API behavior (proposed)

### 5.1 Upload / ingestion

- Request (or tenant config) supplies: **country**, **brand**, **language**, **vehicle_metadata** (model_year_min/max, model_code_pattern, engine, transmission, etc.).
- Stored on Book/Edition (or document_scope) and in Qdrant payloads.

### 5.2 List documents (books/editions)

- Query params: **country**, **brand**, **language**, optional **vehicle_context** (model_year, model_code, engine, transmission).
- Return only documents that match the scope and (if vehicle_context given) the vehicle metadata (range + pattern + wildcards).

### 5.3 Search / query

- Request can include **vehicle_context** (and optionally country, brand, language if not inferred from tenant/session).
- Filter documents to those matching scope + vehicle; then run vector search within that set (e.g. filter by tenant_id, country, brand, language in Qdrant; then post-filter or pre-expand by vehicle pattern).

### 5.4 Wildcard implementation (model code)

- **Pattern**: string of fixed length (e.g. 3), `*` = any character.
- **Match(user_value, pattern)**: len(user_value) == len(pattern) and for each i: pattern[i] == '*' or pattern[i] == user_value[i].
- **Examples**:  
  - Match("CA2", "C**") → True.  
  - Match("CA2", "***") → True.  
  - Match("CA12", "C**") → False (length 4 vs 3).

---

## 6. Implementation phases (suggested)

| Step | Task |
|------|------|
| 1 | Add **country**, **brand**, **language** (nullable) and **vehicle_metadata** (JSONB) to Book or Edition; migration/backfill. |
| 2 | Implement **wildcard match** (e.g. `match_vehicle_context(doc_metadata, user_vehicle)`): year in range, model_code pattern, * = any. |
| 3 | **Upload/ingestion**: accept and store scope + vehicle_metadata; write same into Qdrant payloads. |
| 4 | **List books**: filter by tenant + country + brand + language; optional vehicle_context and filter by match_vehicle_context. |
| 5 | **Search/query**: add optional vehicle_context (and scope) to request; restrict to matching documents (Qdrant filter + in-app vehicle filter or pre-expanded list). |
| 6 | **Docs**: document scope dimensions, vehicle_metadata shape, and wildcard rules for clients. |

---

## 7. Example vehicle_metadata shapes

**Document: “US Toyota Corolla 2017–2019, model code C**, any engine/transmission”**

```json
{
  "model_year_min": 2017,
  "model_year_max": 2019,
  "model_code_pattern": "C**",
  "engine": "*",
  "transmission": "*"
}
```

**Document: “EU Honda Civic 2020, model code 5A1, engine L15B7, any transmission”**

```json
{
  "model_year_min": 2020,
  "model_year_max": 2020,
  "model_code_pattern": "5A1",
  "engine": "L15B7",
  "transmission": "*"
}
```

**User vehicle context (request):** country=US, brand=Toyota, model_year=2018, model_code=CA2, engine=2ZR-FE, transmission=CVT → first document matches (year in range, CA2 matches C**, * matches 2ZR-FE and CVT).

This design keeps documents **country-, brand-, and language-specific** and adds **vehicle-metadata with wildcard matching** so one document can cover many vehicles and search can be “vehicle-specific” when the client supplies context.

---

## 8. Reference implementation (matching only)

- **`src/ingestion/vehicle_metadata.py`** provides:
  - `match_pattern(user_value, pattern)` — fixed-length wildcard (`*` = one char); e.g. `match_pattern("CA2", "C**")` → True.
  - `match_vehicle_context(doc_metadata, user_vehicle)` — returns True if document's vehicle_metadata matches the user's vehicle (year in range, model code pattern, engine/transmission exact or `*`).

Schema and API changes (country, brand, language, vehicle_metadata on Book/Edition; upload/list/search params) are **not** yet implemented; see "Implementation phases" above for the suggested order.
