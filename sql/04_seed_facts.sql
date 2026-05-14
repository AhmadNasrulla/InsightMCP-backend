-- Sales-line + returns + inventory snapshot fact data.
-- Default scale is 250,000 sales lines (fast for laptops). Override via:
--   psql -v sales_rows=2500000 -f 04_seed_facts.sql
-- For full assignment scale, use 2500000.
SET search_path TO retail_dw;

\if :{?sales_rows}
\else
\set sales_rows 250000
\endif

\if :{?inventory_product_limit}
\else
\set inventory_product_limit 200
\endif

-- 7) Main fact table
INSERT INTO fact_sales_line (
    order_id, order_line_number, date_key, product_key, store_key, customer_key,
    promotion_key, payment_method_key, order_timestamp, quantity_sold, unit_price,
    gross_sales_amount, discount_amount, net_sales_amount, cost_amount, profit_amount, tax_amount
)
SELECT
    100000000 + ((gs - 1) / 3) AS order_id,
    (1 + ((gs - 1) % 3))::smallint AS order_line_number,
    dd.date_key,
    dp.product_key,
    rand_keys.store_key,
    rand_keys.customer_key,
    pr.promotion_key,
    rand_keys.payment_method_key,
    dd.full_date + make_interval(hours => rand_keys.hh, mins => rand_keys.mi, secs => rand_keys.ss),
    rand_keys.quantity_sold,
    dp.list_price,
    ROUND((rand_keys.quantity_sold * dp.list_price)::numeric, 2),
    ROUND((rand_keys.quantity_sold * dp.list_price * COALESCE(pr.discount_percent,0) / 100)::numeric, 2),
    ROUND((rand_keys.quantity_sold * dp.list_price * (1 - COALESCE(pr.discount_percent,0) / 100))::numeric, 2),
    ROUND((rand_keys.quantity_sold * dp.standard_cost)::numeric, 2),
    ROUND((rand_keys.quantity_sold * dp.list_price * (1 - COALESCE(pr.discount_percent,0) / 100)
           - rand_keys.quantity_sold * dp.standard_cost)::numeric, 2),
    ROUND((rand_keys.quantity_sold * dp.list_price * 0.05)::numeric, 2)
FROM generate_series(1, :sales_rows) gs
JOIN LATERAL (
    SELECT
        (1 + (random() * 9999)::int)::bigint AS product_key,
        (1 + (random() * 9)::int)::smallint AS store_key,
        (1 + (random() * 99999)::int)::bigint AS customer_key,
        (1 + (random() * 4)::int)::smallint AS payment_method_key,
        (1 + (random() * 4)::int) AS quantity_sold,
        (random() * 1095)::int AS day_offset,
        (random() * 23)::int AS hh,
        (random() * 59)::int AS mi,
        (random() * 59)::int AS ss,
        CASE WHEN random() < 0.35 THEN (1 + (random() * 49)::int) ELSE NULL END AS promotion_key
) rand_keys ON TRUE
JOIN dim_product dp ON dp.product_key = rand_keys.product_key
JOIN dim_date dd ON dd.full_date = DATE '2024-01-01' + rand_keys.day_offset
LEFT JOIN dim_promotion pr ON pr.promotion_key = rand_keys.promotion_key;

-- 8) Returns: ~1% of sales lines
INSERT INTO fact_returns (original_sales_line_id, date_key, product_key, store_key, customer_key, returned_quantity, refund_amount, return_reason)
SELECT
    sales_line_id,
    date_key,
    product_key,
    store_key,
    customer_key,
    1,
    LEAST(net_sales_amount, unit_price),
    (ARRAY['Damaged','Wrong item','Late delivery','Changed mind','Quality issue'])[1 + (sales_line_id % 5)]
FROM fact_sales_line
WHERE sales_line_id % 100 = 0;

-- 9) Inventory daily snapshot for the first N products (N = :inventory_product_limit)
INSERT INTO fact_inventory_daily_snapshot (date_key, product_key, store_key, opening_stock_qty, received_qty, sold_qty, closing_stock_qty, stockout_flag)
SELECT
    dd.date_key,
    dp.product_key,
    ds.store_key,
    100 + (random()*200)::int,
    (random()*50)::int,
    (random()*30)::int,
    GREATEST(0, 100 + (random()*200)::int + (random()*50)::int - (random()*30)::int),
    CASE WHEN random() < 0.03 THEN TRUE ELSE FALSE END
FROM dim_date dd
CROSS JOIN (SELECT product_key FROM dim_product ORDER BY product_key LIMIT :inventory_product_limit) dp
CROSS JOIN dim_store ds;

ANALYZE fact_sales_line;
ANALYZE fact_returns;
ANALYZE fact_inventory_daily_snapshot;
