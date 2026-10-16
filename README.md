# Sales Intelligence System

**[▶ Open the live dashboard](https://dounia4112.github.io/Sales-Intelligent-System/dashboard/html/)**

An end-to-end sales analytics project. Messy operational data comes in as a
23-sheet Excel export. It is cleaned and modelled into a star schema in DuckDB,
exported as Parquet, and turned into a three-page dashboard.

The dashboard answers three questions:

| Page | Question |
|---|---|
| **Revenue Pulse** | Are we hitting the sales plan, and is the margin holding? |
| **Customers & Markets** | Where does revenue come from, and how concentrated is it? |
| **Order to Cash & Campaigns** | How long does a sale take to become cash, and which campaigns cost too much? |

## How it works

```
data/raw/dataset.xlsx            23 sheets: orders, line items, customers, products,
        │                        shipments, invoices, payments, campaigns, targets…
        ▼  etl/extract.py
  DuckDB  raw.*                  every sheet loaded as-is (an untouched landing copy)
        │
        ▼  etl/clean.py
  DuckDB  staging.stg_*          typed, joined, de-duplicated, test rows removed
        │
        ▼  etl/load.py
  DuckDB  marts.dim_* / fact_*   star schema for reporting
        │
        ▼  etl/export_to_parquets.py
data/processed/*.parquet         one file per mart table
        │
        ▼
dashboard/html/index.html        interactive dashboard (also the Power BI source tables)
```

All of the database work happens in one local file, `warehouse/warehouse.duckdb`.
No server is needed.

### 1. Extract: `etl/extract.py`
Reads every sheet of `data/raw/dataset.xlsx` and copies it unchanged into the
`raw` schema. Nothing is fixed at this stage, so any number can be traced back
to the source.

### 2. Clean: `etl/clean.py`
Builds the `staging` schema:
- **Customers:** merges the customer master, addresses, cities, primary contacts and credit limits, and drops `TEST` accounts.
- **Products:** splits `Category|Subcategory` strings, normalises their casing, gives each product a surrogate key and drops test products.
- **Orders:** combines the 2025 and 2026 order sheets into one table.
- **Sales lines:** joins line items to orders, customers, products and ship-to / bill-to cities.
- **Inventory:** unpivots the wide month-per-column sheet into one row per product per month.
- **Campaigns:** removes duplicate rows from the campaign log and splits it into a campaign list and daily spend.
- **Order process:** stitches together order, ship, delivery, invoice and payment dates for each order.
- **Targets:** converts monthly revenue targets into dates.

### 3. Load: `etl/load.py`
Publishes the `marts` star schema:

| Dimensions | Facts |
|---|---|
| `dim_customer`: segment, region, account manager, payment terms, credit limit | `fact_sales`: one row per order line (quantity, price, cost, discount, total) |
| `dim_product`: category, subcategory, brand, supplier | `fact_sales_targets`: monthly revenue target |
| `dim_date`: daily calendar over the order range | `fact_order_process`: order → ship → deliver → invoice → pay dates |
| `dim_geo`: city and region | `fact_campaign_spend`: daily impressions, clicks and spend per campaign |
| `dim_campaign`: channel, dates, budget | `fact_inventory`: monthly units on hand per product |
| | `fact_promotion_coverage`: which products each campaign promoted |

### 4. Export: `etl/export_to_parquets.py`
Writes each `marts` table to `data/processed/<table>.parquet`. Power BI and the
HTML dashboard both read from these files.

## The dashboard

[`dashboard/html/index.html`](dashboard/html/index.html) is a single
self-contained file. It needs no install and no server. Download it and open it
in any browser. The data is embedded in the file, and every number is
calculated in the browser.

- **Filters:** Period (All / 2025 / 2026), Region and Segment update every card on every page.
- **Detail:** hover over a chart, bar or stage to see the exact figures. The account table can be sorted by any column.
- **Layout:** works in light and dark mode, and on phones.

Each page leads with a summary, then gives the detail. One colour convention
runs through every chart:

- **Blue** is the actual value.
- **Grey track** is the plan or target.
- **Red** marks something that needs attention.
- **Teal** and **purple** tell categories apart, such as the leading region or a customer segment.

### What the data shows

- **Targets:** revenue was $526.6K at a 36.9% gross margin, 95.4% of target. It missed target in 19 of 20 months, always by 2–7%. A miss that consistent suggests the targets are set slightly too high.
- **Concentration:** 25 of the 47 active accounts produce 80% of revenue. The top 10 produce 45%.
- **Cash cycle:** it takes 32.6 days on average to go from order to cash, and 67% of that is waiting for payment after the invoice.
- **Payment terms:** prepaid customers pay about 25 days after the invoice, while Net 60 customers pay about 40 days early. The recorded terms don't match real behaviour.
- **Campaigns:** Black Friday clicks cost $1.84, about 7× the median campaign.

### Known data issues

- `line_total` does not subtract `discount`, so revenue may be overstated on discounted lines.
- `dim_date` starts at the first order date (2025-02-07). Targets (from 2025-02-01) and inventory (from 2025-01) start earlier, so a full calendar is needed before relating them in Power BI.
- Order channel codes 10 / 20 / 30 / 40 have no names in the source.
- Three sales lines have no matching product, and appear as *Unassigned*.

## Running the pipeline

The raw Excel file and the DuckDB warehouse are git-ignored. To run the
pipeline, put the source file at `data/raw/dataset.xlsx` first.

```bash
pip install -r requirements.txt
python etl/extract.py
python etl/clean.py
python etl/load.py
python etl/export_to_parquets.py
```

## Repository layout

```
etl/                   extract → clean → load → export scripts
dashboard/html/        the interactive HTML dashboard
data/                  raw and processed data (git-ignored)
warehouse/             DuckDB database file (git-ignored)
requirements.txt
```

## Tech stack

Python · pandas · DuckDB · Parquet · Power BI · HTML / CSS / JavaScript
(hand-drawn SVG charts, no charting library)
