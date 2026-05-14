-- Retail data warehouse: Kimball-style star schema
CREATE SCHEMA IF NOT EXISTS retail_dw;
SET search_path TO retail_dw;

DROP TABLE IF EXISTS fact_returns CASCADE;
DROP TABLE IF EXISTS fact_inventory_daily_snapshot CASCADE;
DROP TABLE IF EXISTS fact_sales_line CASCADE;
DROP TABLE IF EXISTS dim_payment_method CASCADE;
DROP TABLE IF EXISTS dim_promotion CASCADE;
DROP TABLE IF EXISTS dim_customer CASCADE;
DROP TABLE IF EXISTS dim_store CASCADE;
DROP TABLE IF EXISTS dim_product CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

CREATE TABLE dim_date (
    date_key              INTEGER PRIMARY KEY,
    full_date             DATE NOT NULL UNIQUE,
    day_of_week           SMALLINT NOT NULL,
    day_name              VARCHAR(10) NOT NULL,
    day_of_month          SMALLINT NOT NULL,
    week_of_year          SMALLINT NOT NULL,
    month_number          SMALLINT NOT NULL,
    month_name            VARCHAR(12) NOT NULL,
    quarter_number        SMALLINT NOT NULL,
    year_number           SMALLINT NOT NULL,
    is_weekend            BOOLEAN NOT NULL,
    fiscal_year           SMALLINT NOT NULL,
    fiscal_quarter        SMALLINT NOT NULL
);

CREATE TABLE dim_product (
    product_key           BIGSERIAL PRIMARY KEY,
    product_code          VARCHAR(30) NOT NULL UNIQUE,
    product_name          VARCHAR(150) NOT NULL,
    category_name         VARCHAR(80) NOT NULL,
    subcategory_name      VARCHAR(80) NOT NULL,
    brand_name            VARCHAR(80) NOT NULL,
    supplier_name         VARCHAR(120) NOT NULL,
    unit_size             VARCHAR(40),
    color                 VARCHAR(40),
    standard_cost         NUMERIC(12,2) NOT NULL,
    list_price            NUMERIC(12,2) NOT NULL,
    launch_date           DATE NOT NULL,
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    effective_start_date  DATE NOT NULL DEFAULT DATE '2024-01-01',
    effective_end_date    DATE,
    current_flag          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE dim_store (
    store_key             SMALLSERIAL PRIMARY KEY,
    store_code            VARCHAR(20) NOT NULL UNIQUE,
    store_name            VARCHAR(120) NOT NULL,
    store_type            VARCHAR(40) NOT NULL,
    city                  VARCHAR(80) NOT NULL,
    region                VARCHAR(80) NOT NULL,
    country               VARCHAR(80) NOT NULL DEFAULT 'Pakistan',
    opening_date          DATE NOT NULL,
    manager_name          VARCHAR(100),
    floor_area_sqft       INTEGER
);

CREATE TABLE dim_customer (
    customer_key          BIGSERIAL PRIMARY KEY,
    customer_code         VARCHAR(30) NOT NULL UNIQUE,
    full_name             VARCHAR(120) NOT NULL,
    gender                VARCHAR(20),
    age_band              VARCHAR(20),
    city                  VARCHAR(80),
    region                VARCHAR(80),
    loyalty_tier          VARCHAR(30),
    registration_date     DATE NOT NULL,
    email_hash            VARCHAR(80),
    phone_hash            VARCHAR(80),
    current_flag          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE dim_promotion (
    promotion_key         SERIAL PRIMARY KEY,
    promotion_code        VARCHAR(30) NOT NULL UNIQUE,
    promotion_name        VARCHAR(120) NOT NULL,
    promotion_type        VARCHAR(40) NOT NULL,
    channel               VARCHAR(40) NOT NULL,
    discount_percent      NUMERIC(5,2) NOT NULL,
    start_date            DATE NOT NULL,
    end_date              DATE NOT NULL
);

CREATE TABLE dim_payment_method (
    payment_method_key    SMALLSERIAL PRIMARY KEY,
    payment_method_code   VARCHAR(20) NOT NULL UNIQUE,
    payment_method_name   VARCHAR(60) NOT NULL,
    payment_provider      VARCHAR(80),
    is_digital            BOOLEAN NOT NULL
);

CREATE TABLE fact_sales_line (
    sales_line_id         BIGSERIAL PRIMARY KEY,
    order_id              BIGINT NOT NULL,
    order_line_number     SMALLINT NOT NULL,
    date_key              INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key           BIGINT NOT NULL REFERENCES dim_product(product_key),
    store_key             SMALLINT NOT NULL REFERENCES dim_store(store_key),
    customer_key          BIGINT NOT NULL REFERENCES dim_customer(customer_key),
    promotion_key         INTEGER REFERENCES dim_promotion(promotion_key),
    payment_method_key    SMALLINT NOT NULL REFERENCES dim_payment_method(payment_method_key),
    order_timestamp       TIMESTAMP NOT NULL,
    quantity_sold         INTEGER NOT NULL CHECK (quantity_sold > 0),
    unit_price            NUMERIC(12,2) NOT NULL,
    gross_sales_amount    NUMERIC(14,2) NOT NULL,
    discount_amount       NUMERIC(14,2) NOT NULL DEFAULT 0,
    net_sales_amount      NUMERIC(14,2) NOT NULL,
    cost_amount           NUMERIC(14,2) NOT NULL,
    profit_amount         NUMERIC(14,2) NOT NULL,
    tax_amount            NUMERIC(14,2) NOT NULL DEFAULT 0,
    load_batch_id         INTEGER NOT NULL DEFAULT 1,
    created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(order_id, order_line_number)
);

CREATE TABLE fact_inventory_daily_snapshot (
    inventory_snapshot_id BIGSERIAL PRIMARY KEY,
    date_key              INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key           BIGINT NOT NULL REFERENCES dim_product(product_key),
    store_key             SMALLINT NOT NULL REFERENCES dim_store(store_key),
    opening_stock_qty     INTEGER NOT NULL,
    received_qty          INTEGER NOT NULL DEFAULT 0,
    sold_qty              INTEGER NOT NULL DEFAULT 0,
    closing_stock_qty     INTEGER NOT NULL,
    stockout_flag         BOOLEAN NOT NULL,
    UNIQUE(date_key, product_key, store_key)
);

CREATE TABLE fact_returns (
    return_id             BIGSERIAL PRIMARY KEY,
    original_sales_line_id BIGINT REFERENCES fact_sales_line(sales_line_id),
    date_key              INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key           BIGINT NOT NULL REFERENCES dim_product(product_key),
    store_key             SMALLINT NOT NULL REFERENCES dim_store(store_key),
    customer_key          BIGINT NOT NULL REFERENCES dim_customer(customer_key),
    returned_quantity     INTEGER NOT NULL CHECK (returned_quantity > 0),
    refund_amount         NUMERIC(14,2) NOT NULL,
    return_reason         VARCHAR(100) NOT NULL
);

COMMENT ON TABLE fact_sales_line IS 'Atomic transaction fact: one row per product line sold in one order at one store to one customer on one timestamp.';
COMMENT ON TABLE fact_inventory_daily_snapshot IS 'Periodic snapshot fact: one row per product per store per day.';
COMMENT ON TABLE fact_returns IS 'Transaction fact: returned product lines referencing the original sale.';
COMMENT ON TABLE dim_product IS 'Product dimension with denormalized category/subcategory hierarchy.';
