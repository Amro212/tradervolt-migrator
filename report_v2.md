# TraderVolt Migration Tool (Files → TraderVolt API) — Build Prompt for LLM Agent

## Role

You are an engineering LLM building a **one-off but production-quality migration tool** that imports trading data into TraderVolt **via the TraderVolt REST API**.

This is **NOT** a sync tool and must **NOT** connect to the old platform’s API. The source data is already exported as files.

## High-level goal

Build a migration tool that:

1. Reads our exported files (HTML/CSV-like exports + JSON)
2. Normalizes/matches entities
3. Validates everything **without writing** (dry-run)
4. Produces a reviewable plan + diffs
5. Only after explicit human approval, performs the write/import into TraderVolt in the required order.

## Critical constraints (must follow)

* **Do not execute or push a real migration by default.**
* Implement a strict **two-phase workflow**:

  1. **Dry-run / Plan** (default): parse + validate + generate a migration plan and sample API payloads, but **NO POST/PUT**.
  2. **Apply**: only runs when user sets an explicit flag like `--apply` and confirms.
* Add an additional guard: `--apply` must also require `--i-understand-this-will-write-to-tradervolt`.
* Prefer **API-first migration** due to validations and relations.
* Import **order is mandatory** due to validations:

  1. Symbol Groups
  2. Symbols
  3. Accounts (Traders) — note: *clients/users will be auto-generated*
  4. Orders
  5. Deals
  6. Positions
* Avoid creating many “comprehensive documents”. Produce only:

  * a short `README.md` with how to run dry-run and apply
  * a `migration_plan.json` / `migration_plan.md`
  * logs + reports
* Ask follow-up questions if anything is unclear.

## Inputs we will provide you

* `Clients.htm` (exported table)
* `Accounts.htm`
* `Orders.htm`
* `Positions.htm`
* (Optional) Deals export (if present)
* `symbols.json`
* `QuorionexMarketsTestOnly-Trade 2.json` (environment/config reference)
* A sample successful login output from `POST /api/v1/users/login` that contains `accessToken`.

## Authentication / API context

* TraderVolt uses **Bearer auth** in Swagger (“Authorize” requires `Bearer {token}`). 
* We will provide an `accessToken`. refer to `migration_files/api_v1_users_login.json` to find the `accessToken`.

### IMPORTANT

Even though we will provide the token, the tool must support:

* Reading token from env: `TRADERVOLT_ACCESS_TOKEN`
* Or from a file: `token.json`

## Playwright MCP requirement

Occasionally use **Playwright MCP** to open:

* `https://api.tradervolt.com/swagger/index.html`

Use it to:

* Confirm request/response schemas for each endpoint you call (GET/POST)
* Confirm required fields and any enum constraints
* Confirm which endpoints exist for symbol groups, symbols, accounts/traders, orders, deals, positions

If a schema is ambiguous, you MUST:

* Ask us a follow-up question
* Or propose a safe assumption and keep it in dry-run mode until confirmed

## Deliverables

### 1) A runnable CLI tool

Language: **Python** (preferred) OR Node.js. Choose one and stick to it.

Must provide commands:

* `migrate.py plan --input-dir ./exports --out ./out`
* `migrate.py validate --plan ./out/migration_plan.json`
* `migrate.py apply --plan ./out/migration_plan.json --i-understand-this-will-write-to-tradervolt`

### 2) Outputs for review

In dry-run/plan mode, generate:

* `./out/migration_plan.json` containing:

  * entity counts per type
  * detected keys and mapping strategy
  * dependency graph (what references what)
  * proposed API calls in order (without executing)
  * sample payloads (first 3 items each type)
* `./out/validation_report.md`:

  * missing required fields
  * mapping failures (symbol not found, account missing, etc.)
  * duplicates
  * stats and warnings
* `./out/mappings.json`:

  * source IDs → deterministic external IDs

### 3) Safety & idempotency

* Every created object must include or be tied to a deterministic **externalId** so reruns do not duplicate.
* If TraderVolt supports upserts, use them. If not, implement:

  * lookup by externalId (GET/filter endpoint)
  * then POST if missing
  * then PUT/PATCH if exists (only if safe)
* Implement rate limiting and retries with exponential backoff.

### 4) A walkthrough of the finished product

When done, provide a short step-by-step walkthrough:

* How to run plan
* How to inspect outputs
* How to test with a tiny subset
* How to apply
* How to verify counts in TraderVolt afterward

## Parsing requirements (source files)

* Our “CSV” exports are often **MT5 HTML table exports** (`.htm`).
* Implement robust parsing:

  * Use BeautifulSoup (Python) to parse tables in `.htm`
  * Also support `.csv` if provided
  * Support `.json` for symbols

Normalize the entities into internal schemas:

* SymbolGroup
* Symbol
* Account/Trader
* Order
* Deal
* Position

## Business rules / expectations

* Clients/users should be **auto-generated when accounts/traders are created** (do not separately create clients unless you discover TraderVolt requires it).
* Validation errors are expected; the tool must:

  * surface them clearly
  * never silently drop rows
  * produce a “failed rows” file per entity type

## API discovery checklist (do this early)

Using Swagger (Playwright MCP) confirm:

* Login endpoint already known: `POST /api/v1/users/login`
* Endpoints for:

  * Symbol Groups (GET/POST/PUT?)
  * Symbols (GET/POST/PUT?)
  * Traders/Accounts (GET/POST/PUT?)
  * Orders (GET/POST/PUT?)
  * Deals (GET/POST/PUT?)
  * Positions (GET/POST/PUT?)
* Whether there are bulk endpoints (batch APIs). If none exist, propose a design but do not implement server changes.

## Testing strategy (must implement)

### Unit tests

* Parsers: `.htm` tables produce correct rows
* Normalizers: convert to internal schema
* Mappers: symbol resolution, account linking

### Integration tests (no writes)

* Use real token but only perform safe GET calls:

  * verify token works
  * fetch existing symbols/groups to detect conflicts

### Smoke test apply (tiny subset)

* Implement `--limit N` and `--filter` flags:

  * e.g. migrate only 1 symbol group + 2 symbols + 1 account + 2 orders
* Apply only that subset first

## Follow-up questions you MUST ask us if unclear

1. Do we have a **staging** TraderVolt environment? If yes, use it first.
2. Do we want to migrate **full history** or a time range only?
3. Should we treat symbol names as exact matches, or do we need a mapping table (suffixes like `.r`, `.m`)?
4. For Accounts/Traders, what is the stable unique key in exports (login/accountId/email)?
5. Are there existing records in TraderVolt already, or is it empty?

## Definition of done

* Dry-run produces a clean plan and validation report with **zero critical errors**.
* A limited subset migration succeeds without duplicates.
* Full migration can be run with `apply` and produces logs + summary counts.

## Implementation notes

* Keep the repo small and focused:

  * `migrate.py` (entry)
  * `parsers/`
  * `tradervolt_client/`
  * `models/`
  * `tests/`
  * `README.md`
* Do not generate excessive documentation.
* Prefer clear logging and readable reports.

---

### Start now

1. Inspect the provided files and infer the source schemas.
2. Use Playwright MCP on Swagger to confirm destination schemas.
3. Ask any follow-up questions.
4. Implement the tool with dry-run default.
