import React, { useState, useEffect, useMemo } from 'react';
import { Card, Upload, Button, message, Space, Typography, Alert, Table, Input, Spin, Modal, Form, Select } from 'antd';
import { UploadOutlined, FileTextOutlined, CheckCircleOutlined, SearchOutlined, ClearOutlined, PlusOutlined } from '@ant-design/icons';
import { fetchProductCatalog, fetchProductCatalogCount, uploadProductCatalog, importProductCatalogRow } from '../api/staticDataApi';

const { Title, Text } = Typography;
const { Search } = Input;

export default function ProductCatalog() {
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ data: [], total: 0 });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [searchText, setSearchText] = useState('');
  const [sortColumn, setSortColumn] = useState(null);
  const [sortOrder, setSortOrder] = useState('asc');
  const [totalCount, setTotalCount] = useState(0);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importing, setImporting] = useState(false);
  const [form] = Form.useForm();
  const [productLineFilter, setProductLineFilter] = useState(null);

  useEffect(() => {
    loadCount();
    loadData();
  }, [page, pageSize, searchText, sortColumn, sortOrder, productLineFilter]);

  const loadCount = async () => {
    try {
      const result = await fetchProductCatalogCount();
      setTotalCount(result.total || 0);
    } catch (error) {
      console.error('Failed to load count:', error);
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      // Combine search and product_line filter
      let searchQuery = searchText;
      if (productLineFilter && !searchText) {
        searchQuery = productLineFilter;
      } else if (productLineFilter && searchText) {
        searchQuery = `${searchText} ${productLineFilter}`;
      }

      const result = await fetchProductCatalog({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        search: searchQuery || undefined,
        sort_by: sortColumn || undefined,
        sort_order: sortOrder,
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
      const result = await uploadProductCatalog(file);
      if (result.ok) {
        message.success(`Đã import ${result.imported} dòng từ file ${file.name}`);
        if (result.errors && result.errors.length > 0) {
          message.warning(`${result.errors.length} dòng có lỗi`);
        }
        loadCount();
        loadData();
      } else {
        message.error(result.message || 'Upload thất bại');
      }
    } catch (error) {
      message.error('Upload thất bại: ' + (error?.response?.data?.detail || error.message));
    } finally {
      setUploading(false);
    }
    return false; // Prevent auto upload
  };

  const handleImportRow = async () => {
    try {
      const values = await form.validateFields();
      setImporting(true);
      const result = await importProductCatalogRow(values);
      if (result.ok) {
        message.success(result.message || 'Đã import thành công');
        setImportModalVisible(false);
        form.resetFields();
        loadCount();
        loadData();
      }
    } catch (error) {
      if (error.errorFields) {
        // Form validation errors
        return;
      }
      message.error('Import thất bại: ' + (error?.response?.data?.detail || error.message));
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
      setSortOrder('asc');
    }
    setPage(1);
  };

  const clearFilters = () => {
    setSearchText('');
    setSortColumn(null);
    setSortOrder('asc');
    setProductLineFilter(null);
    setPage(1);
  };

  // Get unique product_line_id for filter
  const productLines = useMemo(() => {
    const lines = new Set();
    data.data.forEach(row => {
      if (row.product_line_id) lines.add(row.product_line_id);
    });
    return Array.from(lines).sort();
  }, [data.data]);

  const columns = useMemo(() => {
    const baseColumns = [
      {
        title: 'Product Line ID',
        dataIndex: 'product_line_id',
        key: 'product_line_id',
        sorter: true,
        sortOrder: sortColumn === 'product_line_id' ? sortOrder : null,
        onHeaderCell: () => ({
          onClick: () => handleSortChange('product_line_id'),
          style: { cursor: 'pointer', userSelect: 'none' },
        }),
      },
      {
        title: 'Product ID',
        dataIndex: 'product_id',
        key: 'product_id',
        sorter: true,
        sortOrder: sortColumn === 'product_id' ? sortOrder : null,
        onHeaderCell: () => ({
          onClick: () => handleSortChange('product_id'),
          style: { cursor: 'pointer', userSelect: 'none' },
        }),
      },
      {
        title: 'Variant ID',
        dataIndex: 'variant_id',
        key: 'variant_id',
        sorter: true,
        sortOrder: sortColumn === 'variant_id' ? sortOrder : null,
        onHeaderCell: () => ({
          onClick: () => handleSortChange('variant_id'),
          style: { cursor: 'pointer', userSelect: 'none' },
        }),
      },
      {
        title: 'Product Line Name',
        dataIndex: 'product_line_name',
        key: 'product_line_name',
        ellipsis: true,
      },
      {
        title: 'Product Name',
        dataIndex: 'product_name',
        key: 'product_name',
        ellipsis: true,
      },
      {
        title: 'Variant Name',
        dataIndex: 'variant_name',
        key: 'variant_name',
        ellipsis: true,
      },
      {
        title: 'Product Code',
        dataIndex: 'product_code',
        key: 'product_code',
        ellipsis: true,
      },
    ];

    return baseColumns.map(col => ({
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
    }));
  }, [sortColumn, sortOrder]);

  return (
    <div style={{ padding: '0 8px' }}>
      <Card
        title={
          <Space>
            <FileTextOutlined />
            <Title level={4} style={{ margin: 0 }}>Product Catalog</Title>
          </Space>
        }
      >
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Text strong>Tổng số sản phẩm trong catalog: </Text>
              <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#1890ff' }}>
                {totalCount.toLocaleString()}
              </Text>
            </div>
          </Space>
        </Card>

        <Card size="small" title="Import Data" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text type="secondary">
              Upload file CSV hoặc thêm từng dòng vào Product Catalog.
            </Text>
            <Space wrap>
              <Upload
                accept=".csv"
                showUploadList={false}
                beforeUpload={handleUpload}
                maxCount={1}
              >
                <Button
                  type="primary"
                  icon={<UploadOutlined />}
                  loading={uploading}
                >
                  Upload CSV File
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

        <Card size="small" title="Danh sách Product Catalog">
          <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <Space wrap>
              <Search
                placeholder="Tìm kiếm theo Product Line ID, Product ID, Variant ID, tên sản phẩm..."
                allowClear
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onSearch={handleSearch}
                style={{ width: 300 }}
                enterButton={<SearchOutlined />}
              />
              <Select
                placeholder="Lọc theo Product Line ID"
                allowClear
                value={productLineFilter}
                onChange={setProductLineFilter}
                style={{ width: 200 }}
                showSearch
                filterOption={(input, option) =>
                  (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                }
                options={productLines.map(pl => ({ value: pl, label: pl }))}
              />
            </Space>
            <Space>
              {sortColumn && (
                <span style={{ fontSize: 12, color: '#888' }}>
                  Đang sort theo: <strong>{sortColumn}</strong> ({sortOrder === 'asc' ? 'Tăng dần' : 'Giảm dần'})
                </span>
              )}
              {(searchText || sortColumn || productLineFilter) && (
                <Button size="small" icon={<ClearOutlined />} onClick={clearFilters}>
                  Xóa bộ lọc
                </Button>
              )}
            </Space>
          </Space>

          <Spin spinning={loading}>
            <Table
              columns={columns}
              dataSource={data.data}
              rowKey="product_catalog_key"
              size="small"
              scroll={{ x: 'max-content' }}
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
        title="Thêm Product Catalog"
        open={importModalVisible}
        onOk={handleImportRow}
        onCancel={() => {
          setImportModalVisible(false);
          form.resetFields();
        }}
        confirmLoading={importing}
        okText="Thêm"
        cancelText="Hủy"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="product_line_id"
            label="Product Line ID"
            rules={[{ required: true, message: 'Vui lòng nhập Product Line ID' }]}
          >
            <Input placeholder="VD: DEF" />
          </Form.Item>
          <Form.Item
            name="product_id"
            label="Product ID"
            rules={[{ required: true, message: 'Vui lòng nhập Product ID' }]}
          >
            <Input placeholder="VD: MG01107417" />
          </Form.Item>
          <Form.Item
            name="variant_id"
            label="Variant ID"
            rules={[{ required: true, message: 'Vui lòng nhập Variant ID' }]}
          >
            <Input placeholder="VD: 03" />
          </Form.Item>
          <Form.Item
            name="product_line_name"
            label="Product Line Name"
          >
            <Input placeholder="Tên product line" />
          </Form.Item>
          <Form.Item
            name="product_name"
            label="Product Name"
          >
            <Input placeholder="Tên sản phẩm" />
          </Form.Item>
          <Form.Item
            name="variant_name"
            label="Variant Name"
          >
            <Input placeholder="Tên variant" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
