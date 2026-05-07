import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Card, Upload, Button, message, Space, Typography, Alert, Table, Input, Spin, Select, Modal, Form, InputNumber, DatePicker, Popconfirm, Tooltip } from 'antd';
import { UploadOutlined, BankOutlined, CheckCircleOutlined, SearchOutlined, ClearOutlined, PlusOutlined, ReloadOutlined, SettingOutlined, EditOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';
import { fetchBankTransactions, fetchBankTransactionsCount, uploadBankTransactions, importBankTransactionRow, deleteBankTransactions, updateBankTransaction, fetchPlAccounts, createPlAccount, updatePlAccount, deletePlAccount } from '../api/staticDataApi';
import { useCurrency } from '../contexts/CurrencyContext';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { Search } = Input;

const DATE_FORMAT = 'YYYY-MM-DD';

const EDITABLE_COLUMNS = new Set([
  'transaction_date',
  'reference_number',
  'account_number',
  'account_name',
  'transaction_description',
  'pl_account_number',
  'credit_amount',
  'debit_amount',
  'balance',
]);

function validateField(field, value) {
  if (value === null || value === undefined || value === '') {
    if (field === 'transaction_date' || field === 'reference_number' || field === 'account_number') {
      return 'Required';
    }
    return null;
  }

  if (field === 'transaction_date') {
    if (value && !dayjs(value, DATE_FORMAT, true).isValid() && !dayjs.isDayjs(value)) {
      return 'Invalid date (YYYY-MM-DD)';
    }
    return null;
  }

  if (field === 'credit_amount' || field === 'debit_amount' || field === 'balance') {
    const num = Number(value);
    if (isNaN(num)) return 'Must be a number';
    return null;
  }

  return null;
}

function EditableCell({
  editing,
  dataIndex,
  record,
  children,
  onSave,
  onCancel,
  inputRef,
  ...restProps
}) {
  const getValueFromInput = useCallback(() => {
    const input = inputRef?.current;
    if (!input) return { value: undefined, valid: false };

    if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
      return { value: input.value, valid: true };
    }

    return { value: undefined, valid: false };
  }, [inputRef]);

  const triggerSave = useCallback(() => {
    const { value: rawValue, valid } = getValueFromInput();
    if (!valid) return;

    let value = rawValue;
    const error = validateField(dataIndex, value);
    if (error) {
      message.error(`${dataIndex}: ${error}`);
      return;
    }

    let oldValue = record[dataIndex];
    if (dataIndex === 'transaction_date') {
      if (value === (oldValue || '')) { onCancel(); return; }
    } else if (dataIndex === 'credit_amount' || dataIndex === 'debit_amount' || dataIndex === 'balance') {
      const oldNum = oldValue != null ? Number(oldValue) : 0;
      const newNum = value === '' ? 0 : Number(value);
      if (oldNum === newNum) { onCancel(); return; }
      value = newNum;
    } else {
      if (value === (oldValue || '')) { onCancel(); return; }
    }

    onSave(record, dataIndex, value);
  }, [dataIndex, record, onSave, onCancel, getValueFromInput]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      triggerSave();
    }
    if (e.key === 'Escape') {
      onCancel();
    }
  }, [triggerSave, onCancel]);

  if (!editing || !EDITABLE_COLUMNS.has(dataIndex)) {
    return <td {...restProps}>{children}</td>;
  }

  const isDate = dataIndex === 'transaction_date';
  const isNumber = dataIndex === 'credit_amount' || dataIndex === 'debit_amount' || dataIndex === 'balance';
  const isLongText = dataIndex === 'transaction_description';

  let inputNode;
  const currentValue = record[dataIndex];

  if (isDate) {
    inputNode = (
      <DatePicker
        ref={inputRef}
        size="small"
        defaultValue={currentValue ? dayjs(currentValue) : null}
        format={DATE_FORMAT}
        style={{ width: '100%' }}
        onChange={triggerSave}
        open
        getPopupContainer={(trigger) => trigger.parentElement}
        onKeyDown={handleKeyDown}
      />
    );
  } else if (isNumber) {
    inputNode = (
      <InputNumber
        ref={inputRef}
        size="small"
        defaultValue={currentValue != null ? currentValue : 0}
        style={{ width: '100%' }}
        onKeyDown={handleKeyDown}
        min={0}
        step={1000}
      />
    );
  } else if (isLongText) {
    inputNode = (
      <Input.TextArea
        ref={inputRef}
        size="small"
        defaultValue={currentValue || ''}
        autoSize={{ minRows: 1, maxRows: 4 }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            triggerSave();
          }
          if (e.key === 'Escape') onCancel();
        }}
      />
    );
  } else {
    inputNode = (
      <Input
        ref={inputRef}
        size="small"
        defaultValue={currentValue || ''}
        onKeyDown={handleKeyDown}
      />
    );
  }

  return (
    <td {...restProps}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <div style={{ flex: 1 }}>{inputNode}</div>
        <Space size={2} style={{ flexShrink: 0 }}>
          <Button
            type="link"
            size="small"
            icon={<CheckOutlined />}
            style={{ color: '#52c41a', padding: '0 2px', minWidth: 18, height: 18 }}
            onClick={(e) => {
              e.stopPropagation();
              triggerSave();
            }}
          />
          <Button
            type="link"
            size="small"
            icon={<CloseOutlined />}
            style={{ color: '#ff4d4f', padding: '0 2px', minWidth: 18, height: 18 }}
            onClick={(e) => {
              e.stopPropagation();
              onCancel();
            }}
          />
        </Space>
      </div>
    </td>
  );
}

export default function BankAccount() {
  const { fmt, currency } = useCurrency();
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ data: [], total: 0 });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [searchText, setSearchText] = useState('');
  const [sortColumn, setSortColumn] = useState(null);
  const [sortOrder, setSortOrder] = useState('desc');
  const [totalCount, setTotalCount] = useState(0);
  const [accountNumber, setAccountNumber] = useState(null);
  const [dateFrom, setDateFrom] = useState(null);
  const [dateTo, setDateTo] = useState(null);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [form] = Form.useForm();

  const [editingKey, setEditingKey] = useState(null);
  const [editingColumn, setEditingColumn] = useState(null);
  const inputRef = useRef(null);

  const isEditing = useCallback((record, column) => {
    return record.bank_transaction_key === editingKey && column === editingColumn;
  }, [editingKey, editingColumn]);

  const startEditing = useCallback((record, column) => {
    setEditingKey(record.bank_transaction_key);
    setEditingColumn(column);
    setTimeout(() => {
      inputRef.current?.focus?.();
    }, 50);
  }, []);

  const cancelEditing = useCallback(() => {
    setEditingKey(null);
    setEditingColumn(null);
  }, []);

  const saveCell = useCallback(async (record, dataIndex, newValue) => {
    const key = record.bank_transaction_key;

    let apiValue = newValue;
    if (dataIndex === 'transaction_date') {
      if (dayjs.isDayjs(newValue)) {
        apiValue = newValue.format(DATE_FORMAT);
      }
    }

    try {
      await updateBankTransaction(key, { [dataIndex]: apiValue });
      message.success('Updated');
      setData(prev => ({
        ...prev,
        data: prev.data.map(row =>
          row.bank_transaction_key === key ? { ...row, [dataIndex]: newValue } : row
        ),
      }));
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Update failed');
      loadData();
    } finally {
      setEditingKey(null);
      setEditingColumn(null);
    }
  }, []);

  // PL Account Config modal state
  const [plAccountsVisible, setPlAccountsVisible] = useState(false);
  const [plAccounts, setPlAccounts] = useState([]);
  const [plAccountsLoading, setPlAccountsLoading] = useState(false);
  const [addAccountForm] = Form.useForm();
  const [addingAccount, setAddingAccount] = useState(false);

  useEffect(() => {
    loadCount();
    loadData();
  }, [page, pageSize, searchText, sortColumn, sortOrder, accountNumber, dateFrom, dateTo]);

  const loadCount = async () => {
    try {
      const result = await fetchBankTransactionsCount(
        accountNumber || undefined,
        dateFrom ? dateFrom.format('YYYY-MM-DD') : undefined,
        dateTo ? dateTo.format('YYYY-MM-DD') : undefined,
      );
      setTotalCount(result.total || 0);
    } catch (error) {
      console.error('Failed to load count:', error);
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const result = await fetchBankTransactions({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        search: searchText || undefined,
        sort_by: sortColumn || undefined,
        sort_order: sortOrder,
        account_number: accountNumber || undefined,
        date_from: dateFrom ? dateFrom.format('YYYY-MM-DD') : undefined,
        date_to: dateTo ? dateTo.format('YYYY-MM-DD') : undefined,
      });
      setData({ data: result.data || [], total: result.total || 0 });
    } catch (error) {
      message.error('Không tải được dữ liệu: ' + (error?.response?.data?.detail || error.message));
      setData({ data: [], total: 0 });
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (file) => {
    setUploading(true);
    try {
      const result = await uploadBankTransactions(file);
      if (result.ok) {
        message.success(`Đã import ${result.imported} dòng từ file ${file.name}`);
        if (result.errors && result.errors.length > 0) {
          message.warning(`${result.errors.length} dòng có lỗi`);
        }
        loadCount();
        loadData();
      } else {
        const msg = result.message || 'Upload thất bại';
        message.error(msg);
        Modal.error({
          title: 'Upload thất bại',
          content: (
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 400, overflow: 'auto' }}>
              {msg}
            </pre>
          ),
          width: 800,
        });
      }
    } catch (error) {
      const detail = error?.response?.data?.detail || error.message;
      const isDuplicate =
        typeof detail === 'string' &&
        detail.includes('Duplicate bank transactions detected');
      if (isDuplicate) {
        message.error('Upload thất bại: duplicate. Có thể file sao kê này đã được import trước đó.');
      } else {
        const fullMessage = 'Upload thất bại: ' + detail;
        message.error(fullMessage);
        Modal.error({
          title: 'Upload thất bại',
          content: (
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 400, overflow: 'auto' }}>
              {fullMessage}
            </pre>
          ),
          width: 800,
        });
      }
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleImportRow = async () => {
    try {
      const values = await form.validateFields();
      setImporting(true);

      const rowData = {
        ...values,
        transaction_date: values.transaction_date ? values.transaction_date.format('YYYY-MM-DD') : null,
        opening_date: values.opening_date ? values.opening_date.format('YYYY-MM-DD') : null,
      };

      const result = await importBankTransactionRow(rowData);
      if (result.ok) {
        message.success(result.message || 'Đã import thành công');
        setImportModalVisible(false);
        form.resetFields();
        loadCount();
        loadData();
      }
    } catch (error) {
      if (error.errorFields) {
        return;
      }
      const detail = error?.response?.data?.detail || error.message;
      const fullMessage = 'Import thất bại: ' + detail;
      message.error(fullMessage);
      Modal.error({
        title: 'Import thất bại',
        content: (
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 400, overflow: 'auto' }}>
            {fullMessage}
          </pre>
        ),
        width: 800,
      });
    } finally {
      setImporting(false);
    }
  };

  const handleSearch = (value) => {
    setSearchText(value);
    setPage(1);
  };

  const handleSortChange = (column) => {
    if (sortColumn === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const clearFilters = () => {
    setSearchText('');
    setSortColumn(null);
    setSortOrder('desc');
    setAccountNumber(null);
    setDateFrom(null);
    setDateTo(null);
    setPage(1);
  };

  const accountNumbers = useMemo(() => {
    const accounts = new Set();
    data.data.forEach(row => {
      if (row.account_number) accounts.add(row.account_number);
    });
    return Array.from(accounts).sort();
  }, [data.data]);

  const mergedColumns = useMemo(() => {
    const baseColumns = [
      {
        title: 'Ngày GD',
        dataIndex: 'transaction_date',
        key: 'transaction_date',
        width: 110,
        sorter: true,
        sortOrder: sortColumn === 'transaction_date' ? sortOrder : null,
        onHeaderCell: () => ({
          onClick: () => handleSortChange('transaction_date'),
          style: { cursor: 'pointer', userSelect: 'none' },
        }),
        editable: true,
        render: (text, record) => {
          const editing = isEditing(record, 'transaction_date');
          return editing ? text : (
            <span
              onDoubleClick={() => startEditing(record, 'transaction_date')}
              style={{ cursor: 'pointer' }}
            >
              {text || '—'}
            </span>
          );
        },
      },
      {
        title: 'Mã GD',
        dataIndex: 'reference_number',
        key: 'reference_number',
        width: 130,
        editable: true,
        render: (text, record) => {
          const editing = isEditing(record, 'reference_number');
          return editing ? text : (
            <span
              onDoubleClick={() => startEditing(record, 'reference_number')}
              style={{ cursor: 'pointer' }}
            >
              {text || '—'}
            </span>
          );
        },
      },
      {
        title: 'Số TK',
        dataIndex: 'account_number',
        key: 'account_number',
        width: 100,
        editable: true,
        render: (text, record) => {
          const editing = isEditing(record, 'account_number');
          return editing ? text : (
            <span
              onDoubleClick={() => startEditing(record, 'account_number')}
              style={{ cursor: 'pointer' }}
            >
              {text || '—'}
            </span>
          );
        },
      },
      {
        title: 'Tên TK',
        dataIndex: 'account_name',
        key: 'account_name',
        width: 110,
        editable: true,
        render: (text, record) => {
          const editing = isEditing(record, 'account_name');
          return editing ? text : (
            <span
              onDoubleClick={() => startEditing(record, 'account_name')}
              style={{ cursor: 'pointer' }}
            >
              {text || '—'}
            </span>
          );
        },
      },
      {
        title: 'Diễn giải',
        dataIndex: 'transaction_description',
        key: 'transaction_description',
        width: 200,
        editable: true,
        render: (text, record) => {
          const editing = isEditing(record, 'transaction_description');
          return editing ? text : (
            <div
              onDoubleClick={() => startEditing(record, 'transaction_description')}
              style={{ cursor: 'pointer', wordBreak: 'break-word', whiteSpace: 'normal', maxWidth: 200 }}
            >
              {text || '—'}
            </div>
          );
        },
      },
      {
        title: 'PL Account',
        dataIndex: 'pl_account_number',
        key: 'pl_account_number',
        width: 90,
        editable: true,
        render: (text, record) => {
          const editing = isEditing(record, 'pl_account_number');
          return editing ? text : (
            <span
              onDoubleClick={() => startEditing(record, 'pl_account_number')}
              style={{ cursor: 'pointer' }}
            >
              {text || '—'}
            </span>
          );
        },
      },
      {
        title: 'Product Line',
        dataIndex: 'product_line_name',
        key: 'product_line_name',
        width: 100,
        ellipsis: true,
        editable: false,
      },
      {
        title: 'Product',
        dataIndex: 'product_name',
        key: 'product_name',
        width: 100,
        ellipsis: true,
        editable: false,
      },
      {
        title: 'Variant',
        dataIndex: 'variant_name',
        key: 'variant_name',
        width: 90,
        ellipsis: true,
        editable: false,
      },
      {
        title: `Credit (${currency})`,
        dataIndex: 'credit_amount',
        key: 'credit_amount',
        width: 120,
        align: 'right',
        editable: true,
        render: (v, record) => {
          const editing = isEditing(record, 'credit_amount');
          return editing ? v : (
            <span
              onDoubleClick={() => startEditing(record, 'credit_amount')}
              style={{ cursor: 'pointer' }}
            >
              {v != null ? fmt(v) : '—'}
            </span>
          );
        },
      },
      {
        title: `Debit (${currency})`,
        dataIndex: 'debit_amount',
        key: 'debit_amount',
        width: 120,
        align: 'right',
        editable: true,
        render: (v, record) => {
          const editing = isEditing(record, 'debit_amount');
          return editing ? v : (
            <span
              onDoubleClick={() => startEditing(record, 'debit_amount')}
              style={{ cursor: 'pointer' }}
            >
              {v != null ? fmt(v) : '—'}
            </span>
          );
        },
      },
      {
        title: `Balance (${currency})`,
        dataIndex: 'balance',
        key: 'balance',
        width: 130,
        align: 'right',
        editable: true,
        render: (v, record) => {
          const editing = isEditing(record, 'balance');
          return editing ? v : (
            <span
              onDoubleClick={() => startEditing(record, 'balance')}
              style={{ cursor: 'pointer' }}
            >
              {v != null ? fmt(v) : '—'}
            </span>
          );
        },
      },
    ];

    return baseColumns.map(col => {
      if (!col.editable) {
        return {
          ...col,
          title: (
            <Space>
              <span>{col.title}</span>
              {col.sortOrder && (
                <span style={{ fontSize: 10, color: '#1890ff' }}>
                  {col.sortOrder === 'asc' ? '↑' : '↓'}
                </span>
              )}
            </Space>
          ),
        };
      }

      return {
        ...col,
        onCell: (record) => ({
          record,
          dataIndex: col.dataIndex,
          editing: isEditing(record, col.dataIndex),
          onSave: saveCell,
          onCancel: cancelEditing,
          inputRef,
        }),
        title: (
          <Space>
            <span>{col.title}</span>
            {col.sortOrder && (
              <span style={{ fontSize: 10, color: '#1890ff' }}>
                {col.sortOrder === 'asc' ? '↑' : '↓'}
              </span>
            )}
            <EditOutlined style={{ fontSize: 10, color: '#bbb' }} />
          </Space>
        ),
      };
    });
  }, [sortColumn, sortOrder, fmt, currency, editingKey, editingColumn, startEditing, isEditing, saveCell, cancelEditing]);

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys) => setSelectedRowKeys(keys),
  };

  // PL Account Config handlers
  const loadPlAccounts = async () => {
    setPlAccountsLoading(true);
    try {
      const result = await fetchPlAccounts();
      setPlAccounts(result.data || []);
    } catch (e) {
      message.error('Failed to load PL account config');
    } finally {
      setPlAccountsLoading(false);
    }
  };

  const handleOpenPlAccounts = () => {
    setPlAccountsVisible(true);
    loadPlAccounts();
  };

  const handleChangeCategory = async (accountNumber, category) => {
    try {
      await updatePlAccount(accountNumber, { category });
      setPlAccounts(prev =>
        prev.map(a => a.account_number === accountNumber ? { ...a, category } : a)
      );
    } catch (e) {
      message.error('Failed to update category');
    }
  };

  const handleChangeAccountNumber = async (oldNumber, newNumber) => {
    const trimmed = newNumber.trim();
    if (!trimmed || trimmed === oldNumber) return;
    try {
      await updatePlAccount(oldNumber, { account_number: trimmed });
      setPlAccounts(prev =>
        prev.map(a => a.account_number === oldNumber ? { ...a, account_number: trimmed } : a)
      );
      message.success(`Renamed ${oldNumber} → ${trimmed}`);
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Failed to rename account number');
    }
  };

  const handleChangeDescription = async (accountNumber, description) => {
    try {
      await updatePlAccount(accountNumber, { description });
      setPlAccounts(prev =>
        prev.map(a => a.account_number === accountNumber ? { ...a, description } : a)
      );
    } catch (e) {
      message.error('Failed to update description');
    }
  };

  const handleDeletePlAccount = (accountNumber) => {
    Modal.confirm({
      title: `Delete account ${accountNumber}?`,
      content: 'This will remove it from the P&L account configuration.',
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await deletePlAccount(accountNumber);
          setPlAccounts(prev => prev.filter(a => a.account_number !== accountNumber));
          message.success(`Deleted ${accountNumber}`);
        } catch (e) {
          message.error('Failed to delete account');
        }
      },
    });
  };

  const handleAddAccount = async () => {
    let values;
    try {
      values = await addAccountForm.validateFields();
    } catch {
      return;
    }
    setAddingAccount(true);
    try {
      await createPlAccount(values);
      message.success(`Added ${values.pl_account_number}`);
      addAccountForm.resetFields();
      loadPlAccounts();
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Failed to add account');
    } finally {
      setAddingAccount(false);
    }
  };

  const CATEGORY_OPTIONS = [
    { value: 'COGS',      label: 'COGS' },
    { value: 'EXPENSE',   label: 'EXPENSE' },
    { value: 'REVENUE',   label: 'REVENUE' },
    { value: 'DEDUCTION', label: 'DEDUCTION' },
    { value: 'OTHER',     label: 'OTHER' },
  ];

  const plAccountColumns = [
    {
      title: 'Account No.',
      dataIndex: 'account_number',
      key: 'account_number',
      width: 120,
      render: (num, record) => (
        <Input
          size="small"
          defaultValue={num}
          onBlur={(e) => handleChangeAccountNumber(record.account_number, e.target.value)}
          onPressEnter={(e) => {
            handleChangeAccountNumber(record.account_number, e.target.value);
            e.target.blur();
          }}
        />
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (desc, record) => (
        <Input
          size="small"
          defaultValue={desc}
          onBlur={(e) => {
            if (e.target.value !== desc) {
              handleChangeDescription(record.account_number, e.target.value);
            }
          }}
          onPressEnter={(e) => {
            if (e.target.value !== desc) {
              handleChangeDescription(record.account_number, e.target.value);
              e.target.blur();
            }
          }}
        />
      ),
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      width: 130,
      render: (cat, record) => (
        <Select
          value={cat}
          size="small"
          style={{ width: 115 }}
          onChange={(val) => handleChangeCategory(record.account_number, val)}
          options={CATEGORY_OPTIONS}
        />
      ),
    },
    {
      title: '',
      key: 'action',
      width: 65,
      render: (_, record) => (
        <Button size="small" danger onClick={() => handleDeletePlAccount(record.account_number)}>
          Delete
        </Button>
      ),
    },
  ];

  const handleDeleteSelected = () => {
    if (!selectedRowKeys.length) return;
    Modal.confirm({
      title: 'Xóa giao dịch ngân hàng đã chọn?',
      content: `Bạn sắp xóa ${selectedRowKeys.length.toLocaleString()} dòng khỏi bảng fact_bank_transactions. Hành động này không thể hoàn tác.`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          setLoading(true);
          await deleteBankTransactions(selectedRowKeys);
          message.success(`Đã xóa ${selectedRowKeys.length.toLocaleString()} giao dịch.`);
          setSelectedRowKeys([]);
          loadCount();
          loadData();
        } catch (e) {
          console.error('Delete bank transactions failed', e);
          message.error('Xóa giao dịch thất bại');
        } finally {
          setLoading(false);
        }
      },
    });
  };

  return (
    <div style={{ padding: '0 8px' }}>
      <style>{`
        .bank-table-small .ant-table {
          font-size: 11px;
        }
        .bank-table-small .ant-table-thead > tr > th {
          font-size: 11px;
          padding: 6px 6px;
        }
        .bank-table-small .ant-table-tbody > tr > td {
          font-size: 11px;
          padding: 6px 6px;
        }
        .bank-table-small .ant-pagination {
          font-size: 11px;
          margin: 8px 0;
        }
        .bank-table-small .ant-table-tbody > tr > td {
          word-break: break-word;
        }
        .bank-table-small .ant-table-tbody > tr > td .ant-input,
        .bank-table-small .ant-table-tbody > tr > td .ant-input-number,
        .bank-table-small .ant-table-tbody > tr > td .ant-picker {
          font-size: 11px;
        }
        .bank-table-small .ant-table-tbody > tr > td:hover:not(.ant-table-cell-row-hover) {
          background-color: #fafafa;
        }
      `}</style>
      <Card
        title={
          <Space>
            <BankOutlined />
            <Title level={4} style={{ margin: 0 }}>Bank Account & Transactions</Title>
          </Space>
        }
      >
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Text strong>Tổng số giao dịch: </Text>
              <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#1890ff' }}>
                {totalCount.toLocaleString()}
              </Text>
            </div>
            <Text type="secondary" style={{ fontSize: 11 }}>
              Double-click any editable cell (marked with <EditOutlined style={{ fontSize: 9 }} />) to edit inline. Press Enter to save, Escape to cancel.
            </Text>
          </Space>
        </Card>

        <Card size="small" title="Import Data" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text type="secondary">
              Upload file CSV hoặc Excel (xlsx/xls) hoặc thêm từng dòng vào Bank Transactions. File cần có các cột: Transaction Date, Reference No., Account Number, Account Name, Opening Date, Credit Amount, Debit Amount, Balance, Description.
            </Text>
            <Space wrap>
              <Upload
                accept=".csv,.xlsx,.xls"
                showUploadList={false}
                beforeUpload={handleUpload}
                maxCount={1}
              >
                <Button
                  type="primary"
                  icon={<UploadOutlined />}
                  loading={uploading}
                >
                  Upload CSV / Excel
                </Button>
              </Upload>
              <Button
                type="default"
                icon={<PlusOutlined />}
                onClick={() => setImportModalVisible(true)}
              >
                Thêm từng dòng
              </Button>
            </Space>
          </Space>
        </Card>

        <Card size="small" title="Danh sách Giao dịch Ngân hàng">
          <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <Space wrap>
              <Search
                placeholder="Tìm kiếm theo diễn giải, mã GD, số TK..."
                allowClear
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onSearch={handleSearch}
                style={{ width: 300 }}
                enterButton={<SearchOutlined />}
              />
              <Select
                placeholder="Lọc theo số TK"
                allowClear
                value={accountNumber}
                onChange={setAccountNumber}
                style={{ width: 200 }}
                showSearch
                filterOption={(input, option) =>
                  (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                }
                options={accountNumbers.map(acc => ({ value: acc, label: acc }))}
              />
              <DatePicker
                placeholder="From"
                value={dateFrom}
                onChange={(d) => { setDateFrom(d); setPage(1); }}
              />
              <DatePicker
                placeholder="To"
                value={dateTo}
                onChange={(d) => { setDateTo(d); setPage(1); }}
              />
            </Space>
            <Space>
              <Button
                size="small"
                danger
                disabled={!selectedRowKeys.length}
                onClick={handleDeleteSelected}
              >
                Xóa giao dịch đã chọn
              </Button>
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={() => {
                  loadCount();
                  loadData();
                  message.success('Đã refresh lại dữ liệu Bank Transactions & Product mapping.');
                }}
              >
                Refresh Product Mapping
              </Button>
              <Button
                size="small"
                icon={<SettingOutlined />}
                onClick={handleOpenPlAccounts}
              >
                Config P&L Accounts
              </Button>
              {sortColumn && (
                <span style={{ fontSize: 12, color: '#888' }}>
                  Đang sort theo: <strong>{sortColumn}</strong> ({sortOrder === 'asc' ? 'Tăng dần' : 'Giảm dần'})
                </span>
              )}
              {(searchText || sortColumn || accountNumber || dateFrom || dateTo) && (
                <Button size="small" icon={<ClearOutlined />} onClick={clearFilters}>
                  Xóa bộ lọc
                </Button>
              )}
            </Space>
          </Space>

          <Spin spinning={loading}>
            <Table
              components={{
                body: {
                  cell: EditableCell,
                },
              }}
              columns={mergedColumns}
              dataSource={data.data}
              rowKey="bank_transaction_key"
              rowSelection={rowSelection}
              size="small"
              className="bank-table-small"
              scroll={{ x: 1400 }}
              pagination={{
                current: page,
                pageSize,
                total: data.total,
                showSizeChanger: true,
                showTotal: (t) => `Tổng ${t.toLocaleString()} dòng`,
                pageSizeOptions: ['20', '50', '100', '200'],
              }}
              onChange={(p) => {
                setPage(p.current || 1);
                setPageSize(p.pageSize || 50);
              }}
            />
          </Spin>
        </Card>
      </Card>

      <Modal
        title="Config P&L Accounts"
        open={plAccountsVisible}
        onCancel={() => setPlAccountsVisible(false)}
        footer={null}
        width={780}
      >
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
          Configure which bank P&L account numbers are treated as COGS or EXPENSE in P&L calculations.
          Changes take effect on the next query — no server restart needed.
        </Text>
        <Form form={addAccountForm} layout="inline" style={{ marginBottom: 16, flexWrap: 'wrap', gap: 4 }}>
          <Form.Item
            name="pl_account_number"
            rules={[{ required: true, message: 'Required' }]}
            style={{ marginBottom: 4 }}
          >
            <Input placeholder="Account no." style={{ width: 120 }} />
          </Form.Item>
          <Form.Item
            name="description"
            style={{ marginBottom: 4 }}
          >
            <Input placeholder="Description" style={{ width: 220 }} />
          </Form.Item>
          <Form.Item
            name="category"
            rules={[{ required: true, message: 'Required' }]}
            style={{ marginBottom: 4 }}
          >
            <Select
              placeholder="Category"
              style={{ width: 120 }}
              options={CATEGORY_OPTIONS}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              size="small"
              loading={addingAccount}
              onClick={handleAddAccount}
              icon={<PlusOutlined />}
            >
              Add
            </Button>
          </Form.Item>
        </Form>
        <Spin spinning={plAccountsLoading}>
          <Table
            columns={plAccountColumns}
            dataSource={plAccounts}
            rowKey="account_number"
            size="small"
            pagination={false}
          />
        </Spin>
      </Modal>

      <Modal
        title="Thêm Bank Transaction"
        open={importModalVisible}
        onOk={handleImportRow}
        onCancel={() => {
          setImportModalVisible(false);
          form.resetFields();
        }}
        confirmLoading={importing}
        okText="Thêm"
        cancelText="Hủy"
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="transaction_date"
            label="Ngày GD (Transaction Date)"
            rules={[{ required: true, message: 'Vui lòng chọn ngày giao dịch' }]}
          >
            <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
          </Form.Item>
          <Form.Item
            name="reference_number"
            label="Mã giao dịch (Reference No.)"
            rules={[{ required: true, message: 'Vui lòng nhập mã giao dịch' }]}
          >
            <Input placeholder="Mã giao dịch" />
          </Form.Item>
          <Form.Item
            name="account_number"
            label="Số tài khoản truy vấn (Account Number)"
            rules={[{ required: true, message: 'Vui lòng nhập số tài khoản' }]}
          >
            <Input placeholder="Số tài khoản" />
          </Form.Item>
          <Form.Item
            name="account_name"
            label="Tên tài khoản truy vấn (Account Name)"
          >
            <Input placeholder="Tên tài khoản" />
          </Form.Item>
          <Form.Item
            name="opening_date"
            label="Ngày mở tài khoản (Opening Date)"
          >
            <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
          </Form.Item>
          <Form.Item
            name="credit_amount"
            label="Phát sinh có — Credit Amount (VND)"
          >
            <InputNumber style={{ width: '100%' }} placeholder="0" min={0} />
          </Form.Item>
          <Form.Item
            name="debit_amount"
            label="Phát sinh nợ — Debit Amount (VND)"
          >
            <InputNumber style={{ width: '100%' }} placeholder="0" min={0} />
          </Form.Item>
          <Form.Item
            name="balance_after_transaction"
            label="Số dư — Balance (VND)"
          >
            <InputNumber style={{ width: '100%' }} placeholder="0" min={0} />
          </Form.Item>
          <Form.Item
            name="transaction_description"
            label="Diễn giải (Description)"
          >
            <Input.TextArea rows={3} placeholder="Diễn giải giao dịch (sẽ tự động parse product info nếu có)" />
          </Form.Item>
          <Alert
            message="Lưu ý"
            description="Các cột Product Line, Product ID, Variant ID, PL Account Number sẽ tự động được parse từ Description nếu có format: {Product Line ID}_{Product ID}_{Variant ID} {PL Account Number}"
            type="info"
            showIcon
            style={{ marginTop: 8 }}
          />
        </Form>
      </Modal>
    </div>
  );
}
