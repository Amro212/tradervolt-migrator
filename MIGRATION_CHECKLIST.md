# MT5 → TraderVolt Migration Checklist

## ⚠️ Assumptions Made (Require Confirmation)

### Account Filtering
- [x] **Managers excluded** - 12 accounts (`managers\administrators`, `managers\dealers`) NOT migrated
  - **Question**: Should manager accounts be migrated or are they staff-only?

### Field Mappings
- [x] **`password`** = `"TempPass123!"` (hardcoded placeholder)
  - **Question**: Should we generate random passwords per user? Or let TraderVolt auto-generate?
  - **Security risk**: All users have same temp password until changed

- [x] **`isEnabled`** = `true` (all accounts active by default)
  - **Question**: Should archived/disabled MT5 accounts remain disabled in TraderVolt?

- [x] **`preliminary` group** → `ROOT` group (no direct mapping exists)
  - **Question**: Should preliminary accounts go to REAL or ROOT group?

- [x] **`tradeType`** = Capitalized ("Demo" / "Real")
  - **Question**: Verify API accepts capitalized vs lowercase ("demo" / "real")

- [x] **Empty fields** → `null` (not empty strings)
  - Clean JSON but might affect API validation

- [x] **MT5 metadata** stored in `notes` field as JSON
  - Format: `{"mt5_login": 555962, "mt5_group": "demo\\forex-net-usd-01"}`
  - **Question**: Is this format acceptable or do you need different metadata storage?

### Data Priority
- [x] **Accounts.htm prioritized over Clients.htm** when both have same field
  - Example: If phone exists in both, Accounts.htm value used
  - **Question**: Should Clients.htm data override Accounts.htm for specific fields?

- [x] **`lastName` fallback** - If missing, uses `firstName` as fallback
  - **Question**: Should we reject/skip accounts with missing lastName instead?

### Duplicate Handling
- [x] **Duplicate emails allowed** (e.g., multiple Liam Anderson accounts)
  - Seen: `sumitdravon@gmail.com` appears 4 times
  - **Question**: Should we merge duplicates or create separate TraderVolt accounts?

## 🚨 Critical Questions for Dev Team

### 1. Financial Data Migration
- **Balance, Credit, Equity NOT migrated** (only stored in notes for reference)
- TraderVolt's `financialStatus` object seems read-only (set by system)
- **Question**: How do we set initial balances? Separate API call? Manual adjustment?

### 2. Orders & Positions Migration
- **Not yet implemented** - Only traders created so far
- Parsed and ready: 132 orders, 15 positions
- **Questions**:
  - What API endpoint for creating orders/positions?
  - Should we migrate closed orders or only open positions?
  - How to link orders/positions to newly created traders (need TraderVolt trader ID)?

### 3. API Behavior Unknowns
- **Unknown fields**: `password` and `isEnabled` not in discovery data
  - Assumed creation-only fields
  - **Question**: Will API reject unknown fields or ignore them?

- **Required vs Optional**: Don't know which fields are strictly required
  - Assumed: firstName, lastName, email, tradersGroupId, tradeType
  - **Question**: What's the minimum required field set?

### 4. Group Mapping Verification
- Current mapping:
  - `demo\*` → `d3c9f1e8-ec2f-421b-8c3f-57eb5a0c3c9f` (DEMO)
  - `real\*` → `cfd69018-9475-4ed6-a63f-63e6230d0b68` (REAL)
  - `preliminary` → `9c6b651e-bbe6-4b2a-bed3-84aabe05e19b` (ROOT)
- **Question**: Are these group IDs correct? Should all MT5 sub-groups map to same TraderVolt group?

### 5. Testing Strategy
- **No dry-run mode** in TraderVolt API (no "test" flag visible)
- **Question**: 
  - Is there a staging/test environment?
  - Can we test with 1-2 accounts first?
  - How to rollback if migration fails midway?

## ⚠️ Data Quality Concerns

### Missing Data (Null Values)
Based on preview, many traders have null values for:
- `city`, `state`, `postcode`, `street` - Most accounts missing address details
- `birthDate`, `citizenship`, `taxId` - KYC fields mostly empty
- `leadCampaign`, `leadSource` - Marketing attribution missing

**Question**: Is this acceptable or do you need these fields populated?

### Potential Issues
1. **Phone format inconsistency** - Mix of formats: `7896541231`, `+15557654321`, `965221554566`
   - **Question**: Should we normalize to E.164 format (+[country][number])?

2. **Country names** - Free text ("United States", "India", "Afghanistan")
   - **Question**: Does TraderVolt expect ISO country codes (US, IN, AF)?

3. **State field** - Some have numeric values (`"1234"`)
   - **Question**: Is this correct or data corruption?

4. **Duplicate traders with same email** - 4 instances found
   - **Question**: Handle as separate accounts or merge?

## 📋 Pre-Migration Verification Checklist

- [ ] **Confirm manager accounts** - Migrate or exclude?
- [ ] **Set password policy** - Random per user, single temp, or auto-generate?
- [ ] **Verify group mappings** - Correct TraderVolt group IDs?
- [ ] **Test with 1 account** - Verify API accepts payload format
- [ ] **Check required fields** - Confirm minimum field requirements
- [ ] **Decide on duplicates** - Merge or create separate accounts?
- [ ] **Plan balance migration** - How to set initial financialStatus?
- [ ] **Plan orders/positions** - API endpoints and linking strategy?
- [ ] **Staging environment** - Available for testing?
- [ ] **Rollback plan** - How to undo if migration fails?

## 📊 Current Migration State

### Ready to Migrate
- ✅ **29 traders** (23 DEMO, 5 REAL, 1 ROOT)
- ✅ Payload format matches TraderVolt schema (21 fields)
- ✅ All critical fields populated (firstName, lastName, email, phone, country)
- ✅ Preview file: `out/preview/traders_to_create.json`

### Not Yet Implemented
- ⏳ Financial data migration (balance, credit, equity)
- ⏳ Orders migration (132 orders parsed, ready)
- ⏳ Positions migration (15 positions parsed, ready)
- ⏳ Error handling and retry logic
- ⏳ Progress tracking and logging
- ⏳ Rollback capability

### Files Modified
- ✅ `src/parsers/htm_parser.py` - Fixed all parsers (added 40+ fields)
- ✅ `preview_migration.py` - Created comparison tool
- ⏳ `src/models/entities.py` - Needs update for new fields
- ⏳ `src/commands/plan.py` - Needs update for new parser fields
- ⏳ `src/commands/apply.py` - Needs orders/positions migration