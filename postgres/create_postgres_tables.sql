-- =====================================================================================
-- ETSY STAR SCHEMA DATABASE - PostgreSQL Tables
-- =====================================================================================
-- This script creates all tables for the Etsy data warehouse star schema
-- Run order: 1) Dimensions first, 2) Facts last
-- =====================================================================================

-- =====================================================================================
-- DIMENSION TABLES
-- =====================================================================================

-- 1. TIME DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_time (
    -- Primary Key
    time_key INTEGER PRIMARY KEY,

    -- Date Components
    full_date DATE NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    week_of_year INTEGER,
    day_of_month INTEGER,
    day_of_week INTEGER,
    day_of_year INTEGER,

    -- Date Names
    month_name VARCHAR(20) NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    quarter_name VARCHAR(10) NOT NULL,

    -- Date Flags
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN DEFAULT FALSE,
    holiday_name VARCHAR(100),
    is_business_day BOOLEAN DEFAULT TRUE,

    -- Etsy Business Calendar
    etsy_season VARCHAR(50),
    is_peak_season BOOLEAN DEFAULT FALSE,
    selling_season VARCHAR(50),

    -- Current Period Flags
    is_current_day BOOLEAN DEFAULT FALSE,
    is_current_week BOOLEAN DEFAULT FALSE,
    is_current_month BOOLEAN DEFAULT FALSE,
    is_current_quarter BOOLEAN DEFAULT FALSE,
    is_current_year BOOLEAN DEFAULT FALSE
);

-- 2. PRODUCT DIMENSION (SCD Type 2)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_product (
    -- Primary Key
    product_key BIGSERIAL PRIMARY KEY,

    -- Business Key
    listing_id BIGINT,

    -- Basic Product Info
    title TEXT,
    description TEXT,
    price DECIMAL(15,2),
    currency_code VARCHAR(3),
    quantity INTEGER,

    -- Product Classification
    category TEXT,
    subcategory TEXT,
    product_type TEXT,

    -- Product Attributes
    materials_list TEXT,  -- JSON array as text
    tags_list TEXT,       -- JSON array as text
    color TEXT,
    material TEXT,
    dimensions TEXT,
    how_made TEXT,

    -- Product Variations
    variation_1_type TEXT,
    variation_1_name TEXT,
    variation_1_values TEXT,
    variation_2_type TEXT,
    variation_2_name TEXT,
    variation_2_values TEXT,

    -- Product Images
    image_urls TEXT,       -- JSON array as text
    primary_image_url TEXT,

    -- Business Information
    sku_list TEXT,         -- JSON array as text
    story TEXT,
    instructions TEXT,
    how_use TEXT,
    fit_for TEXT,
    country_origin TEXT,

    -- Data Quality Score
    completeness_score DECIMAL(3,2) DEFAULT 0.00,

    -- SCD Type 2 Fields
    effective_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expiry_date TIMESTAMP NOT NULL DEFAULT '9999-12-31 23:59:59',
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. CUSTOMER DIMENSION (SCD Type 2)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_customer (
    -- Primary Key
    customer_key BIGSERIAL PRIMARY KEY,

    -- Business Key
    buyer_user_name TEXT NOT NULL,

    -- Personal Information (PII - requires encryption)
    full_name TEXT,
    first_name TEXT,
    last_name TEXT,

    -- Geographic Information (Default shipping location)
    country TEXT,
    state TEXT,
    city TEXT,
    zipcode TEXT,

    -- Payment Information
    payment_method TEXT,
    ship_date TIMESTAMP,

    -- Address Information
    street_1 TEXT,
    street_2 TEXT,
    ship_name TEXT,

    -- SCD Type 2 Fields
    effective_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expiry_date TIMESTAMP NOT NULL DEFAULT '9999-12-31 23:59:59',
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. ORDER DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_order (
    -- Primary Key
    order_key BIGSERIAL PRIMARY KEY,

    -- Business Key
    order_id BIGINT NOT NULL UNIQUE,

    -- Order Characteristics
    order_type TEXT,      -- Regular, In-person, etc.
    payment_method TEXT,
    payment_type TEXT,
    number_of_items INTEGER DEFAULT 1,
    order_value DECIMAL(15,2),  -- Total order value

    -- Financial Information (from code)
    discount_amount DECIMAL(15,2),
    shipping_discount DECIMAL(15,2),
    shipping DECIMAL(15,2),
    sales_tax DECIMAL(15,2),
    order_total DECIMAL(15,2),
    card_processing_fees DECIMAL(15,2),
    order_net DECIMAL(15,2),
    adjusted_order_total DECIMAL(15,2),
    adjusted_card_processing_fees DECIMAL(15,2),
    adjusted_net_order_amount DECIMAL(15,2),

    -- Discounts & Promotions
    coupon_code TEXT,
    coupon_details TEXT,
    has_discount BOOLEAN DEFAULT FALSE,
    discount_type TEXT,   -- Percentage, Fixed, Shipping

    -- Shipping Information
    shipping_method TEXT,
    shipping_country TEXT,
    shipping_state TEXT,
    shipping_city TEXT,
    is_international BOOLEAN DEFAULT FALSE,


    -- Special Attributes
    is_gift BOOLEAN DEFAULT FALSE,
    has_personalization BOOLEAN DEFAULT FALSE,
    in_person_location TEXT,

    -- Audit Fields
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. GEOGRAPHY DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_geography (
    -- Primary Key
    geography_key BIGSERIAL PRIMARY KEY,

    -- Location Hash for efficient lookups
    location_hash VARCHAR(32),

    -- Address Components
    country_name TEXT NOT NULL,
    state_name TEXT,
    city_name TEXT,
    postal_code TEXT,

    -- Geographic Hierarchy
    continent TEXT,
    region TEXT,         -- North America, Europe, etc.

    -- Additional Geographic Codes (Added to match SQLite)
    country_code VARCHAR(3),
    state_code VARCHAR(10),
    sub_region TEXT,

    -- Business Geography
    etsy_market TEXT,     -- US, EU, International
    shipping_zone TEXT,   -- Domestic, International

    -- Economic Information
    currency_code VARCHAR(3),
    timezone VARCHAR(50),

    -- Audit Fields
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. PAYMENT METHOD DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_payment (
    -- Primary Key
    payment_key BIGSERIAL PRIMARY KEY,

    -- Payment Method Details
    payment_method TEXT NOT NULL,
    payment_type TEXT,    -- Online, In-person
    payment_provider TEXT, -- Etsy Payments, PayPal, etc.

    -- Audit Fields
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. BANK ACCOUNT DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_bank_account (
    -- Primary Key
    bank_account_key BIGSERIAL PRIMARY KEY,

    -- Business Key
    account_number TEXT NOT NULL UNIQUE,

    -- Account Information
    account_name TEXT NOT NULL,
    opening_date DATE,
    
    -- Customer Information
    cif_number TEXT,       -- Customer Identification Number
    customer_address TEXT, -- Full address from bank records
    
    -- Account Status
    is_active BOOLEAN DEFAULT TRUE,
    currency_code VARCHAR(3) DEFAULT 'VND',

    -- Audit Fields
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 8. PRODUCT CATALOG DIMENSION (Internal Business Products)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_product_catalog (
    -- Primary Key
    product_catalog_key BIGSERIAL PRIMARY KEY,

    -- Business Keys (Composite Natural Key)
    product_line_id VARCHAR(50) NOT NULL,
    product_id VARCHAR(50) NOT NULL,
    variant_id VARCHAR(50) NOT NULL,

    -- Descriptive Attributes
    product_line_name VARCHAR(200),
    product_name VARCHAR(200),
    variant_name VARCHAR(200),

    -- Generated Code for fast lookup
    product_code VARCHAR(200) GENERATED ALWAYS AS 
        (product_line_id || '_' || product_id || '_' || variant_id) STORED,

    -- Audit Fields
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint on natural key
    CONSTRAINT uq_product_catalog_natural_key 
        UNIQUE (product_line_id, product_id, variant_id)
);

-- =====================================================================================
-- FACT TABLES
-- =====================================================================================

-- =====================================================================================
-- 1. SALES FACT TABLE (Primary)
-- =====================================================================================
-- Note: Currency dimension removed - all amounts converted to USD in silver layer
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_sales (
    -- Primary Key
    sales_key BIGSERIAL PRIMARY KEY,

    -- Dimension Foreign Keys
    product_key BIGINT REFERENCES dim_product(product_key), -- Nullable
    customer_key BIGINT REFERENCES dim_customer(customer_key), -- Nullable
    order_key BIGINT REFERENCES dim_order(order_key), -- Nullable
    sale_date_key INTEGER REFERENCES dim_time(time_key), -- Nullable
    ship_date_key INTEGER REFERENCES dim_time(time_key), -- Nullable
    paid_date_key INTEGER REFERENCES dim_time(time_key), -- Nullable
    geography_key BIGINT REFERENCES dim_geography(geography_key), -- Nullable
    payment_key BIGINT REFERENCES dim_payment(payment_key), -- Nullable

    -- Degenerate Dimensions (Business Keys)
    transaction_id BIGINT,
    order_id BIGINT,
    sku TEXT,

    -- Quantity Measures
    quantity_sold INTEGER,

    -- Revenue Measures (Original Currency)
    item_price DECIMAL(15,2),
    item_total DECIMAL(15,2),
    discount_amount DECIMAL(15,2),
    shipping_amount DECIMAL(15,2),
    shipping_discount DECIMAL(15,2),
    order_sales_tax DECIMAL(15,2),

    -- Conversion tracking
    conversion_date DATE,

    -- Product Variations (Denormalized for analysis)
    variations TEXT, -- JSON or structured format
    size TEXT,
    style TEXT,
    color TEXT,
    material TEXT,
    personalization TEXT,

    -- VAT Information
    vat_paid_by_buyer DECIMAL(15,2),

    -- Audit Fields
    created_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'sold_order_items',
    batch_id VARCHAR(100)
);

-- =====================================================================================
-- 2. FINANCIAL TRANSACTIONS FACT TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_financial_transactions (
    -- Primary Key
    financial_transaction_key BIGSERIAL PRIMARY KEY,

    -- Dimension Foreign Keys
    transaction_date_key INTEGER REFERENCES dim_time(time_key),
    customer_key BIGINT REFERENCES dim_customer(customer_key), -- Nullable
    order_key BIGINT REFERENCES dim_order(order_key),         -- Nullable
    product_key BIGINT REFERENCES dim_product(product_key),   -- Nullable

    -- Business Keys
    extracted_id TEXT,
    order_id BIGINT,
    transaction_id BIGINT,

    -- Transaction Classification
    transaction_type TEXT,
    transaction_title TEXT,
    revenue_type TEXT, -- Revenue, Cost, Transfer
    fee_type TEXT,    -- Processing, Listing, Transaction
    id_type TEXT,      -- Order ID, Listing ID, Transaction ID
    info_description TEXT,

    -- Financial Measures (Original Currency)
    amount DECIMAL(15,2),
    fees_and_taxes DECIMAL(15,2),
    net DECIMAL(15,2),
    tax_details DECIMAL(15,2),

    -- Raw Data Preservation
    original_info TEXT,

    -- Audit Fields
    created_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'statement',
    batch_id VARCHAR(100)
);

-- =====================================================================================
-- 3. DEPOSITS FACT TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_deposits (
    -- Primary Key
    deposit_key BIGSERIAL PRIMARY KEY,

    -- Dimension Foreign Keys
    deposit_date_key INTEGER REFERENCES dim_time(time_key),

    -- Deposit Measures
    deposit_amount DECIMAL(15,2),
    deposit_status TEXT,
    bank_account_ending_digits INTEGER,

    -- Audit Fields
    created_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'deposits',
    batch_id VARCHAR(100)
);

-- =====================================================================================
-- 4. PAYMENTS FACT TABLE (Optional - Detailed Payment Tracking)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_payments (
    -- Primary Key
    payment_transaction_key BIGSERIAL PRIMARY KEY,

    -- Dimension Foreign Keys
    customer_key BIGINT REFERENCES dim_customer(customer_key),
    order_key BIGINT REFERENCES dim_order(order_key),
    payment_date_key INTEGER REFERENCES dim_time(time_key),
    payment_method_key BIGINT REFERENCES dim_payment(payment_key),

    -- Business Keys
    payment_id BIGINT,
    buyer_username TEXT,
    buyer_name TEXT,
    order_id BIGINT,

    -- Payment Amounts
    gross_amount DECIMAL(15,2),
    fees DECIMAL(15,2),
    net_amount DECIMAL(15,2),

    -- Posted vs Adjusted
    posted_gross DECIMAL(15,2),
    posted_fees DECIMAL(15,2),
    posted_net DECIMAL(15,2),
    adjusted_gross DECIMAL(15,2),
    adjusted_fees DECIMAL(15,2),
    adjusted_net DECIMAL(15,2),

    -- Multi-currency
    currency TEXT,
    listing_amount DECIMAL(15,2),
    listing_currency TEXT,
    exchange_rate DECIMAL(15,8),
    vat_amount DECIMAL(15,2),
    gift_card_applied BOOLEAN,

    -- Status & Flags
    status TEXT,
    funds_available TIMESTAMP,
    order_date TIMESTAMP,
    buyer TEXT,
    order_type TEXT,
    payment_type TEXT,
    refund_amount DECIMAL(15,2),

    -- Audit Fields
    created_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'direct_checkout',
    batch_id VARCHAR(100)
);

-- =====================================================================================
-- 5. BANK TRANSACTIONS FACT TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_bank_transactions (
    -- Primary Key
    bank_transaction_key BIGSERIAL PRIMARY KEY,

    -- Dimension Foreign Keys
    bank_account_key BIGINT REFERENCES dim_bank_account(bank_account_key),
    transaction_date_key INTEGER REFERENCES dim_time(time_key),
    product_catalog_key BIGINT REFERENCES dim_product_catalog(product_catalog_key),

    -- Business Keys
    reference_number TEXT NOT NULL,        -- TF250922206699656
    account_number TEXT NOT NULL,          -- 8007041138769

    -- Transaction Details
    transaction_description TEXT,          -- Diễn giải
    pl_account_number VARCHAR(10),

    -- Parsed Product Information from transaction_description
    parsed_product_line_id VARCHAR(50),
    parsed_product_id VARCHAR(50),
    parsed_variant_id VARCHAR(50),
    
    -- Financial Measures
    credit_amount DECIMAL(15,2),           -- Phát sinh có
    debit_amount DECIMAL(15,2),            -- Phát sinh nợ  
    balance_after_transaction DECIMAL(15,2), -- Số dư sau giao dịch
    
    -- Transaction Classification
    is_business_related BOOLEAN DEFAULT TRUE,
    
    -- Audit Fields
    data_source VARCHAR(50) DEFAULT 'bank_statement',
    batch_id VARCHAR(100)
);

-- =====================================================================================
-- PERFORMANCE INDEXES
-- =====================================================================================

-- Product Dimension Indexes
CREATE INDEX IF NOT EXISTS idx_dim_product_listing_id ON dim_product(listing_id);
CREATE INDEX IF NOT EXISTS idx_dim_product_current ON dim_product(is_current, effective_date);
CREATE INDEX IF NOT EXISTS idx_dim_product_category ON dim_product(category, subcategory);

-- Customer Dimension Indexes
CREATE INDEX IF NOT EXISTS idx_dim_customer_buyer_id ON dim_customer(buyer_user_name);
CREATE INDEX IF NOT EXISTS idx_dim_customer_current ON dim_customer(is_current, effective_date);

-- Order Dimension Indexes
CREATE INDEX IF NOT EXISTS idx_dim_order_order_id ON dim_order(order_id);
CREATE INDEX IF NOT EXISTS idx_dim_order_type ON dim_order(order_type);

-- Geography Dimension Indexes
CREATE INDEX IF NOT EXISTS idx_dim_geography_country ON dim_geography(country_name);
CREATE INDEX IF NOT EXISTS idx_dim_geography_market ON dim_geography(etsy_market);

-- Sales Fact Indexes (Most Important)
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON fact_sales(sale_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_geography ON fact_sales(geography_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_composite ON fact_sales(sale_date_key, product_key, customer_key);

-- Financial Transactions Fact Indexes
CREATE INDEX IF NOT EXISTS idx_fact_financial_date ON fact_financial_transactions(transaction_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_financial_type ON fact_financial_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_fact_financial_revenue_type ON fact_financial_transactions(revenue_type);

-- Deposits Fact Indexes
CREATE INDEX IF NOT EXISTS idx_fact_deposits_date ON fact_deposits(deposit_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_deposits_status ON fact_deposits(deposit_status);

-- Bank Account Dimension Indexes
CREATE INDEX IF NOT EXISTS idx_dim_bank_account_number ON dim_bank_account(account_number);
CREATE INDEX IF NOT EXISTS idx_dim_bank_account_active ON dim_bank_account(is_active);

-- Product Catalog Dimension Indexes
CREATE INDEX IF NOT EXISTS idx_dim_product_catalog_product_line ON dim_product_catalog(product_line_id);
CREATE INDEX IF NOT EXISTS idx_dim_product_catalog_product ON dim_product_catalog(product_id);
CREATE INDEX IF NOT EXISTS idx_dim_product_catalog_variant ON dim_product_catalog(variant_id);
CREATE INDEX IF NOT EXISTS idx_dim_product_catalog_product_code ON dim_product_catalog(product_code);
CREATE INDEX IF NOT EXISTS idx_dim_product_catalog_composite ON dim_product_catalog(product_line_id, product_id, variant_id);

-- Bank Transactions Fact Indexes
CREATE INDEX IF NOT EXISTS idx_fact_bank_transactions_date ON fact_bank_transactions(transaction_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_bank_transactions_account ON fact_bank_transactions(bank_account_key);
CREATE INDEX IF NOT EXISTS idx_fact_bank_transactions_reference ON fact_bank_transactions(reference_number);
CREATE INDEX IF NOT EXISTS idx_fact_bank_transactions_product_catalog ON fact_bank_transactions(product_catalog_key);
CREATE INDEX IF NOT EXISTS idx_fact_bank_transactions_parsed_product ON fact_bank_transactions(parsed_product_line_id, parsed_product_id, parsed_variant_id);
CREATE INDEX IF NOT EXISTS idx_fact_bank_transactions_composite ON fact_bank_transactions(transaction_date_key, bank_account_key);

-- Optimized index for COGS queries (product cost calculations)
-- Partial index: only index rows where debit_amount IS NOT NULL (expenses)
CREATE INDEX IF NOT EXISTS idx_fact_bank_transactions_cogs 
ON fact_bank_transactions(parsed_product_id, pl_account_number) 
WHERE debit_amount IS NOT NULL;
