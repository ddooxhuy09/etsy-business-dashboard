import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Tabs, Select, Input, Button, Space, Modal, Form,
  InputNumber, message, Popconfirm, Tag, Typography, Row, Col,
} from 'antd';
import {
  EditOutlined, DeleteOutlined, SearchOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { fetchDataRows, updateDataRow, deleteDataRow } from '../api/dataApi';
import { fetchImportPeriods } from '../api/importApi';
import { useCurrency } from '../contexts/CurrencyContext';
import ImportComponent from './Home';

const { Text } = Typography;

const SOURCE_TABS = [
  { key: 'import', label: 'Import CSV' },
  { key: 'statement', label: 'Statement' },
  { key: 'payments', label: 'Payments' },
  { key: 'listings', label: 'Listings' },
  { key: 'sold-order-items', label: 'Sold Order Items' },
  { key: 'sold-orders', label: 'Sold Orders' },
  { key: 'deposits', label: 'Deposits' },
];

// Columns where the value is a USD amount (will be formatted with currency context)
const AMOUNT_COLS_MAP = {
  statement: ['Amount', 'Fees & Taxes', 'Net'],
  payments: ['Gross', 'Fees', 'Net'],
  listings: ['Price'],
  'sold-order-items': ['Price', 'Discount', 'Item Total', 'Shipping'],
  'sold-orders': ['Order Total', 'Discount', 'Shipping', 'Sales Tax'],
  deposits: ['Amount'],
};

export default function DataExplorer() {
  const { fmt } = useCurrency();

  const [activeTab, setActiveTab] = useState('import');
  const [periods, setPeriods] = useState([]);
  const [period, setPeriod] = useState(null);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);

  const [data, setData] = useState({ rows: [], total: 0, pages: 0 });
  const [loading, setLoading] = useState(false);

  const [editRow, setEditRow] = useState(null);
  const [editLoading, setEditLoading] = useState(false);
  const [form] = Form.useForm();

  // Load periods on mount
  useEffect(() => {
    fetchImportPeriods()
      .then((d) => {
        const ps = d.periods || [];
        setPeriods(ps);
        if (ps.length > 0) setPeriod(ps[ps.length - 1]);
      })
      .catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    if (activeTab === 'import') return;
    setLoading(true);
    try {
      const result = await fetchDataRows(activeTab, { period, search, page, page_size: pageSize });
      setData(result);
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [activeTab, period, search, page, pageSize]);

  useEffect(() => { loadData(); }, [loadData]);

  // Reset page when tab / period / search changes
  useEffect(() => { setPage(1); }, [activeTab, period, search]);

  const handleTabChange = (key) => {
    setActiveTab(key);
    setSearchInput('');
    setSearch('');
  };

  const handleSearch = () => setSearch(searchInput);

  const handleDelete = async (row) => {
    try {
      await deleteDataRow(activeTab, row.id);
      message.success('Row deleted');
      loadData();
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Delete failed');
    }
  };

  const openEdit = (row) => {
    setEditRow(row);
    // Only populate editable fields (exclude id, Period, Date, etc.)
    const formValues = {};
    Object.entries(row).forEach(([k, v]) => {
      if (k !== 'id' && k !== 'Period') formValues[k] = v;
    });
    form.setFieldsValue(formValues);
  };

  const handleEditSave = async () => {
    setEditLoading(true);
    try {
      const values = form.getFieldsValue();
      // Map display col names back to DB col names
      const dbData = mapDisplayToDb(activeTab, values);
      await updateDataRow(activeTab, editRow.id, dbData);
      message.success('Saved');
      setEditRow(null);
      loadData();
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setEditLoading(false);
    }
  };

  // Build table columns dynamically from the first row
  const buildColumns = (rows, source) => {
    if (!rows || rows.length === 0) return [];
    const amountCols = new Set(AMOUNT_COLS_MAP[source] || []);
    const keys = Object.keys(rows[0]).filter((k) => k !== 'id');

    const cols = keys.map((key) => ({
      title: key,
      dataIndex: key,
      key,
      ellipsis: true,
      width: key === 'Title' || key === 'Item Name' || key === 'Info' ? 200 : undefined,
      render: (val) => {
        if (val == null) return <Text type="secondary">—</Text>;
        if (amountCols.has(key)) return <Text>{fmt(val)}</Text>;
        return String(val);
      },
    }));

    // Actions column
    cols.push({
      title: 'Actions',
      key: 'actions',
      fixed: 'right',
      width: 100,
      render: (_, row) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(row)}
          />
          <Popconfirm
            title="Delete this row?"
            onConfirm={() => handleDelete(row)}
            okText="Delete"
            okType="danger"
            cancelText="Cancel"
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    });

    return cols;
  };

  const columns = buildColumns(data.rows, activeTab);

  return (
    <div>
      <Card
        size="small"
        style={{ marginBottom: 16 }}
        title={
          activeTab === 'import' ? <Text strong>Import Data</Text> : (
          <Row gutter={16} align="middle">
            <Col>
              <Text strong>Period:</Text>
            </Col>
            <Col>
              <Select
                value={period}
                onChange={(v) => { setPeriod(v); setPage(1); }}
                options={[
                  { value: null, label: 'All periods' },
                  ...periods.map((p) => ({ value: p, label: p })),
                ]}
                style={{ width: 140 }}
                allowClear
                placeholder="All periods"
              />
            </Col>
            <Col flex="auto">
              <Input
                placeholder="Search..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onPressEnter={handleSearch}
                suffix={<SearchOutlined style={{ color: '#ccc' }} />}
                style={{ maxWidth: 280 }}
              />
            </Col>
            <Col>
              <Space>
                <Button icon={<SearchOutlined />} onClick={handleSearch}>Search</Button>
                <Button icon={<ReloadOutlined />} onClick={loadData} />
              </Space>
            </Col>
          </Row>
          )
        }
      >
        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          items={SOURCE_TABS.map((t) => ({ key: t.key, label: t.label }))}
          size="small"
        />

        {activeTab === 'import' ? (
          <div style={{ margin: '-16px' }}>
            <ImportComponent />
          </div>
        ) : (
          <>
            <div style={{ marginBottom: 8 }}>
              <Text type="secondary">
                {data.total.toLocaleString()} rows
                {period ? ` — period: ${period}` : ''}
              </Text>
            </div>

            <Table
              rowKey="id"
              columns={columns}
              dataSource={data.rows}
              loading={loading}
              pagination={{
                current: page,
                pageSize,
                total: data.total,
                onChange: (p) => setPage(p),
                showSizeChanger: false,
                showTotal: (total, range) => `${range[0]}–${range[1]} of ${total}`,
              }}
              scroll={{ x: 'max-content' }}
              size="small"
              bordered
            />
          </>
        )}
      </Card>

      {/* Edit Modal */}
      <Modal
        title={`Edit row — ${SOURCE_TABS.find((t) => t.key === activeTab)?.label}`}
        open={!!editRow}
        onCancel={() => setEditRow(null)}
        onOk={handleEditSave}
        okText="Save"
        confirmLoading={editLoading}
        width={560}
        destroyOnClose
      >
        {editRow && (
          <Form form={form} layout="vertical" size="small">
            {Object.entries(editRow)
              .filter(([k]) => k !== 'id')
              .map(([key, val]) => {
                const amountCols = AMOUNT_COLS_MAP[activeTab] || [];
                const isAmount = amountCols.includes(key);
                const isReadonly = ['Date', 'Sale Date', 'Listing ID', 'Order ID',
                  'Transaction ID', 'Payment ID', 'Effective Date', 'Created Date'].includes(key);
                return (
                  <Form.Item key={key} name={key} label={key}>
                    {isReadonly ? (
                      <Input disabled />
                    ) : isAmount || typeof val === 'number' ? (
                      <InputNumber style={{ width: '100%' }} />
                    ) : (
                      <Input />
                    )}
                  </Form.Item>
                );
              })}
          </Form>
        )}
      </Modal>
    </div>
  );
}

// Map display column names → DB column names for update payload
function mapDisplayToDb(source, values) {
  const maps = {
    statement: {
      'Type': 'entry_type', 'Title': 'title',
      'Info': 'info', 'Amount': 'amount',
      'Fees & Taxes': 'fees_and_taxes', 'Net': 'net',
    },
    payments: {
      'Gross': 'gross_amount', 'Fees': 'fees', 'Net': 'net_amount', 'Status': 'payment_status',
    },
    listings: {
      'Title': 'title', 'Price': 'price', 'Quantity': 'quantity',
    },
    'sold-order-items': {
      'Quantity': 'quantity_sold', 'Price': 'price', 'Item Total': 'item_total',
    },
    'sold-orders': {
      'Order Type': 'order_type', 'Items': 'number_of_items',
      'Order Total': 'order_total', 'Discount': 'discount_amount',
      'Shipping': 'shipping', 'Coupon': 'coupon_code',
    },
    deposits: { 'Amount': 'deposit_amount', 'Status': 'deposit_status' },
  };

  const colMap = maps[source] || {};
  const result = {};
  Object.entries(values).forEach(([displayKey, val]) => {
    const dbKey = colMap[displayKey];
    if (dbKey) result[dbKey] = val;
  });
  return result;
}
