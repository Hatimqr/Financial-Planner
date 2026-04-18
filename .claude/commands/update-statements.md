---
description: Generate/update monthly statement JSON files from a bank statement PDF
argument-hint: <path-to-pdf>
---

# Update Statement JSONs

Parse the bank statement PDF at `$ARGUMENTS` and sync the monthly JSON files in `data/statements/`. Create missing months, append missing transactions to existing months, update closing balances.

## Process

### 1. Read the PDF
Use the Read tool on the provided PDF path. If the argument is empty, stop and ask the user for a path.

### 2. Extract every transaction row
For each row in the statement table, capture:
- **Value Date** → `date` (format `YYYY-MM-DD`, year inferred from statement period in header)
- **Description** column → raw text (keep as `original_description`)
- **Ref/Cheque No** → `reference`
- **Debit Amount** → if present, transaction `amount` is **negative** of that value
- **Credit Amount** → if present, transaction `amount` is **positive** of that value
- **Balance** (running balance) — needed to derive per-month opening/closing

Ignore the Posting Date column for the `date` field; use Value Date only (this matches the existing JSON convention in `dec.json` and `jan.json`).

### 3. Group by value-date month
Bucket transactions by `YYYY-MM`. Keep them in PDF chronological order (oldest → newest) within each month.

### 4. Per-month opening/closing balance
Opening balance for month M = running balance right **before** the first value-date-M transaction. Closing = running balance **after** the last value-date-M transaction. Be careful: the PDF is sorted by posting-date desc, so value-date ordering differs — reconstruct by following the running balance column.

### 5. For each month, determine the filename
3-letter month abbreviations, lowercase: `jan.json`, `feb.json`, `mar.json`, `apr.json`, `may.json`, `jun.json`, `jul.json`, `aug.json`, `sep.json`, `oct.json`, `nov.json`, `dec.json`. Write to `data/statements/<abbrev>.json`.

### 6. Merge with existing JSON (if present)

Read the existing file if it exists. A PDF transaction is considered **already present** in the JSON if there's a JSON entry with the **same `reference`** (the reference number from the PDF is the primary key). For entries with ref `000000` (refunds) or missing refs, fall back to matching on `date` + `original_description` + `amount`.

- **Existing file**: append only new transactions (keep old ones untouched). Update `closing_balance` to the new post-last-txn balance. Update `statement_period.to` to cover the new range.
- **New file**: create with full header, all transactions.

Never re-order or re-categorize existing entries — the user may have edited them.

### 7. Transaction JSON schema (per entry)

```json
{
  "date": "YYYY-MM-DD",
  "description": "Clean human-readable",
  "payee": "Merchant name",
  "amount": "<signed, 2 decimals, negative=debit>",
  "reference": "<ref from PDF, with PHUB prefix for transfers>",
  "original_description": "<raw PDF description verbatim>",
  "foreign_currency_note": "<'100.0 USD' or '2000.0 LKR' etc, '' if AED>",
  "postings": [
    { "account": "<category path>", "amount": "<opposite sign of transaction amount>" }
  ]
}
```

Rules:
- `amount` is signed from the bank's perspective. `postings` amount is the offsetting side (opposite sign).
- For `PHUB*****` refs shown in the Description column (incoming transfers), strip `PHUB` from `original_description` but keep it in `reference`.
- Refunds: description = `Refund - <merchant>`, amount positive, posting amount negative.

### 8. Categorization (match against raw description, case-insensitive)

| Pattern in description | Account |
|---|---|
| `B/O HATIM REHMANJEE` (incoming transfer) | `Equity:Transfers` |
| Initial bank deposit (first-ever B/O before any purchases) | `Equity:Opening Balance` |
| `Transfer to Investment` | `Assets:Investments:Stocks` |
| `NETFLIX` | `Expenses:Entertainment:Subscriptions` |
| `CLAUDE AI`, `OPENAI`, `ANTHROPIC` | `Expenses:Subscriptions:AI` |
| `Dialog Axi` (any telco) | `Expenses:Utilities:Phone` |
| `HIGH OCTAN`, fuel-station-like names | `Expenses:Transport:Fuel` |
| `DURDANS`, `CEYLON HOS`, any `HOSPITAL`/`MEDICAL`/`PHARMACY` | `Expenses:Health:Medical` |
| `LULU HYPER`, `GRANDIOSE`, `LOTUS BAQA`, `CARREFOUR`, `SPINNEYS` | `Expenses:Groceries` |
| `ZARA`, `BERSHKA`, `PULL AND B`, `SUN & SAND`, `SUPERIOR G`, `ADMM LLC`, `Amazon`, `OPEN 25`, clothing/retail | `Expenses:Shopping` |
| Everything else starting with `PUR` (restaurants, cafes, food delivery, TAP*Keeta, MercadoPago, etc) | `Expenses:Food & Dining` |

When a merchant is ambiguous (e.g. `SAADIYAT N`, `Simply Str`, `Buffal qlu`), default to `Expenses:Food & Dining` and note it in the summary report.

### 9. Description/payee cleanup

From a raw `PUR 03/01 973.5 LKR UNCLE'S CO COLOMBO 4874`:
- Strip `PUR DD/MM`, the foreign currency amount, and the trailing card-digits (`4874`).
- `payee` = the merchant key (e.g. `Uncle's Coffee`, expand common abbreviations).
- `description` = `<payee> <location>` (e.g. `Uncle's Coffee Colombo`).
- `foreign_currency_note` = the currency portion if present (`973.5 LKR`), else `""`.

### 10. Write / edit files

- New files: use Write.
- Existing files: use Edit. Make the smallest possible edit — typically (a) one Edit to bump `closing_balance`/`statement_period.to`, and (b) one Edit to insert the new transaction objects before the closing `]` of `transactions`.

### 11. Balance reconciliation check

For each written/updated file, verify: `opening_balance + sum(amount for all transactions) == closing_balance` (tolerance 0.05). If a month fails, DO NOT silently write — flag it in the summary and ask the user.

### 12. Report

End with a concise summary:
- `Created: feb.json (32 txns), mar.json (21 txns)`
- `Updated: jan.json (+3 txns, closing 8766.62 → 8733.12)`
- `Unchanged: dec.json`
- Any merchants that fell through to the default category and are worth user review.
- Any balance-reconciliation warnings.

## Guardrails
- If `$ARGUMENTS` is empty or doesn't point to an existing file, stop and ask.
- Never re-order or mutate existing transaction entries in an existing JSON.
- Never set `closing_balance` to a value that doesn't reconcile with `opening_balance + sum(amounts)`.
- Only read/write files under `data/statements/`.
