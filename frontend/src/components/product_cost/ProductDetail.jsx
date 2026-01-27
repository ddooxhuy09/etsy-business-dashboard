import React, { useEffect, useState } from 'react';
import { Table, Typography, Button, Space, message, Spin } from 'antd';
import { fetchVariants, fetchCogsBreakdown, fetchEtsyFeeBreakdown, fetchMarginBreakdown } from '../../api/productCost';
import { ArrowLeftOutlined, DownOutlined, UpOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

function formatMoney(num) {
    return Number(num || 0).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function formatPercent(num) {
    return `${(Number(num) || 0).toFixed(2)}%`;
}

export default function ProductDetail({ productId, productName, onBack }) {
    const [variants, setVariants] = useState([]);
    const [detailLoading, setDetailLoading] = useState(false);
    const [showCogsDetail, setShowCogsDetail] = useState(false);
    const [cogsDetail, setCogsDetail] = useState([]);
    const [cogsLoading, setCogsLoading] = useState(false);
    const [showEtsyFeeDetail, setShowEtsyFeeDetail] = useState(false);
    const [etsyFeeDetail, setEtsyFeeDetail] = useState([]);
    const [etsyFeeLoading, setEtsyFeeLoading] = useState(false);
    const [showMarginDetail, setShowMarginDetail] = useState(false);
    const [marginDetail, setMarginDetail] = useState([]);
    const [marginLoading, setMarginLoading] = useState(false);

    useEffect(() => {
        if (!productId) return;
        let mounted = true;
        const loadDetail = async () => {
            try {
                setDetailLoading(true);
                const variantsData = await fetchVariants(productId);
                if (mounted) setVariants(variantsData);
            } catch (err) {
                console.error(err);
                message.error('Failed to load product detail');
            } finally {
                if (mounted) setDetailLoading(false);
            }
        };
        loadDetail();
        return () => {
            mounted = false;
        };
    }, [productId]);

    const handleCogsToggle = async () => {
        const next = !showCogsDetail;
        setShowCogsDetail(next);
        if (next && cogsDetail.length === 0 && productId) {
            try {
                setCogsLoading(true);
                const data = await fetchCogsBreakdown(productId);
                setCogsDetail(data);
            } catch (e) {
                console.error(e);
                message.error('Failed to load COGS breakdown');
            } finally {
                setCogsLoading(false);
            }
        }
    };

    const handleEtsyFeeToggle = async () => {
        const next = !showEtsyFeeDetail;
        setShowEtsyFeeDetail(next);
        if (next && etsyFeeDetail.length === 0 && productId) {
            try {
                setEtsyFeeLoading(true);
                const data = await fetchEtsyFeeBreakdown(productId);
                setEtsyFeeDetail(data);
            } catch (e) {
                console.error(e);
                message.error('Failed to load Etsy Fee breakdown');
            } finally {
                setEtsyFeeLoading(false);
            }
        }
    };

    const handleMarginToggle = async () => {
        const next = !showMarginDetail;
        setShowMarginDetail(next);
        if (next && marginDetail.length === 0 && productId) {
            try {
                setMarginLoading(true);
                const data = await fetchMarginBreakdown(productId);
                setMarginDetail(data);
            } catch (e) {
                console.error(e);
                message.error('Failed to load margin breakdown');
            } finally {
                setMarginLoading(false);
            }
        }
    };

    const totals = variants.reduce(
        (acc, v) => ({
            sales: acc.sales + (Number(v.sales) || 0),
            unit: acc.unit + (Number(v.unit) || 0),
            refund: acc.refund + (Number(v.refund) || 0),
            cogs: acc.cogs + (Number(v.cogs) || 0),
            etsy_fee: acc.etsy_fee + (Number(v.etsy_fee) || 0),
            profit: acc.profit + (Number(v.profit) || 0),
            marginNumerator:
                acc.marginNumerator +
                ((Number(v.sales) || 0) - (Number(v.refund) || 0) - (Number(v.cogs) || 0) - (Number(v.etsy_fee) || 0)),
        }),
        { sales: 0, unit: 0, refund: 0, cogs: 0, etsy_fee: 0, profit: 0, marginNumerator: 0 }
    );
    const totalMargin = totals.sales ? (totals.marginNumerator / totals.sales) * 100 : 0;

    const metricsData = [
        { key: 'sales', metric: 'Sales', icon: '💰', total: totals.sales, values: variants.map((v) => v.sales), type: 'revenue' },
        { key: 'unit', metric: 'Units Sold', icon: '📦', total: totals.unit, values: variants.map((v) => v.unit), type: 'count' },
        { key: 'refund', metric: 'Refunds', icon: '↩️', total: totals.refund, values: variants.map((v) => v.refund), type: 'expense' },
        { key: 'cogs', metric: 'COGS', icon: '🏭', total: totals.cogs, values: variants.map((v) => v.cogs), type: 'expense', expandable: true },
        { key: 'etsy_fee', metric: 'Etsy Fees', icon: '🏷️', total: totals.etsy_fee, values: variants.map((v) => v.etsy_fee), type: 'expense', expandable: true },
        { key: 'profit', metric: 'Net Profit', icon: '📈', total: totals.profit, values: variants.map((v) => v.profit), type: 'profit' },
        { key: 'margin', metric: 'Margin %', icon: '📊', total: totalMargin, values: variants.map((v) => v.margin), type: 'percent', expandable: true },
    ];

    const columns = [
        {
            title: 'Metric',
            dataIndex: 'metric',
            width: 220,
            fixed: 'left',
            render: (v, row) => {
                const isCogs = row.key === 'cogs' && row.expandable;
                const isEtsyFee = row.key === 'etsy_fee' && row.expandable;
                const isMargin = row.key === 'margin' && row.expandable;
                return (
                    <div className="metric-cell">
                        <div className="metric-main">
                            <span className="metric-icon">{row.icon}</span>
                            <Text strong className="metric-name">{v}</Text>
                            {isCogs && (
                                <Button type="text" size="small" className="cogs-toggle-btn"
                                    icon={showCogsDetail ? <UpOutlined /> : <DownOutlined />} onClick={handleCogsToggle}>
                                    {showCogsDetail ? 'Hide' : 'Details'}
                                </Button>
                            )}
                            {isEtsyFee && (
                                <Button type="text" size="small" className="cogs-toggle-btn"
                                    icon={showEtsyFeeDetail ? <UpOutlined /> : <DownOutlined />} onClick={handleEtsyFeeToggle}>
                                    {showEtsyFeeDetail ? 'Hide' : 'Details'}
                                </Button>
                            )}
                            {isMargin && (
                                <Button type="text" size="small" className="cogs-toggle-btn"
                                    icon={showMarginDetail ? <UpOutlined /> : <DownOutlined />} onClick={handleMarginToggle}>
                                    {showMarginDetail ? 'Hide' : 'Details'}
                                </Button>
                            )}
                        </div>
                        {isCogs && showCogsDetail && (
                            <div className="cogs-breakdown">
                                {cogsLoading && <div className="cogs-loading"><Spin size="small" /> Loading breakdown...</div>}
                                {!cogsLoading && cogsDetail.map((item, idx) => (
                                    <div key={idx} className="cogs-item">
                                        <span className="cogs-label">{item.label} <span className="cogs-account">({item.pl_account_number})</span></span>
                                        <span className="cogs-amount">${formatMoney(item.amount)}</span>
                                    </div>
                                ))}
                                {!cogsLoading && cogsDetail.length === 0 && <Text className="no-data">No breakdown data available</Text>}
                            </div>
                        )}
                        {isEtsyFee && showEtsyFeeDetail && (
                            <div className="cogs-breakdown">
                                {etsyFeeLoading && <div className="cogs-loading"><Spin size="small" /> Loading breakdown...</div>}
                                {!etsyFeeLoading && etsyFeeDetail.map((item, idx) => (
                                    <div key={idx} className="cogs-item">
                                        <span className="cogs-label">{item.label}</span>
                                        <span className="cogs-amount">${formatMoney(item.amount)}</span>
                                    </div>
                                ))}
                                {!etsyFeeLoading && etsyFeeDetail.length === 0 && <Text className="no-data">No breakdown data available</Text>}
                            </div>
                        )}
                        {isMargin && showMarginDetail && (
                            <div className="cogs-breakdown">
                                {marginLoading && <div className="cogs-loading"><Spin size="small" /> Loading breakdown...</div>}
                                {!marginLoading && marginDetail.map((item, idx) => (
                                    <div key={idx} className="cogs-item">
                                        <span className="cogs-label">Order #{item.order_id}: ({formatPercent(item.sales_percent)} sales)</span>
                                    </div>
                                ))}
                                {!marginLoading && marginDetail.length === 0 && <Text className="no-data">No breakdown data available</Text>}
                            </div>
                        )}
                    </div>
                );
            },
        },
        {
            title: 'Total',
            dataIndex: 'total',
            width: 120,
            align: 'right',
            className: 'total-column',
            render: (val, row) => {
                if (row.key === 'margin') return null;
                const isCount = row.type === 'count';
                const isProfit = row.type === 'profit';
                const isRevenue = row.type === 'revenue';
                const isPercent = row.type === 'percent';
                let className = 'total-value';
                if (isProfit) className += Number(val) >= 0 ? ' positive' : ' negative';
                else if (isRevenue) className += ' positive';
                else if (row.type === 'expense' && Number(val) > 0) className += ' expense';
                else if (isPercent) className += Number(val) >= 0 ? ' positive' : ' negative';
                return <span className={className}>{isCount ? val : isPercent ? formatPercent(val) : `$${formatMoney(val)}`}</span>;
            },
        },
        ...variants.map((v, idx) => ({
            title: <div className="variant-header"><span className="variant-name">{v.variant}</span></div>,
            dataIndex: 'values',
            align: 'right',
            width: 130,
            render: (_, row) => {
                if (row.key === 'margin') return null;
                const val = row.values[idx] ?? 0;
                const isCount = row.type === 'count';
                const isProfit = row.type === 'profit';
                const isRevenue = row.type === 'revenue';
                const isPercent = row.type === 'percent';
                let className = 'variant-value';
                if (isProfit) className += Number(val) >= 0 ? ' positive' : ' negative';
                else if (isRevenue) className += ' positive';
                else if (row.type === 'expense' && Number(val) > 0) className += ' expense';
                else if (isPercent) className += Number(val) >= 0 ? ' positive' : ' negative';
                return <span className={className}>{isCount ? val : isPercent ? formatPercent(val) : `$${formatMoney(val)}`}</span>;
            },
        })),
    ];

    return (
        <div className="product-detail-container">
            <div className="detail-header">
                <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} className="back-button">
                    Back to Products
                </Button>
                <div className="product-info">
                    <Title level={2} className="product-title">{productName || productId}</Title>
                    <Text className="product-id">ID: {productId}</Text>
                </div>
            </div>
            <div className="detail-table-container">
                <Table
                    className="product-detail-table"
                    size="middle"
                    pagination={false}
                    loading={detailLoading}
                    dataSource={metricsData}
                    columns={columns}
                    scroll={{ x: 'max-content' }}
                    rowClassName={(record) => `metric-row metric-row-${record.type}`}
                />
            </div>
        </div>
    );
}
