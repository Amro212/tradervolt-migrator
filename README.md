# TraderVolt Migration Tool

One-off, production-quality migration tool for importing MT5 exports into TraderVolt via REST API.

## Features

- **Safety First**: Requires explicit confirmation flags for production writes
- **Test Mode**: Create entities with `MIG_TEST_` prefix for safe testing in production
- **Discovery**: Fetch existing TraderVolt data before migration
- **Validation**: Check migration plan for errors before applying
- **Verification**: POST + GET read-back to confirm entity creation
- **Sequential Execution**: Respects dependency order between entity types
- **Token Refresh**: Automatic handling of token expiration (~7min expiry)
- **Rate Limiting**: Configurable requests per second with exponential backoff
- **Cleanup**: Delete test entities by prefix

## Installation

```bash
# Clone or copy project
cd meta-migrator

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### Authentication

The tool automatically handles authentication using your TraderVolt credentials. Set these environment variables:

```bash
export TRADERVOLT_EMAIL="your-email@example.com"
export TRADERVOLT_PASSWORD="your-password"
```

**How it works:**
1. On first run, the tool logs in using your credentials
2. Tokens are cached to `out/token.json` (gitignored)
3. On subsequent runs, cached tokens are reused until expired
4. When access token expires (~7 min), it auto-refreshes
5. When refresh token expires (~30 days), it re-logs in automatically

No manual token management required!

### Source Data

Place MT5 export files in `./migration_files/`:
- `Clients.htm` - Client data
- `Accounts.htm` - Trading accounts
- `Orders.htm` - Trade orders
- `Positions.htm` - Open positions
- `symbols.json` - Symbol configuration

## Usage

### Step 1: Discovery

Fetch existing data from TraderVolt to understand current state:

```bash
python migrate.py discover
```

Results saved to `out/discovery/`.

### Step 2: Generate Migration Plan

Parse source files and create a migration plan:

```bash
python migrate.py plan --source ./migration_files
```

Plan saved to `out/migration_plan.json`.

For test mode (entities prefixed with `MIG_TEST_`):

```bash
python migrate.py plan --source ./migration_files --test --limit 1
```

### Step 3: Validate Plan

Check for errors and conflicts:

```bash
python migrate.py validate
```

### Step 4: Apply Migration

#### Test Mode (Safe)

Create a single test entity with `MIG_TEST_` prefix:

```bash
python migrate.py apply --test --limit 1
```

#### Production Mode (CAUTION)

Requires two safety flags:

```bash
python migrate.py apply --apply --i-understand-this-will-write-to-tradervolt
```

You'll also be prompted to type `MIGRATE` to confirm.

### Step 5: Cleanup Test Entities

Remove entities with `MIG_TEST_` prefix:

```bash
# Dry run (see what would be deleted)
python migrate.py cleanup --prefix MIG_TEST_ --dry-run

# Actually delete
python migrate.py cleanup --prefix MIG_TEST_
```

## Migration Order

Entities are migrated in dependency order:

1. **Symbol Groups** → 2. **Symbols** → 3. **Trader Groups** → 4. **Traders** → 5. **Orders** → 6. **Positions** → 7. **Deals**

The tool automatically resolves foreign key references (e.g., `tradersGroupId` for traders).

## Output Files

```
out/
├── discovery/           # Discovery results
│   ├── symbols-groups.json
│   ├── symbols.json
│   └── ...
├── migration_plan.json  # Generated migration plan
└── results/             # Migration results
    ├── mappings.json    # Source ID → TraderVolt ID mappings
    ├── created_entities.json
    └── migration_stats.json
```

## Safety Features

| Feature | Description |
|---------|-------------|
| `--test` | Creates entities with `MIG_TEST_YYYYMMDD_` prefix |
| `--limit N` | Limits to N entities per type |
| `--apply` | Required flag to enable any writes |
| `--i-understand-this-will-write-to-tradervolt` | Additional confirmation |
| Prompt | Type `MIGRATE` to confirm production writes |
| Verification | GET after POST to confirm creation |
| Cleanup | `cleanup` command removes test entities |

## API Rate Limiting

- Default: 1 request per second
- Exponential backoff on 429/5xx errors
- Automatic retry (3 attempts)

## Token Management

The tool fully automates token lifecycle:

1. **Login**: Uses `TRADERVOLT_EMAIL` and `TRADERVOLT_PASSWORD` env vars
2. **Caching**: Tokens saved to `out/token.json` between runs
3. **Refresh**: Auto-refreshes access tokens before expiry (~7 min)
4. **Re-login**: Auto re-logs in if refresh token expires (~30 days)

## Troubleshooting

### Authentication failed

Ensure environment variables are set:
```bash
export TRADERVOLT_EMAIL="your-email@example.com"
export TRADERVOLT_PASSWORD="your-password"
```

### Entity already exists

Use `discover` command to check existing entities, then either:
- Skip duplicates (default behavior)
- Delete existing entities first
- Use test mode with unique prefix

## Project Structure

```
meta-migrator/
├── migrate.py                 # CLI entry point
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── .gitignore
├── migration_files/           # Source data (not in git)
│   ├── Clients.htm
│   ├── Accounts.htm
│   ├── Orders.htm
│   ├── Positions.htm
│   └── symbols.json
├── src/
│   ├── tradervolt_client/
│   │   └── api.py            # TraderVolt API client
│   ├── models/
│   │   └── entities.py       # Data models
│   ├── parsers/
│   │   ├── htm_parser.py     # HTML table parser
│   │   └── json_parser.py    # JSON parser
│   └── commands/
│       ├── discover.py
│       ├── plan.py
│       ├── validate.py
│       ├── apply.py
│       └── cleanup.py
└── out/                       # Output directory (not in git)
```

## License

Internal use only. Not for distribution.
