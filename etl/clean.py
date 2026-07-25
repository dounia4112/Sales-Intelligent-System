import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "warehouse" / "warehouse.duckdb"


def clean():
    con = duckdb.connect(DB_PATH)
    con.execute('CREATE SCHEMA IF NOT EXISTS staging')

    #----------------------------------------------
    # Customers
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_customer AS
        SELECT
            cm.CustomerID AS customer_id,
            cm.CustomerName AS customer_name,
            cm.Segment AS segment,
            cm.AccountManager AS account_manager,
            cm.PaymentTerms AS payment_terms,
            a.Street AS street,
            a.CityName AS city,
            ci.RegionName AS region,
            cc.ContactName AS primary_contact,
            cc.Email AS primary_email,
            ud.CreditLimit AS credit_limit,
            ud.Phone AS phone
        FROM raw.cust_master cm
        LEFT JOIN raw.address a ON cm.AddressID = a.AddressID
        LEFT JOIN raw.cities ci ON a.CityName = ci.CityName
        LEFT JOIN raw.customer_contacts cc
                ON cm.CustomerID = cc.CustomerID AND cc.IsPrimary = true
        LEFT JOIN raw.user_details ud ON cm.CustomerID = ud.UserID
        WHERE cm.AccountManager != 'TEST'
    """)


    #----------------------------------------------
    # Products
    #----------------------------------------------

    con.execute("""
    CREATE OR REPLACE TABLE staging.stg_product AS
    SELECT
        ROW_NUMBER() OVER (ORDER BY pr.ProductCode) AS product_key,
        pr.ProductCode AS product_code,
        pr.ProductName AS product_name,
        pr.Brand AS brand,
        pr.SubcategoryName AS subcategory,
        sc.category AS category,
        pr.UnitPrice AS unit_price,
        pr.PrimarySupplier AS supplier,
    FROM raw.products pr
    LEFT JOIN (
        SELECT
            UPPER(split_part(CategorySubcategory, '|', 1)[1]) 
                || LOWER(split_part(CategorySubcategory, '|', 1)[2:]) AS category,
            UPPER(split_part(CategorySubcategory, '|', 2)[1]) 
                || LOWER(split_part(CategorySubcategory, '|', 2)[2:]) AS subcategory
        FROM raw.subcategories
    ) AS sc ON pr.SubcategoryName = sc.subcategory
    WHERE pr.Brand IS NOT NULL AND pr.Brand != 'TEST'
""")
    

    #----------------------------------------------
    # Orders
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_order AS
        SELECT
            o.OrderID AS order_id,
            o.CustomerName AS customer_name,
            o.CustomerCity customer_city,
            o.RegionName AS region,
            o.ShipToCity AS ship_to_city,
            o.BillToCity AS bill_to_city,
            CAST(o.OrderDate AS DATE) AS order_date,
            o.OrderChannel AS order_channel_code,
            o.Status AS status,
            o.Priority AS priority,
            CAST(o.OrderTotal AS DOUBLE) AS order_total,
            '2025' AS year
        FROM raw.orders_2025 o
        UNION ALL
        SELECT
            o.OrderID AS order_id,
            o.CustomerName AS customer_name,
            o.CustomerCity customer_city,
            o.RegionName AS region,
            o.ShipToCity AS ship_to_city,
            o.BillToCity AS bill_to_city,
            CAST(o.OrderDate AS DATE) AS order_date,
            o.OrderChannel AS order_channel_code,
            o.Status AS status,
            o.Priority AS priority,
            CAST(o.OrderTotal AS DOUBLE) AS order_total,
            '2026' AS year
        FROM raw.orders_2026 o
    """)

    #----------------------------------------------
    # Geo
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_geo AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY c.CityName) AS geo_key,
            c.CityName AS city,
            c.RegionName AS region
        FROM raw.cities c
    """)

    #----------------------------------------------
    # campaign
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_campaign AS
        SELECT 
            ROW_NUMBER() OVER (ORDER BY temp.CampaignName) AS campaign_key,
            temp.CampaignName AS campaign_name,
            temp.Channel AS channel,
            temp.StartDate AS start_date,
            temp.EndDate AS end_date,
            temp.Budget AS budget
        FROM (  SELECT DISTINCT
                    cl.CampaignName,
                    cl.Channel,
                    cl.StartDate ,
                    cl.EndDate ,
                    cl.Budget
                FROM raw.CAMPAIGN_LOG cl
            ) AS temp
        ORDER BY campaign_key
    """)

    #----------------------------------------------
    # Fact Sales
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_sales AS
        SELECT
            oli.LineID AS line_id,
            oli.OrderID AS order_id,
            pr.product_key,
            cm.customer_id,
            geo.geo_key AS ship_to_city_key,
            geo2.geo_key AS bill_to_city_key,
            o.order_date,
            CAST(oli.Quantity AS INT) AS quantity,
            CAST(oli.UnitPrice AS DOUBLE) AS unit_price,
            CAST(oli.UnitCost AS DOUBLE) AS cost,
            CAST(oli.DiscountPct AS DOUBLE) AS discount,
            CAST(oli.LineTotal AS DOUBLE) AS line_total,
            o.order_channel_code 
        FROM raw.order_line_items oli
        LEFT JOIN staging.stg_order o ON oli.OrderID = o.order_id
        LEFT JOIN staging.stg_customer cm ON o.customer_name = cm.customer_name
        LEFT JOIN staging.stg_product pr ON oli.ProductName = pr.product_name
        LEFT JOIN staging.stg_geo geo ON o.ship_to_city = geo.city
        LEFT JOIN staging.stg_geo geo2 ON o.bill_to_city = geo2.city
    """)


    #----------------------------------------------
    # Fact Inventory
    #----------------------------------------------

    inv_cols = con.execute("DESCRIBE raw.inventory").fetchdf()["column_name"].tolist()
    month_cols = [c for c in inv_cols if c != "ProductName"]
    unpivot_union = " UNION ALL ".join(
        f'SELECT ProductName AS product_name, \'{m}\' AS month, "{m}" AS stock_level FROM raw.inventory'
        for m in month_cols
    )

    con.execute(f"""
        CREATE OR REPLACE TABLE staging.stg_inventory AS
        SELECT 
            pr.product_key,
            CAST(un.month || '-01' AS DATE) AS date,
            un.stock_level AS units
        FROM ({unpivot_union}) AS un
        LEFT JOIN staging.stg_product pr ON pr.product_name = un.product_name
    """)

    #----------------------------------------------
    # Fact campaign Spend
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_campaign_spend AS
        SELECT DISTINCT
            co.campaign_key,
            cl.Date AS date,
            cl.Impressions AS impressions,
            cl.Clicks AS clicks,
            cl.Spend AS spend,
        FROM raw.CAMPAIGN_LOG cl
        LEFT JOIN staging.stg_campaign co ON cl.campaignName = co.campaign_name
    """)

    #----------------------------------------------
    # Fact promotion coverage
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_promotion_coverage AS
        SELECT
            cam.campaign_key,
            pr.product_key
        FROM raw.campaign_skus csk
        LEFT JOIN staging.stg_campaign cam ON csk.CampaignName = cam.campaign_name
        LEFT JOIN staging.stg_product pr ON csk.PromotedSKUs = pr.product_code
    """)


    #----------------------------------------------
    # Fact sorder process
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_order_process AS
        SELECT 
            o.order_id AS order_id,
            CAST(o.order_date AS DATE) AS order_date,
            c.customer_id,
            sh.ShipDate AS ship_date,
            sh.DeliveryDate AS delivery_date,
            inv.InvoiceDate AS invoice_date,
            p.PayDate AS payment_date
        FROM staging.stg_order o
        LEFT JOIN staging.stg_customer c ON o.customer_name = c.customer_name
        LEFT JOIN raw.shipments sh ON o.order_id = sh.OrderID
        LEFT JOIN raw.invoices inv ON o.order_id = inv.OrderID
        LEFT JOIN raw.payments p ON inv.InvoiceID = p.InvoiceID
    """)



    #----------------------------------------------
    # Fact sales targets
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE staging.stg_sales_targets AS
        SELECT 
            CAST(Period || '-01' AS DATE) AS date,
            TargetRevenue AS target_revenue
        FROM raw.sales_targets 
    """)

    con.close()
    print("Clean/staging complete.")



if __name__ == "__main__":
    clean()
