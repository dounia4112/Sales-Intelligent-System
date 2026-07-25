import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "warehouse" / "warehouse.duckdb"


def load():
    con = duckdb.connect(DB_PATH)
    con.execute('CREATE SCHEMA IF NOT EXISTS marts')

    # ---------------- Dimensions ----------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE marts.dim_customer AS
        SELECT customer_id, customer_name, segment, account_manager,
                payment_terms, street, city, region, primary_contact,
                primary_email, credit_limit, phone
        FROM staging.stg_customer
    """)

    con.execute("""
        CREATE OR REPLACE TABLE marts.dim_product AS
        SELECT product_key, product_code, product_name, brand,
                subcategory, category, unit_price, supplier
        FROM staging.stg_product
    """)

    con.execute("""
        CREATE OR REPLACE TABLE marts.dim_geo AS
        SELECT geo_key, city, region FROM staging.stg_geo
    """)

    con.execute("""
            CREATE OR REPLACE TABLE marts.dim_campaign AS
            SELECT campaign_key, campaign_name,  channel, 
                start_date, end_date, budget
            FROM staging.stg_campaign
        """)

    con.execute("""
        CREATE OR REPLACE TABLE marts.dim_date AS
        WITH bounds AS (
            SELECT MIN(order_date) AS lo, MAX(order_date) AS hi FROM staging.stg_order
        )
        SELECT
            d::DATE AS date,
            EXTRACT(YEAR FROM d) AS year,
            EXTRACT(QUARTER FROM d) AS quarter,
            EXTRACT(MONTH FROM d) AS month,
            STRFTIME(d::DATE, '%Y-%m') AS year_month,
            EXTRACT(DOW FROM d) AS day_of_week
        FROM bounds, generate_series(bounds.lo, bounds.hi, INTERVAL 1 DAY) AS t(d)
    """)


    # ---------------- Facts -----------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE marts.fact_sales AS
        SELECT line_id, order_id, product_key, customer_id,
            ship_to_city_key, bill_to_city_key, order_date,
            quantity, unit_price, cost, discount, line_total, order_channel_code 
        FROM staging.stg_sales
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE marts.fact_inventory AS
        SELECT product_key, date, units
        FROM staging.stg_inventory
    """)

    

    con.execute("""
        CREATE OR REPLACE TABLE marts.fact_campaign_spend AS
        SELECT campaign_key, date, impressions, clicks, spend,
        FROM staging.stg_campaign_spend
    """)

    #----------------------------------------------
    # Fact promotion coverage
    #----------------------------------------------

    con.execute("""
        CREATE OR REPLACE TABLE marts.fact_promotion_coverage AS
        SELECT campaign_key, product_key
        FROM staging.stg_promotion_coverage
    """)

    con.execute("""
        CREATE OR REPLACE TABLE marts.fact_order_process AS
        SELECT order_id, order_date, customer_id,
            ship_date, delivery_date, invoice_date , payment_date
        FROM staging.stg_order_process
    """)

    con.execute("""
        CREATE OR REPLACE TABLE marts.fact_sales_targets AS
        SELECT date, target_revenue
        FROM staging.stg_sales_targets
    """)


    con.close()
    print("Load complete.")



if __name__ == "__main__":
    load()