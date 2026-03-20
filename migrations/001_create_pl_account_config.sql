-- Migration: create pl_account_config
-- Run once in Supabase SQL Editor (or any PostgreSQL client).
-- Safe to re-run: uses IF NOT EXISTS and ON CONFLICT DO UPDATE.

CREATE TABLE IF NOT EXISTS pl_account_config (
    account_number  TEXT    PRIMARY KEY,
    description     TEXT    NOT NULL DEFAULT '',
    category        TEXT    NOT NULL CHECK (category IN ('COGS', 'EXPENSE', 'REVENUE', 'DEDUCTION', 'OTHER')),
    is_active       BOOLEAN NOT NULL DEFAULT true
);

-- If upgrading an existing table that was created without description:
ALTER TABLE pl_account_config ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';

-- Seed / refresh all standard accounts
INSERT INTO pl_account_config (account_number, description, category, is_active) VALUES
    ('5111',     'Doanh thu bán hàng hóa',                                      'REVENUE',   true),
    ('5118',     'Doanh thu khác',                                               'REVENUE',   true),
    ('5211',     'Chiết khấu thương mại',                                        'DEDUCTION', true),
    ('5212',     'Giảm giá hàng bán',                                            'DEDUCTION', true),
    ('5213',     'Hàng bán bị trả lại',                                          'DEDUCTION', true),
    ('6211',     'Chi phí len',                                                  'COGS',      true),
    ('6221',     'Chi phí làm concept design',                                   'COGS',      true),
    ('6222',     'Chi phí làm chart + móc + quay (optional)',                    'COGS',      true),
    ('6223',     'Chi phí quay',                                                 'COGS',      true),
    ('6224',     'Chi phí chụp + quay',                                          'COGS',      true),
    ('6225',     'Chi phí viết pattern - dịch chart',                            'COGS',      true),
    ('6273',     'Chi phí dụng cụ tool',                                         'EXPENSE',   true),
    ('6273_alt', 'Chi phí dụng cụ quay, ánh sáng, phông nền',                   'EXPENSE',   true),
    ('631',      'Giá thành sản xuất',                                           'COGS',      true),
    ('632',      'Giá vốn hàng bán',                                             'COGS',      true),
    ('6411',     'Chi phí nhân viên',                                            'EXPENSE',   true),
    ('6412',     'Chi phí nguyên vật liệu, bao bì',                              'EXPENSE',   true),
    ('6413',     'Chi phí dụng cụ tool sàn',                                     'EXPENSE',   true),
    ('6414',     'Chi phí dụng cụ tool',                                         'EXPENSE',   true),
    ('6421',     'Chi phí nhân viên quản lý',                                    'EXPENSE',   true),
    ('6428',     'Chi phí nhân viên marketing - đăng và quản lí kênh',           'EXPENSE',   true),
    ('911',      'Tổng giá thành vận hành',                                      'OTHER',     true)
ON CONFLICT (account_number) DO UPDATE
    SET description = EXCLUDED.description,
        category    = EXCLUDED.category;
