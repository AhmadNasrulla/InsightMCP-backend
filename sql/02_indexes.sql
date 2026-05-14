SET search_path TO retail_dw;

CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON fact_sales_line(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON fact_sales_line(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_store ON fact_sales_line(store_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON fact_sales_line(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_promo ON fact_sales_line(promotion_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_payment ON fact_sales_line(payment_method_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_order_ts ON fact_sales_line(order_timestamp);
CREATE INDEX IF NOT EXISTS idx_product_category_subcategory ON dim_product(category_name, subcategory_name);
CREATE INDEX IF NOT EXISTS idx_store_region_city ON dim_store(region, city);
CREATE INDEX IF NOT EXISTS idx_customer_region_city ON dim_customer(region, city);
CREATE INDEX IF NOT EXISTS idx_inventory_date_store_product ON fact_inventory_daily_snapshot(date_key, store_key, product_key);
CREATE INDEX IF NOT EXISTS idx_returns_date_product ON fact_returns(date_key, product_key);
