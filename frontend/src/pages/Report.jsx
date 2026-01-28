import React, { useState, useEffect, useMemo } from 'react';
import { Card, Table, Button, DatePicker, Spin, message, Descriptions, Space, Input, Select } from 'antd';
import { SearchOutlined, ClearOutlined } from '@ant-design/icons';
import { fetchBankAccounts, fetchBankAccountsCount, fetchBankAccountInfo, fetchAccountStatement, getAccountStatementPdfUrl } from '../api/report';

const { Search } = Input;

function toCSV(arr, columns) {
  if (!arr || !arr.length) return '';
  const cols = columns || Object.keys(arr[0]);
  const row = (r) => cols.map((c) => {
    const v = r[c];
    const s = v != null ? String(v) : '';
    return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(',');
  return [cols.join(','), ...arr.map(row)].join('\r\n');
}

function downloadCSV(data, filename) {
  const blob = new Blob(['\uFEFF' + data], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

const BANK_COLUMNS = [
  { title: 'Account Number', dataIndex: 'Account Number', key: 'Account Number', width: 140 },
  { 
    title: 'Account Name', 
    dataIndex: 'Account Name', 
    key: 'Account Name', 
    width: 200,
    ellipsis: { showTitle: true }  // Hiển thị tooltip khi hover để xem đầy đủ
  },
  { title: 'CIF Number', dataIndex: 'CIF Number', key: 'CIF Number', width: 110 },
  { title: 'Currency', dataIndex: 'Currency', key: 'Currency', width: 80 },
  { title: 'Total Transactions', dataIndex: 'Total Transactions', key: 'Total Transactions', width: 120, align: 'right' },
  { title: 'Total Credit (VND)', dataIndex: 'Total Credit (VND)', key: 'Total Credit (VND)', width: 140, align: 'right', render: (v) => (v != null ? Number(v).toLocaleString() : '—') },
  { title: 'Total Debit (VND)', dataIndex: 'Total Debit (VND)', key: 'Total Debit (VND)', width: 140, align: 'right', render: (v) => (v != null ? Number(v).toLocaleString() : '—') },
  { title: 'Current Balance (VND)', dataIndex: 'Current Balance (VND)', key: 'Current Balance (VND)', width: 150, align: 'right', render: (v) => (v != null ? Number(v).toLocaleString() : '—') },
  { title: 'First Transaction', dataIndex: 'First Transaction Date', key: 'First Transaction Date', width: 120 },
  { title: 'Last Transaction', dataIndex: 'Last Transaction Date', key: 'Last Transaction Date', width: 120 },
];

const STMT_COLUMNS = [
  { title: 'Ngày GD', dataIndex: 'Ngày GD', key: 'Ngày GD', width: 110 },
  { title: 'Mã giao dịch', dataIndex: 'Mã giao dịch', key: 'Mã giao dịch', width: 120 },
  { title: 'Phát sinh có', dataIndex: 'Phát sinh có', key: 'Phát sinh có', width: 120, align: 'right', render: (v) => (v != null ? Number(v).toLocaleString() : '—') },
  { title: 'Phát sinh nợ', dataIndex: 'Phát sinh nợ', key: 'Phát sinh nợ', width: 120, align: 'right', render: (v) => (v != null ? Number(v).toLocaleString() : '—') },
  { title: 'Số dư', dataIndex: 'Số dư', key: 'Số dư', width: 130, align: 'right', render: (v) => (v != null ? Number(v).toLocaleString() : '—') },
  { title: 'Diễn giải', dataIndex: 'Diễn giải', key: 'Diễn giải', ellipsis: true },
];

export default function Report() {
  const [totalCount, setTotalCount] = useState(0);
  const [bankData, setBankData] = useState([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(30);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [showReport, setShowReport] = useState(false);

  // Search and filter for bank accounts
  const [bankSearchText, setBankSearchText] = useState('');
  const [bankCurrencyFilter, setBankCurrencyFilter] = useState(null);

  const [accountInfo, setAccountInfo] = useState(null);
  const [fromDate, setFromDate] = useState(null);
  const [toDate, setToDate] = useState(null);
  const [stmtData, setStmtData] = useState([]);
  const [stmtLoading, setStmtLoading] = useState(false);

  // Search, filter, and pagination for statement
  const [stmtSearchText, setStmtSearchText] = useState('');
  const [stmtPage, setStmtPage] = useState(1);
  const [stmtPageSize, setStmtPageSize] = useState(30);

  // Load all bank accounts (for client-side filtering and pagination)
  useEffect(() => {
    setBankLoading(true);
    // Load with large page size to get all data, or implement a separate endpoint
    fetchBankAccounts({ page: 1, pageSize: 10000 })
      .then((r) => {
        setBankData(r.data || []);
        setTotalCount(r.data?.length || 0);
      })
      .catch(() => message.error('Failed to load bank accounts'))
      .finally(() => setBankLoading(false));
  }, []);

  // When showReport and selectedAccount: fetch account info and statement
  useEffect(() => {
    if (!showReport || !selectedAccount) return;
    fetchBankAccountInfo(selectedAccount).then(setAccountInfo).catch(() => message.error('Failed to load account info'));
  }, [showReport, selectedAccount]);

  useEffect(() => {
    if (!showReport || !selectedAccount) return;
    setStmtLoading(true);
    // Format dates properly - only include if date is set
    const fromDateStr = fromDate && fromDate.format ? fromDate.format('YYYY-MM-DD') : null;
    const toDateStr = toDate && toDate.format ? toDate.format('YYYY-MM-DD') : null;
    fetchAccountStatement({
      account_number: selectedAccount,
      from_date: fromDateStr,
      to_date: toDateStr,
    })
      .then((r) => setStmtData(r.data || []))
      .catch(() => message.error('Failed to load account statement'))
      .finally(() => setStmtLoading(false));
  }, [showReport, selectedAccount, fromDate, toDate]);

  // Filter bank data by search and currency
  const filteredBankData = useMemo(() => {
    let filtered = [...bankData];
    
    // Search filter
    if (bankSearchText) {
      const searchLower = bankSearchText.toLowerCase();
      filtered = filtered.filter((r) => {
        const accountNumber = String(r['Account Number'] || '').toLowerCase();
        const accountName = String(r['Account Name'] || '').toLowerCase();
        return accountNumber.includes(searchLower) || accountName.includes(searchLower);
      });
    }
    
    // Currency filter
    if (bankCurrencyFilter) {
      filtered = filtered.filter((r) => r['Currency'] === bankCurrencyFilter);
    }
    
    return filtered;
  }, [bankData, bankSearchText, bankCurrencyFilter]);

  // Paginate filtered bank data
  const paginatedBankData = useMemo(() => {
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    return filteredBankData.slice(start, end);
  }, [filteredBankData, page, pageSize]);

  const bankRows = useMemo(() => paginatedBankData.map((r, i) => ({ ...r, key: r['Account Number'] || `bank-${i}` })), [paginatedBankData]);
  
  // Get unique currencies for filter
  const currencies = useMemo(() => {
    const unique = [...new Set(bankData.map((r) => r['Currency']).filter(Boolean))];
    return unique.sort();
  }, [bankData]);

  // Filter and paginate statement data
  const filteredStmtData = useMemo(() => {
    let filtered = [...stmtData];
    
    // Search filter
    if (stmtSearchText) {
      const searchLower = stmtSearchText.toLowerCase();
      filtered = filtered.filter((r) => {
        return Object.values(r).some((v) => {
          const str = String(v || '').toLowerCase();
          return str.includes(searchLower);
        });
      });
    }
    
    return filtered;
  }, [stmtData, stmtSearchText]);

  const paginatedStmtData = useMemo(() => {
    const start = (stmtPage - 1) * stmtPageSize;
    const end = start + stmtPageSize;
    return filteredStmtData.slice(start, end);
  }, [filteredStmtData, stmtPage, stmtPageSize]);

  const stmtRows = useMemo(() => paginatedStmtData.map((r, i) => ({ ...r, key: `stmt-${i}` })), [paginatedStmtData]);

  const rowSelection = {
    type: 'radio',
    selectedRowKeys: selectedAccount ? [selectedAccount] : [],
    onChange: (_, selectedRows) => setSelectedAccount(selectedRows[0]?.['Account Number'] || null),
  };

  const pagination = {
    current: page,
    pageSize,
    total: filteredBankData.length, // Use filtered count
    showSizeChanger: true,
    pageSizeOptions: ['10', '25', '30', '50', '100'],
    showTotal: (t) => `Tổng ${t.toLocaleString()} tài khoản`,
    onChange: (p, ps) => {
      setPage(p);
      setPageSize(ps || 30);
    },
  };

  const pdfUrl = selectedAccount
    ? getAccountStatementPdfUrl(selectedAccount, fromDate?.format?.('YYYY-MM-DD'), toDate?.format?.('YYYY-MM-DD'))
    : '';

  return (
    <div style={{ padding: '0 8px', maxWidth: '100%', overflow: 'hidden' }}>
      <style>{`
        .report-table-small .ant-table {
          font-size: 11px;
        }
        .report-table-small .ant-table-thead > tr > th {
          font-size: 11px;
          padding: 6px 6px;
        }
        .report-table-small .ant-table-tbody > tr > td {
          font-size: 11px;
          padding: 6px 6px;
        }
        .report-table-small .ant-pagination {
          font-size: 11px;
          margin: 8px 0;
        }
        .report-compact .ant-card-head {
          padding: 8px 12px;
          min-height: 40px;
        }
        .report-compact .ant-card-head-title {
          font-size: 14px;
          padding: 0;
        }
        .report-compact .ant-card-body {
          padding: 12px;
        }
        .report-compact p {
          font-size: 12px;
          margin-bottom: 8px;
        }
        .report-compact .ant-space {
          margin-bottom: 8px;
        }
        .report-compact .ant-btn {
          font-size: 12px;
          height: 28px;
          padding: 0 12px;
        }
        .report-compact .ant-input-search {
          font-size: 12px;
        }
        .report-compact .ant-select {
          font-size: 12px;
        }
      `}</style>
      <Card title="Account Statement Report" className="report-compact" style={{ marginBottom: 12 }}>
        <p style={{ color: '#666', marginBottom: 8, fontSize: '12px' }}>Chọn tài khoản ngân hàng, bấm Create Report để xem sao kê và tải PDF.</p>

        {/* Search and Filter Controls */}
        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <Search
            placeholder="Tìm kiếm theo số tài khoản hoặc tên..."
            allowClear
            value={bankSearchText}
            onChange={(e) => setBankSearchText(e.target.value)}
            style={{ width: 300 }}
            enterButton={<SearchOutlined />}
          />
          <Space>
            <span>Currency:</span>
            <Select
              placeholder="Tất cả"
              allowClear
              value={bankCurrencyFilter}
              onChange={setBankCurrencyFilter}
              style={{ width: 120 }}
              options={currencies.map((c) => ({ label: c, value: c }))}
            />
            {(bankSearchText || bankCurrencyFilter) && (
              <Button
                size="small"
                icon={<ClearOutlined />}
                onClick={() => {
                  setBankSearchText('');
                  setBankCurrencyFilter(null);
                }}
              >
                Xóa bộ lọc
              </Button>
            )}
          </Space>
        </Space>

        <div style={{ marginBottom: 12 }}>
          <Spin spinning={bankLoading}>
            <Table
              columns={BANK_COLUMNS}
              dataSource={bankRows}
              rowSelection={rowSelection}
              pagination={pagination}
              scroll={{ x: 'max-content', y: 'calc(100vh - 400px)' }}
              size="small"
              className="report-table-small"
            />
          </Spin>
        </div>

        <Space wrap>
          <Button
            type="primary"
            onClick={() => setShowReport(true)}
            disabled={!selectedAccount}
          >
            Create Report
          </Button>
          {selectedAccount && <span style={{ color: '#666' }}>Selected: {selectedAccount}</span>}
            <Button
              onClick={() => {
                // Export filtered data
                const csv = toCSV(filteredBankData, BANK_COLUMNS.map((c) => c.dataIndex).filter(Boolean));
                downloadCSV(csv, `bank_accounts_${new Date().toISOString().slice(0, 10)}.csv`);
              }}
              disabled={!filteredBankData.length}
            >
              Download Bank Accounts CSV
            </Button>
        </Space>
      </Card>

      {showReport && selectedAccount && (
        <Card
          title="Sao kê tài khoản / Account Statement"
          className="report-compact"
          extra={<Button size="small" onClick={() => setShowReport(false)}>Close</Button>}
          style={{ marginBottom: 12 }}
        >
          {accountInfo && (
            <Descriptions size="small" column={2} style={{ marginBottom: 16 }} bordered>
              <Descriptions.Item label="Số tài khoản">{accountInfo.account_number}</Descriptions.Item>
              <Descriptions.Item label="Loại tiền">{accountInfo.currency_code}</Descriptions.Item>
              <Descriptions.Item label="Tên tài khoản">{accountInfo.account_name}</Descriptions.Item>
              <Descriptions.Item label="CIF Number">{accountInfo.cif_number}</Descriptions.Item>
              <Descriptions.Item label="Ngày mở tài khoản">{accountInfo.opening_date}</Descriptions.Item>
              <Descriptions.Item label="Địa chỉ" span={2}>{accountInfo.customer_address}</Descriptions.Item>
            </Descriptions>
          )}

          <Space wrap style={{ marginBottom: 16 }}>
            <span>Từ ngày:</span>
            <DatePicker value={fromDate} onChange={setFromDate} />
            <span>Đến ngày:</span>
            <DatePicker value={toDate} onChange={setToDate} />
          </Space>

          {/* Search for Statement */}
          <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <Search
              placeholder="Tìm kiếm trong sao kê..."
              allowClear
              value={stmtSearchText}
              onChange={(e) => {
                setStmtSearchText(e.target.value);
                setStmtPage(1);
              }}
              style={{ width: 300 }}
              enterButton={<SearchOutlined />}
            />
            {stmtSearchText && (
              <Button
                size="small"
                icon={<ClearOutlined />}
                onClick={() => {
                  setStmtSearchText('');
                  setStmtPage(1);
                }}
              >
                Xóa tìm kiếm
              </Button>
            )}
          </Space>

          <Spin spinning={stmtLoading}>
            <Table
              columns={STMT_COLUMNS}
              dataSource={stmtRows}
              scroll={{ x: 900 }}
              size="small"
              pagination={{
                current: stmtPage,
                pageSize: stmtPageSize,
                total: filteredStmtData.length,
                showSizeChanger: true,
                showTotal: (t) => `Tổng ${t.toLocaleString()} giao dịch`,
                pageSizeOptions: ['20', '30', '50', '100'],
                onChange: (p, ps) => {
                  setStmtPage(p);
                  setStmtPageSize(ps || 30);
                },
              }}
              style={{ marginBottom: 16, fontSize: '12px' }}
              className="report-table-small"
            />
          </Spin>

          <Space wrap>
            <Button
              onClick={() => {
                const cols = ['Ngày GD', 'Mã giao dịch', 'Số tài khoản truy vấn', 'Tên tài khoản truy vấn', 'Ngày mở tài khoản', 'Phát sinh có', 'Phát sinh nợ', 'Số dư', 'Diễn giải'];
                downloadCSV(toCSV(stmtData, cols), `account_statement_${selectedAccount}_${new Date().toISOString().slice(0, 10)}.csv`);
              }}
              disabled={!stmtData.length}
            >
              Download CSV
            </Button>
            <Button type="primary" href={pdfUrl} target="_blank" rel="noopener noreferrer">
              Download PDF
            </Button>
          </Space>
        </Card>
      )}
    </div>
  );
}
