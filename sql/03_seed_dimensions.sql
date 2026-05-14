-- Seed the dimensions (stores, payment methods, promotions, customers, products, dates).
-- Idempotent: clears warehouse data before re-inserting.
SET search_path TO retail_dw;

TRUNCATE TABLE fact_returns, fact_inventory_daily_snapshot, fact_sales_line,
    dim_promotion, dim_payment_method, dim_customer, dim_product, dim_store, dim_date
    RESTART IDENTITY CASCADE;

-- 1) Date dimension: 2024-01-01 .. 2026-12-31
INSERT INTO dim_date (
    date_key, full_date, day_of_week, day_name, day_of_month, week_of_year,
    month_number, month_name, quarter_number, year_number, is_weekend,
    fiscal_year, fiscal_quarter
)
SELECT
    TO_CHAR(d::date, 'YYYYMMDD')::int,
    d::date,
    EXTRACT(ISODOW FROM d)::smallint,
    TRIM(TO_CHAR(d, 'Day')),
    EXTRACT(DAY FROM d)::smallint,
    EXTRACT(WEEK FROM d)::smallint,
    EXTRACT(MONTH FROM d)::smallint,
    TRIM(TO_CHAR(d, 'Month')),
    EXTRACT(QUARTER FROM d)::smallint,
    EXTRACT(YEAR FROM d)::smallint,
    CASE WHEN EXTRACT(ISODOW FROM d) IN (6,7) THEN TRUE ELSE FALSE END,
    CASE WHEN EXTRACT(MONTH FROM d) >= 7
         THEN (EXTRACT(YEAR FROM d) + 1)::smallint
         ELSE EXTRACT(YEAR FROM d)::smallint END,
    (((EXTRACT(MONTH FROM d)::int + 5) % 12) / 3 + 1)::smallint
FROM generate_series(DATE '2024-01-01', DATE '2026-12-31', INTERVAL '1 day') d;

-- 2) Stores
INSERT INTO dim_store (store_code, store_name, store_type, city, region, opening_date, manager_name, floor_area_sqft) VALUES
('STR-001','Lahore Emporium','Mall','Lahore','Punjab','2021-03-15','Ayesha Khan',25000),
('STR-002','Karachi Clifton','High Street','Karachi','Sindh','2020-08-20','Bilal Ahmed',22000),
('STR-003','Islamabad Blue Area','Flagship','Islamabad','Capital','2019-11-05','Sara Malik',30000),
('STR-004','Peshawar Saddar','High Street','Peshawar','KPK','2022-02-01','Hamza Ali',18000),
('STR-005','Quetta Cantt','High Street','Quetta','Balochistan','2022-07-10','Zara Shah',16000),
('STR-006','Faisalabad D-Ground','Mall','Faisalabad','Punjab','2021-12-12','Usman Raza',21000),
('STR-007','Multan Gulgasht','High Street','Multan','Punjab','2023-01-20','Hina Noor',17000),
('STR-008','Hyderabad Latifabad','High Street','Hyderabad','Sindh','2023-05-25','Kashif Memon',16500),
('STR-009','Rawalpindi Saddar','Mall','Rawalpindi','Punjab','2020-04-18','Nida Farooq',23000),
('STR-010','Sialkot Cantt','High Street','Sialkot','Punjab','2024-01-10','Danish Butt',15000);

-- 3) Payment methods
INSERT INTO dim_payment_method (payment_method_code, payment_method_name, payment_provider, is_digital) VALUES
('CASH','Cash','In-store cash',FALSE),
('CARD','Debit/Credit Card','Bank POS',TRUE),
('WALLET','Mobile Wallet','JazzCash/EasyPaisa demo',TRUE),
('BANK','Bank Transfer','Online banking',TRUE),
('BNPL','Buy Now Pay Later','BNPL demo provider',TRUE);

-- 4) Promotions: 50 campaigns
INSERT INTO dim_promotion (promotion_code, promotion_name, promotion_type, channel, discount_percent, start_date, end_date)
SELECT
    'PROMO-' || LPAD(gs::text, 3, '0'),
    'Campaign ' || gs,
    (ARRAY['Seasonal','Clearance','Loyalty','Flash Sale','Bundle'])[1 + (gs % 5)],
    (ARRAY['Store','Web','App','Omni-channel'])[1 + (gs % 4)],
    (ARRAY[5,10,15,20,25])[1 + (gs % 5)]::numeric,
    DATE '2024-01-01' + ((gs * 17) % 900),
    DATE '2024-01-01' + ((gs * 17) % 900) + 21
FROM generate_series(1,50) gs;

-- 5) Customers: 100,000 synthetic customers
INSERT INTO dim_customer (customer_code, full_name, gender, age_band, city, region, loyalty_tier, registration_date, email_hash, phone_hash)
SELECT
    'CUST-' || LPAD(gs::text, 7, '0'),
    'Customer ' || gs,
    (ARRAY['Male','Female','Other/Unknown'])[1 + (gs % 3)],
    (ARRAY['18-24','25-34','35-44','45-54','55+'])[1 + (gs % 5)],
    (ARRAY['Lahore','Karachi','Islamabad','Peshawar','Quetta','Faisalabad','Multan','Hyderabad','Rawalpindi','Sialkot'])[1 + (gs % 10)],
    (ARRAY['Punjab','Sindh','Capital','KPK','Balochistan'])[1 + (gs % 5)],
    (ARRAY['Bronze','Silver','Gold','Platinum'])[1 + (gs % 4)],
    DATE '2021-01-01' + (gs % 1400),
    md5('customer-email-' || gs),
    md5('customer-phone-' || gs)
FROM generate_series(1,100000) gs;

-- 6) Products: 10 categories x 10 subcategories x 100 products = 10,000 products
-- Uses real subcategory names per the project spec.
WITH categories(cat_id, category_name) AS (VALUES
    (1,'Electronics'),(2,'Home & Kitchen'),(3,'Fashion'),(4,'Health & Beauty'),(5,'Sports & Outdoors'),
    (6,'Books & Stationery'),(7,'Toys & Games'),(8,'Automotive'),(9,'Grocery'),(10,'Office & Industrial')
),
subcat_names(cat_id, sub_no, subcategory_name) AS (VALUES
    (1,1,'Laptops'),(1,2,'Smartphones'),(1,3,'Tablets'),(1,4,'Cameras'),(1,5,'Headphones'),
    (1,6,'Smart Watches'),(1,7,'Networking'),(1,8,'Gaming Consoles'),(1,9,'Printers'),(1,10,'Storage Devices'),
    (2,1,'Cookware'),(2,2,'Appliances'),(2,3,'Furniture'),(2,4,'Bedding'),(2,5,'Lighting'),
    (2,6,'Decor'),(2,7,'Cleaning'),(2,8,'Kitchen Tools'),(2,9,'Bathroom'),(2,10,'Garden'),
    (3,1,'Men Shirts'),(3,2,'Men Shoes'),(3,3,'Women Dresses'),(3,4,'Women Shoes'),(3,5,'Kids Wear'),
    (3,6,'Watches'),(3,7,'Bags'),(3,8,'Jewelry'),(3,9,'Winter Wear'),(3,10,'Activewear'),
    (4,1,'Skincare'),(4,2,'Haircare'),(4,3,'Makeup'),(4,4,'Fragrance'),(4,5,'Personal Care'),
    (4,6,'Vitamins'),(4,7,'Fitness Care'),(4,8,'Oral Care'),(4,9,'Grooming'),(4,10,'Baby Care'),
    (5,1,'Cricket'),(5,2,'Football'),(5,3,'Gym Equipment'),(5,4,'Cycling'),(5,5,'Camping'),
    (5,6,'Running'),(5,7,'Swimming'),(5,8,'Yoga'),(5,9,'Hiking'),(5,10,'Sportswear'),
    (6,1,'Textbooks'),(6,2,'Novels'),(6,3,'Reference'),(6,4,'Notebooks'),(6,5,'Pens'),
    (6,6,'Art Supplies'),(6,7,'Office Paper'),(6,8,'Exam Prep'),(6,9,'Magazines'),(6,10,'Educational Toys'),
    (7,1,'Board Games'),(7,2,'Puzzles'),(7,3,'Action Figures'),(7,4,'Dolls'),(7,5,'STEM Toys'),
    (7,6,'Outdoor Toys'),(7,7,'Video Games'),(7,8,'Infant Toys'),(7,9,'Building Blocks'),(7,10,'Remote Control'),
    (8,1,'Car Care'),(8,2,'Motorbike Parts'),(8,3,'Tyres'),(8,4,'Oils'),(8,5,'Accessories'),
    (8,6,'Tools'),(8,7,'Batteries'),(8,8,'Lights'),(8,9,'Interior'),(8,10,'Safety'),
    (9,1,'Rice & Grains'),(9,2,'Snacks'),(9,3,'Beverages'),(9,4,'Dairy'),(9,5,'Frozen Foods'),
    (9,6,'Breakfast'),(9,7,'Spices'),(9,8,'Canned Food'),(9,9,'Personal Household'),(9,10,'Organic'),
    (10,1,'Desks'),(10,2,'Chairs'),(10,3,'Filing'),(10,4,'Monitors'),(10,5,'Projectors'),
    (10,6,'Cables'),(10,7,'Packaging'),(10,8,'Safety Gear'),(10,9,'Lab Supplies'),(10,10,'Industrial Tools')
),
subcategories AS (
    SELECT c.cat_id, c.category_name, sn.sub_no, sn.subcategory_name,
           ((c.cat_id - 1) * 10 + sn.sub_no) AS subcategory_id
    FROM categories c JOIN subcat_names sn ON sn.cat_id = c.cat_id
),
products AS (
    SELECT sc.category_name, sc.subcategory_name, sc.subcategory_id,
           ((sc.subcategory_id - 1) * 100 + p.product_no) AS product_seq,
           p.product_no
    FROM subcategories sc CROSS JOIN generate_series(1,100) p(product_no)
)
INSERT INTO dim_product (
    product_code, product_name, category_name, subcategory_name, brand_name, supplier_name,
    unit_size, color, standard_cost, list_price, launch_date
)
SELECT
    'PROD-' || LPAD(product_seq::text, 6, '0'),
    subcategory_name || ' Item ' || LPAD(product_no::text, 3, '0'),
    category_name,
    subcategory_name,
    'Brand ' || (1 + product_seq % 50),
    'Supplier ' || (1 + product_seq % 150),
    (ARRAY['Small','Medium','Large','Pack','Single Unit'])[1 + (product_seq % 5)],
    (ARRAY['Black','White','Blue','Red','Green','Silver','Mixed'])[1 + (product_seq % 7)],
    ROUND((50 + random() * 5000)::numeric, 2),
    ROUND((80 + random() * 8000)::numeric, 2),
    DATE '2023-01-01' + (product_seq % 1000)
FROM products;
