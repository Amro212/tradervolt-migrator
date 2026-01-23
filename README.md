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

The tool requires a TraderVolt access token. Provide it via:

1. **Environment variable** (preferred):
   ```bash
   export TRADERVOLT_ACCESS_TOKEN="your-token-here"
   ```

2. **token.json file** in project root:
   ```json
   {
     "accessToken": "...",
     "refreshToken": "...",
     "accessTokenExpiresAt": "2025-01-23T12:00:00Z",
     "refreshTokenExpiresAt": "2025-02-23T12:00:00Z"
   }
   ```

3. **migration_files/api_v1_users_login_test.json** (fallback for development)

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

## Token Refresh

Access tokens expire after ~7 minutes. The tool automatically:
- Checks token expiry before each request (with 60s buffer)
- Refreshes using the refresh token
- Refresh tokens valid for ~30 days

## Troubleshooting

### No access token found

Set `TRADERVOLT_ACCESS_TOKEN` environment variable or create `token.json`.

### Token refresh failed

1. Check if refresh token is expired (~30 days)
2. Re-authenticate via TraderVolt login API
3. Save new tokens to `token.json`

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
