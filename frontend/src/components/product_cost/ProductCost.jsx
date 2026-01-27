import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Table, Typography, Tag, message, Input, Space } from 'antd';
import { fetchProducts, fetchVariants } from '../../api/productCost';
import { LinkOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

const PRODUCT_LINE_COLORS = {
    default: ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#6366f1'],
};

function formatMoney(num) {
    return Number(num || 0).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function VariantsTable({ productId }) {
    const [loading, setLoading] = useState(false);
    const [rows, setRows] = useState([]);

    useEffect(() => {
        let mounted = true;
        const load = async () => {
            try {
                setLoading(true);
                const data = await fetchVariants(productId);
                if (mounted) setRows(data);
            } catch (err) {
                console.error(err);
                message.error('Failed to load variants');
            } finally {
                if (mounted) setLoading(false);
            }
        };
        load();
        return () => {
            mounted = false;
        };
    }, [productId]);

    const columns = [
        {
            title: 'Variant',
            dataIndex: 'variant',
            className: 'variant-name-cell',
        },
        {
            title: 'COGS',
            dataIndex: 'cogs',
            align: 'right',
            render: (v) => <span className="money-cell">${formatMoney(v)}</span>,
            width: 120,
        },
    ];

    return (
        <Table
            className="variants-table"
            size="small"
            pagination={false}
            loading={loading}
            columns={columns}
            dataSource={rows.map((r, idx) => ({ key: `${productId}-${idx}`, ...r }))}
        />
    );
}

export default function ProductCost() {
    const [loading, setLoading] = useState(false);
    const [rows, setRows] = useState([]);
    const [colorMap, setColorMap] = useState({});
    const [searchText, setSearchText] = useState('');

    useEffect(() => {
        let mounted = true;
        const load = async () => {
            try {
                setLoading(true);
                const data = await fetchProducts();
                if (!mounted) return;
                setRows(data);
                const uniques = [...new Set(data.map((d) => d.product_line_id))];
                const cmap = {};
                uniques.forEach((pl, idx) => {
                    cmap[pl] = PRODUCT_LINE_COLORS.default[idx % PRODUCT_LINE_COLORS.default.length];
                });
                setColorMap(cmap);
            } catch (err) {
                console.error(err);
                message.error('Failed to load products');
            } finally {
                if (mounted) setLoading(false);
            }
        };
        load();
        return () => {
            mounted = false;
        };
    }, []);

    const grouped = useMemo(() => {
        const map = new Map();
        rows.forEach((r) => {
            if (!map.has(r.product_id)) {
                map.set(r.product_id, {
                    ...r,
                    key: r.product_id,
                });
            }
        });
        return Array.from(map.values());
    }, [rows]);

    const filtered = useMemo(() => {
        if (!searchText.trim()) return grouped;
        const query = searchText.trim().toLowerCase();
        return grouped.filter((r) => {
            const name = (r.product_name || '').toLowerCase();
            const id = (r.product_id || '').toLowerCase();
            const line = (r.product_line_id || '').toLowerCase();
            return name.includes(query) || id.includes(query) || line.includes(query);
        });
    }, [grouped, searchText]);

    const columns = [
        {
            title: 'Product Line',
            dataIndex: 'product_line_id',
            width: 130,
            sorter: (a, b) => (a.product_line_id || '').localeCompare(b.product_line_id || ''),
            render: (v) => (
                <Tag
                    className="product-line-tag"
                    style={{
                        backgroundColor: `${colorMap[v]}20`,
                        borderColor: colorMap[v],
                        color: colorMap[v],
                    }}
                >
                    {v}
                </Tag>
            ),
        },
        {
            title: 'Product Name',
            dataIndex: 'product_name',
            ellipsis: true,
            sorter: (a, b) => (a.product_name || '').localeCompare(b.product_name || ''),
            render: (v, record) => {
                const to = `/product-cost?product_id=${encodeURIComponent(
                    record.product_id || ''
                )}&product_name=${encodeURIComponent(v || '')}`;
                return (
                    <Link to={to} className="product-link">
                        <span className="product-name">{v}</span>
                        <LinkOutlined className="link-icon" />
                    </Link>
                );
            },
        },
        {
            title: 'Product ID',
            dataIndex: 'product_id',
            width: 140,
            className: 'product-id-cell',
            sorter: (a, b) => (a.product_id || '').localeCompare(b.product_id || ''),
        },
        {
            title: 'Sales',
            dataIndex: 'sales',
            align: 'right',
            width: 110,
            sorter: (a, b) => (a.sales || 0) - (b.sales || 0),
            defaultSortOrder: 'descend',
            render: (v) => <span className="money-cell positive">${formatMoney(v)}</span>,
        },
        {
            title: 'Refund',
            dataIndex: 'refund',
            align: 'right',
            width: 100,
            sorter: (a, b) => (a.refund || 0) - (b.refund || 0),
            render: (v) => (
                <span className={`money-cell ${Number(v) > 0 ? 'negative' : ''}`}>
                    ${formatMoney(v)}
                </span>
            ),
        },
        {
            title: 'Units',
            dataIndex: 'unit',
            align: 'center',
            width: 70,
            className: 'unit-cell',
            sorter: (a, b) => (a.unit || 0) - (b.unit || 0),
        },
        {
            title: 'COGS',
            dataIndex: 'cogs',
            align: 'right',
            width: 100,
            sorter: (a, b) => (a.cogs || 0) - (b.cogs || 0),
            render: (v) => <span className="money-cell expense">${formatMoney(v)}</span>,
        },
        {
            title: 'Etsy Fee',
            dataIndex: 'etsy_fee',
            align: 'right',
            width: 100,
            sorter: (a, b) => (a.etsy_fee || 0) - (b.etsy_fee || 0),
            render: (v) => <span className="money-cell expense">${formatMoney(v)}</span>,
        },
        {
            title: 'Profit',
            dataIndex: 'profit',
            align: 'right',
            width: 110,
            sorter: (a, b) => (a.profit || 0) - (b.profit || 0),
            render: (v) => (
                <span className={`money-cell profit ${Number(v) >= 0 ? 'positive' : 'negative'}`}>
                    ${formatMoney(v)}
                </span>
            ),
        },
        {
            title: 'Margin %',
            key: 'margin',
            align: 'right',
            width: 90,
            sorter: (a, b) => {
                const marginA = a.sales > 0 ? (a.profit / a.sales) * 100 : 0;
                const marginB = b.sales > 0 ? (b.profit / b.sales) * 100 : 0;
                return marginA - marginB;
            },
            render: (_, record) => {
                const margin = record.sales > 0 ? (record.profit / record.sales) * 100 : 0;
                return (
                    <span className={`money-cell ${margin >= 0 ? 'positive' : 'negative'}`}>
                        {margin.toFixed(1)}%
                    </span>
                );
            },
        },
    ];

    return (
        <div className="product-cost-container">
            <div className="page-header">
                <div className="page-header-left">
                    <Title level={2} className="page-title">
                        Product Cost Analysis
                    </Title>
                    <Text className="page-subtitle">
                        Track costs, fees, and profitability across all products
                    </Text>
                </div>
                <Space>
                    <Input.Search
                        allowClear
                        placeholder="Search by product name, ID, or line"
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        style={{ width: 280 }}
                    />
                </Space>
            </div>

            <div className="table-container">
                <Table
                    className="product-cost-table"
                    rowKey="key"
                    loading={loading}
                    dataSource={filtered}
                    columns={columns}
                    showSorterTooltip={{ target: 'sorter-icon' }}
                    pagination={{
                        pageSize: 15,
                        showSizeChanger: true,
                        pageSizeOptions: ['10', '15', '25', '50'],
                        showTotal: (total, range) =>
                            `${range[0]}-${range[1]} of ${total} products`,
                    }}
                    expandable={{
                        expandedRowRender: (record) => (
                            <div className="expanded-row-content">
                                <VariantsTable productId={record.product_id} />
                            </div>
                        ),
                        expandRowByClick: false,
                    }}
                    scroll={{ x: 1200 }}
                />
            </div>
        </div>
    );
}
