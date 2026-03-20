# -*- coding: utf-8 -*-
"""One-time script: update pl_account_config with proper Vietnamese descriptions."""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.db import execute_query

rows = [
    ('5111',     'Doanh thu bán hàng hóa'),
    ('5118',     'Doanh thu khác'),
    ('5211',     'Chiết khấu thương mại'),
    ('5212',     'Giảm giá hàng bán'),
    ('5213',     'Hàng bán bị trả lại'),
    ('6211',     'Chi phí len'),
    ('6221',     'Chi phí làm concept design'),
    ('6222',     'Chi phí làm chart + móc + quay (optional)'),
    ('6223',     'Chi phí quay'),
    ('6224',     'Chi phí chụp + quay'),
    ('6225',     'Chi phí viết pattern - dịch chart'),
    ('6273',     'Chi phí dụng cụ tool'),
    ('6273_alt', 'Chi phí dụng cụ quay, ánh sáng, phông nền'),
    ('631',      'Giá thành sản xuất'),
    ('632',      'Giá vốn hàng bán'),
    ('6411',     'Chi phí nhân viên'),
    ('6412',     'Chi phí nguyên vật liệu, bao bì'),
    ('6413',     'Chi phí dụng cụ tool sàn'),
    ('6414',     'Chi phí dụng cụ tool'),
    ('6421',     'Chi phí nhân viên quản lý'),
    ('6428',     'Chi phí nhân viên marketing - đăng và quản lí kênh'),
    ('911',      'Tổng giá thành vận hành'),
]

for acc, desc in rows:
    execute_query(
        'UPDATE pl_account_config SET description = %s WHERE account_number = %s',
        (desc, acc),
    )
    print(f'  updated {acc}: {desc}')

print('Done.')
