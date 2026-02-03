import React, { useState, useEffect, useMemo } from 'react';
import { Card, Table, Select, DatePicker, Spin, message } from 'antd';
import { DownOutlined, RightOutlined } from '@ant-design/icons';
import { fetchProfitLossSummaryTable } from '../api/profitLoss';
import '../styles/profitLoss.css';

const viewModes = [
  { value: 'month', label: 'Month' },
  { value: 'year', label: 'Year' },
  { value: 'month_year', label: 'Month/Year' },
];

// Tất cả các expense items có thể chọn để tính profit
const ALL_EXPENSE_OPTIONS = [
  { value: 'refund_cost', label: 'Refund Cost' },
  { value: 'cost_of_goods', label: 'Cost of Goods' },
  { value: 'total_etsy_fees', label: 'Etsy Fees' },
  { value: 'general_production_cost', label: 'Chi phí sản xuất chung' },
  { value: 'staff_cost', label: 'Chi phí nhân viên (Chi phí bán hàng)' },
  { value: 'material_packaging_cost', label: 'Chi phí nguyên vật liệu, bao bì (Chi phí bán hàng)' },
  { value: 'platform_tool_cost', label: 'Chi phí dụng cụ tool sàn (Chi phí bán hàng)' },
  { value: 'tool_cost', label: 'Chi phí dụng cụ tool (Chi phí bán hàng)' },
  { value: 'management_staff_cost', label: 'Chi phí nhân viên quản lý (Chi phí quản lý doanh nghiệp)' },
  { value: 'marketing_staff_cost', label: 'Chi phí nhân viên marketing - đăng và quản lí kênh (Chi phí quản lý doanh nghiệp)' },
];

// Default selected items
const DEFAULT_EXPENSE_ITEMS = [
  'refund_cost',
  'cost_of_goods',
  'total_etsy_fees',
  'general_production_cost',
  'staff_cost',
  'material_packaging_cost',
  'platform_tool_cost',
  'tool_cost',
  'management_staff_cost',
  'marketing_staff_cost',
];

const ETSY_CHILDREN = [
  '  - Transaction Fee',
  '  - Processing Fee',
  '  - Regulatory Operating Fee',
  '  - Listing Fee',
  '  - Marketing',
  '  - VAT',
];
const VAT_CHILDREN = [
  '    --- auto-renew sold',
  '    --- shipping_transaction',
  '    --- Processing Fee',
  '    --- transaction credit',
  '    --- listing credit',
  '    --- listing',
  '    --- Etsy Plus subscription',
];
const COGS_CHILDREN = [
  '  - Chi phí len (Chi phí nguyên liệu, vật liệu trực tiếp)',
  '  - Chi phí làm concept design (Chi phí nhân công trực tiếp)',
  '  - Chi phí làm chart + móc + quay (optional) (Chi phí nhân công trực tiếp)',
  '  - Chi phí quay (Chi phí nhân công trực tiếp)',
  '  - Chi phí chụp + quay (Chi phí nhân công trực tiếp)',
  '  - Chi phí viết pattern - dịch chart (Chi phí nhân công trực tiếp)',
];

function fmt(v) {
  if (v == null || (typeof v === 'number' && isNaN(v))) return '—';
  if (typeof v !== 'number') return String(v);
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function isChildHidden(lineItem, expanded) {
  if (ETSY_CHILDREN.includes(lineItem) && !expanded.etsy) return true;
  if (VAT_CHILDREN.includes(lineItem) && !expanded.vat) return true;
  if (COGS_CHILDREN.includes(lineItem) && !expanded.cogs) return true;
  return false;
}

export default function ProfitLossStatement() {
  const [startDate, setStartDate] = useState(null);
  const [endDate, setEndDate] = useState(null);
  const [viewMode, setViewMode] = useState('month');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState({ etsy: false, vat: false, cogs: false });
  const [selectedExpenseItems, setSelectedExpenseItems] = useState(DEFAULT_EXPENSE_ITEMS);

  const toggle = (key) => setExpanded((s) => ({ ...s, [key]: !s[key] }));

  const filters = useMemo(
    () => ({
      start_date: startDate?.format?.('YYYY-MM-DD') || null,
      end_date: endDate?.format?.('YYYY-MM-DD') || null,
      view_mode: viewMode,
      selected_items: selectedExpenseItems.length > 0 ? selectedExpenseItems.join(',') : null,
      use_default_formula: false, // Sử dụng selected_items từ UI
    }),
    [startDate, endDate, viewMode, selectedExpenseItems]
  );

  useEffect(() => {
    setLoading(true);
    fetchProfitLossSummaryTable(filters)
      .then((r) => setData(r?.data || []))
      .catch(() => message.error('Failed to load Profit & Loss table'))
      .finally(() => setLoading(false));
  }, [filters.start_date, filters.end_date, filters.view_mode, filters.selected_items]);

  // Profit đã được tính từ backend dựa trên selected_items
  const rows = useMemo(() => {
    return data
      .filter((r) => !isChildHidden(r['Line Item'], expanded))
      .map((r, i) => ({ ...r, key: `pl-${i}` }));
  }, [data, expanded]);

  const columns = useMemo(() => {
    if (!data.length) return [{ title: 'Line Item', dataIndex: 'Line Item', key: 'Line Item', width: 400 }];
    const keys = Object.keys(data[0]);
    return [
      {
        title: 'Line Item',
        dataIndex: 'Line Item',
        key: 'Line Item',
        width: 400,
        fixed: 'left',
        render: (val) => {
          const headers = [
            'Revenue (Sales)',
            '',
            'COGS (Cost of Goods Sold)',
            'Operating Expenses',
            'Net Income (Profit)',
          ];
          const isHeader = headers.includes(val);
          let caret = null;
          if (val === 'Etsy Fees') {
            caret = (
              <span
                role="button"
                tabIndex={0}
                onClick={() => toggle('etsy')}
                onKeyDown={(e) => e.key === 'Enter' && toggle('etsy')}
                style={{ cursor: 'pointer', marginRight: 6, userSelect: 'none' }}
              >
                {expanded.etsy ? <DownOutlined /> : <RightOutlined />}
              </span>
            );
          } else if (val === '  - VAT') {
            caret = (
              <span
                role="button"
                tabIndex={0}
                onClick={() => toggle('vat')}
                onKeyDown={(e) => e.key === 'Enter' && toggle('vat')}
                style={{ cursor: 'pointer', marginRight: 6, userSelect: 'none' }}
              >
                {expanded.vat ? <DownOutlined /> : <RightOutlined />}
              </span>
            );
          } else if (val === 'Cost of Goods') {
            caret = (
              <span
                role="button"
                tabIndex={0}
                onClick={() => toggle('cogs')}
                onKeyDown={(e) => e.key === 'Enter' && toggle('cogs')}
                style={{ cursor: 'pointer', marginRight: 6, userSelect: 'none' }}
              >
                {expanded.cogs ? <DownOutlined /> : <RightOutlined />}
              </span>
            );
          }
          return (
            <span style={{ fontWeight: isHeader ? 600 : 400 }}>
              {caret}
              {val || ''}
            </span>
          );
        },
      },
      ...keys
        .filter((k) => k !== 'Line Item')
        .map((k) => ({
          title: k,
          dataIndex: k,
          key: k,
          align: 'right',
          width: 120,
          render: (v) => fmt(v),
        })),
    ];
  }, [data, expanded]);

  const getRowClassName = (record) => {
    const line = record['Line Item'];
    if (['Revenue (Sales)', '', 'COGS (Cost of Goods Sold)', 'Operating Expenses', 'Net Income (Profit)'].includes(line))
      return 'pl-section-header';
    if (line === 'Profit') return 'pl-profit-row';
    if (['Revenue', 'Cost of Goods', 'Etsy Fees', 'Refund Cost', '  - VAT'].includes(line)) return 'pl-subtotal-row';
    return '';
  };

  return (
    <div className="pl-page" style={{ padding: '0 8px' }}>
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <span><strong>Filters</strong></span>
          <DatePicker placeholder="From" value={startDate} onChange={setStartDate} />
          <DatePicker placeholder="To" value={endDate} onChange={setEndDate} />
          <Select
            value={viewMode}
            onChange={setViewMode}
            options={viewModes}
            style={{ width: 140 }}
          />
        </div>
        
        <div style={{ marginTop: 16 }}>
          <div style={{ marginBottom: 8 }}>
            <strong>Chọn các chi phí để tính Profit:</strong>
          </div>
          <Select
            mode="multiple"
            allowClear
            placeholder="Chọn các chi phí trừ khỏi Revenue"
            value={selectedExpenseItems}
            onChange={setSelectedExpenseItems}
            options={ALL_EXPENSE_OPTIONS}
            style={{ width: '100%' }}
            maxTagCount="responsive"
            optionFilterProp="label"
          />
        </div>
        
      </Card>

      <Card title="Profit & Loss Summary Table" size="small">
        <Spin spinning={loading}>
          <div className="pl-table-wrapper">
            <Table
              className="pl-table"
              columns={columns}
              dataSource={rows}
              pagination={false}
              scroll={{ x: 'max-content' }}
              size="small"
              rowClassName={getRowClassName}
            />
          </div>
        </Spin>
      </Card>
    </div>
  );
}
