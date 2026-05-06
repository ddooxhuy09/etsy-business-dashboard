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
    date_key        DATE            NOT NULL,
    year            INT             NOT NULL,
    quarter         VARCHAR(6)      NOT NULL,
    month_num       INT             NOT NULL,
    month_name      VARCHAR(10)     NOT NULL,
    week_of_year    INT             NOT NULL,
    day_of_week     VARCHAR(10)     NOT NULL,
    is_weekend      BOOLEAN         NOT NULL,
    CONSTRAINT pk_dim_time PRIMARY KEY (date_key)
);


-- 2. CUSTOMER DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key        BIGSERIAL       PRIMARY KEY,
    buyer_user_name     TEXT            NOT NULL,
    full_name           TEXT
);


-- 3. PRODUCT DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_product (
    product_key         BIGSERIAL       PRIMARY KEY,
    listing_id          TEXT,
    title               TEXT,
    description         TEXT,
    price               DECIMAL(15,2),
    quantity            INTEGER,
    materials           TEXT,
    tags                TEXT,
    variation_1_type    TEXT,
    variation_1_name    TEXT,
    variation_1_values  TEXT,
    variation_2_type    TEXT,
    variation_2_name    TEXT,
    variation_2_values  TEXT,
    image_urls          TEXT,
    sku                 TEXT
);


-- 4. PRODUCT LINE DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_product_line (
    dim_product_line_key    BIGSERIAL       PRIMARY KEY,
    variant_id              VARCHAR(20)     NOT NULL,
    product_line_id         VARCHAR(20)     NOT NULL,
    product_line            VARCHAR(100)    NOT NULL,
    product_id              VARCHAR(20)     NOT NULL,
    product                 VARCHAR(100)    NOT NULL,
    variants                VARCHAR(200)    NOT NULL,
    product_code            VARCHAR(200)    GENERATED ALWAYS AS
                                (product_line_id || '_' || product_id || '_' || variant_id) STORED,
    UNIQUE (product_line_id, product_id, variant_id)
);


-- 5. PL ACCOUNTS DIMENSION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS dim_pl_accounts (
    pl_account_number   VARCHAR(10)     PRIMARY KEY,
    category            VARCHAR(100)    NOT NULL,
    description         TEXT
);


-- =====================================================================================
-- FACT TABLES
-- =====================================================================================

-- 1. ORDERS FACT TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_orders (
    order_key                       BIGSERIAL       PRIMARY KEY,
    order_id                        TEXT            NOT NULL UNIQUE,

    sale_date_key                   DATE            REFERENCES dim_time(date_key),
    date_shipped                    DATE,
    customer_key                    BIGINT          REFERENCES dim_customer(customer_key),
    buyer_user_id                   TEXT,

    order_type                      TEXT,
    payment_method                  TEXT,
    payment_type                    TEXT,
    number_of_items                 INTEGER         DEFAULT 1,
    order_value                     DECIMAL(15,2),
    discount_amount                 DECIMAL(15,2),
    shipping_discount               DECIMAL(15,2),
    shipping                        DECIMAL(15,2),
    sales_tax                       DECIMAL(15,2),
    order_total                     DECIMAL(15,2),
    card_processing_fees            DECIMAL(15,2),
    order_net                       DECIMAL(15,2),
    adjusted_order_total            DECIMAL(15,2),
    adjusted_card_processing_fees   DECIMAL(15,2),
    adjusted_net_order_amount       DECIMAL(15,2),

    order_status                    TEXT,
    coupon_code                     TEXT,
    coupon_details                  TEXT,

    street_1                        TEXT,
    street_2                        TEXT,
    shipping_country                TEXT,
    shipping_state                  TEXT,
    shipping_city                   TEXT,
    shipping_zipcode                TEXT
);


-- 2. ORDER ITEMS FACT TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_order_items (
    order_item_key      BIGSERIAL       PRIMARY KEY,

    order_key           BIGINT          REFERENCES fact_orders(order_key),
    product_key         BIGINT          REFERENCES dim_product(product_key),

    transaction_id      BIGINT,
    order_id            TEXT,
    sku                 TEXT,
    listing_id          TEXT,
    quantity_sold       INTEGER,
    price               DECIMAL(15,2),
    item_total          DECIMAL(15,2),
    variations          TEXT,
    date_paid           DATE,
    vat_paid_by_buyer   DECIMAL(15,2)
);


-- 3. PAYMENTS FACT TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_payments (
    payment_key         BIGSERIAL       PRIMARY KEY,

    payment_id          BIGINT,
    order_id            TEXT,

    funds_available_date DATE,

    gross_amount        DECIMAL(15,2),
    fees                DECIMAL(15,2),
    net_amount          DECIMAL(15,2),
    listing_amount      DECIMAL(15,2),
    refund_amount       DECIMAL(15,2),
    exchange_rate       DECIMAL(15,8),
    vat_amount          DECIMAL(15,2),

    payment_status      TEXT
);


-- 4. STATEMENT FACT TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_statement (
    statement_key       BIGSERIAL       PRIMARY KEY,

    entry_date          DATE,
    entry_type          VARCHAR(20),
    title               TEXT,
    info                TEXT,
    amount              DECIMAL(15,2),
    fees_and_taxes      DECIMAL(15,2),
    net                 DECIMAL(15,2),
    tax_details         TEXT,

    ref_order_id        TEXT
);


-- 5. DEPOSITS BRIDGE TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS bridge_deposits (
    deposit_key                 BIGSERIAL   PRIMARY KEY,

    deposit_date                DATE        REFERENCES dim_time(date_key),

    amount                      DECIMAL(15,2),
    deposit_status              TEXT,
    bank_account_ending_digits  INTEGER
);


-- 6. BANK TRANSACTIONS FACT TABLE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fact_bank_transactions (
    bank_transaction_key    BIGSERIAL       PRIMARY KEY,

    transaction_date        TIMESTAMP,

    reference_number        TEXT            NOT NULL,
    account_number          TEXT            NOT NULL,
    account_name            TEXT,
    opening_date            DATE,
    transaction_description TEXT,
    pl_account_number       VARCHAR(10)     REFERENCES dim_pl_accounts(pl_account_number),

    parsed_product_line_id  VARCHAR(50),
    parsed_product_id       VARCHAR(50),
    parsed_variant_id       VARCHAR(50),

    credit_amount           DECIMAL(15,2),
    debit_amount            DECIMAL(15,2),
    balance                 DECIMAL(15,2)
);


-- =====================================================================================
-- PERFORMANCE INDEXES
-- =====================================================================================

CREATE INDEX IF NOT EXISTS idx_bank_tx_pl_acc 
ON fact_bank_transactions (pl_account_number);

CREATE INDEX IF NOT EXISTS idx_bank_tx_product 
ON fact_bank_transactions (parsed_product_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_bank_tx_account_ref
ON fact_bank_transactions (account_number, reference_number);

CREATE INDEX IF NOT EXISTS idx_orders_date 
ON fact_orders (sale_date_key);

CREATE INDEX IF NOT EXISTS idx_orders_customer 
ON fact_orders (customer_key);

CREATE INDEX IF NOT EXISTS idx_order_items_order 
ON fact_order_items (order_key);

CREATE INDEX IF NOT EXISTS idx_order_items_product 
ON fact_order_items (product_key);

CREATE INDEX IF NOT EXISTS idx_fact_statement_date 
ON fact_statement (entry_date);

CREATE INDEX IF NOT EXISTS idx_fact_payments_order 
ON fact_payments (order_id);

CREATE INDEX IF NOT EXISTS idx_dim_product_listing_id 
ON dim_product (listing_id);

CREATE INDEX IF NOT EXISTS idx_dim_customer_buyer 
ON dim_customer (buyer_user_name);

CREATE INDEX IF NOT EXISTS idx_dim_product_line_code 
ON dim_product_line (product_code);

CREATE INDEX IF NOT EXISTS idx_bridge_deposits_date 
ON bridge_deposits (deposit_date);
