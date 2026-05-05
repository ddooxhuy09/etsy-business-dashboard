import React, { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Select, Statistic, Spin, Typography, Space } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  DollarOutlined,
  ShoppingCartOutlined,
  UserOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';
import {
  chartsTotalRevenue,
  chartsTotalOrders,
  chartsTotalCustomers,
  chartsAov,
  chartsRevenueByMonth,
  chartsProfitByMonth,
  chartsSalesByProduct,
} from '../api/charts';
import { useCurrency } from '../contexts/CurrencyContext';

const Plot = createPlotlyComponent(Plotly);
const { Title, Text } = Typography;

const YEARS = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);
const MONTHS = [
  { value: 'all', label: 'All months' },
  { value: '1', label: 'January' }, { value: '2', label: 'February' },
  { value: '3', label: 'March' }, { value: '4', label: 'April' },
  { value: '5', label: 'May' }, { value: '6', label: 'June' },
  { value: '7', label: 'July' }, { value: '8', label: 'August' },
  { value: '9', label: 'September' }, { value: '10', label: 'October' },
  { value: '11', label: 'November' }, { value: '12', label: 'December' },
];

function buildDateRange(year, month) {
  if (!year || year === 'all') return { start_date: null, end_date: null };
  const y = Number(year);
  if (!month || month === 'all') return { start_date: `${y}-01-01`, end_date: `${y}-12-31` };
  const m = Number(month);
  const lastDay = new Date(y, m, 0).getDate();
  return {
    start_date: `${y}-${String(m).padStart(2, '0')}-01`,
    end_date: `${y}-${String(m).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`,
  };
}

function buildPrevDateRange(year, month) {
  if (!year || year === 'all') return null;
  const y = Number(year);
  const m = month && month !== 'all' ? Number(month) : null;
  if (!m) {
    return { start_date: `${y - 1}-01-01`, end_date: `${y - 1}-12-31` };
  }
  const prevM = m === 1 ? 12 : m - 1;
  const prevY = m === 1 ? y - 1 : y;
  const lastDay = new Date(prevY, prevM, 0).getDate();
  return {
    start_date: `${prevY}-${String(prevM).padStart(2, '0')}-01`,
    end_date: `${prevY}-${String(prevM).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`,
  };
}

function TrendTag({ current, previous }) {
  if (previous == null || previous === 0) return null;
  const pct = ((current - previous) / Math.abs(previous)) * 100;
  const up = pct >= 0;
  return (
    <span style={{ fontSize: 12, color: up ? '#52c41a' : '#ff4d4f', marginLeft: 4 }}>
      {up ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
      {' '}{Math.abs(pct).toFixed(1)}% MoM
    </span>
  );
}

export default function Overview() {
  const { fmt, convert, currency } = useCurrency();
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [month, setMonth] = useState('all');

  const [kpi, setKpi] = useState({ revenue: null, orders: null, customers: null, aov: null });
  const [prevKpi, setPrevKpi] = useState({ revenue: null, orders: null, customers: null, aov: null });
  const [revenueData, setRevenueData] = useState([]);
  const [profitData, setProfitData] = useState([]);
  const [productData, setProductData] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const f = buildDateRange(year, month);
    const prev = buildPrevDateRange(year, month);

    try {
      const [rev, ord, cust, aov, revByMonth, profByMonth, topProducts] = await Promise.all([
        chartsTotalRevenue(f),
        chartsTotalOrders(f),
        chartsTotalCustomers(f),
        chartsAov(f),
        chartsRevenueByMonth(f),
        chartsProfitByMonth(f),
        chartsSalesByProduct(f),
      ]);

      setKpi({
        revenue: rev?.[0]?.['Total Revenue (USD)'] ?? null,
        orders: ord?.[0]?.['Total Orders'] ?? null,
        customers: cust?.[0]?.['Total Customers'] ?? null,
        aov: aov?.[0]?.['Average Order Value (USD)'] ?? null,
      });
      setRevenueData(Array.isArray(revByMonth) ? revByMonth : []);
      setProfitData(Array.isArray(profByMonth) ? profByMonth : []);
      setProductData(Array.isArray(topProducts) ? topProducts.slice(0, 10) : []);

      if (prev) {
        const [pr, po, pc, pa] = await Promise.all([
          chartsTotalRevenue(prev),
          chartsTotalOrders(prev),
          chartsTotalCustomers(prev),
          chartsAov(prev),
        ]);
        setPrevKpi({
          revenue: pr?.[0]?.['Total Revenue (USD)'] ?? null,
          orders: po?.[0]?.['Total Orders'] ?? null,
          customers: pc?.[0]?.['Total Customers'] ?? null,
          aov: pa?.[0]?.['Average Order Value (USD)'] ?? null,
        });
      } else {
        setPrevKpi({ revenue: null, orders: null, customers: null, aov: null });
      }
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => { load(); }, [load]);

  // Convert chart y-values to current currency
  const revenueY = revenueData.map((r) => convert(r['Revenue (USD)'] ?? r['revenue'] ?? 0));
  const revenueX = revenueData.map((r) => r['Month'] ?? r['month'] ?? '');
  const profitY = profitData.map((r) => convert(r['Profit (USD)'] ?? r['profit'] ?? 0));
  const profitX = profitData.map((r) => r['Month'] ?? r['month'] ?? '');
  const productY = productData.map((r) => convert(r['Revenue (USD)'] ?? r['revenue'] ?? 0));
  const productX = productData.map((r) => r['Product'] ?? r['product'] ?? r['title'] ?? '');

  const currencyLabel = currency === 'USD' ? 'USD ($)' : 'VND (₫)';
  const plotLayout = (title) => ({
    title: { text: title, font: { size: 14 } },
    margin: { t: 40, r: 20, b: 60, l: 70 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    yaxis: { title: currencyLabel, tickformat: currency === 'VND' ? ',.0f' : ',.2f' },
    xaxis: { tickangle: -30 },
    height: 300,
  });

  return (
    <div>
      {/* Filter bar */}
      <Card size="small" style={{ marginBottom: 20 }}>
        <Space>
          <Text strong>Year:</Text>
          <Select
            value={year}
            onChange={setYear}
            options={[{ value: 'all', label: 'All years' }, ...YEARS.map((y) => ({ value: String(y), label: y }))]}
            style={{ width: 130 }}
          />
          <Text strong>Month:</Text>
          <Select
            value={month}
            onChange={setMonth}
            options={MONTHS}
            style={{ width: 140 }}
          />
        </Space>
      </Card>

      <Spin spinning={loading}>
        {/* KPI Cards */}
        <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Total Revenue"
                value={kpi.revenue != null ? fmt(kpi.revenue) : '—'}
                formatter={(v) => v}
                prefix={<DollarOutlined style={{ color: '#1890ff' }} />}
                valueStyle={{ color: '#1890ff', fontSize: 22 }}
              />
              <TrendTag current={kpi.revenue} previous={prevKpi.revenue} />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Total Orders"
                value={kpi.orders ?? '—'}
                prefix={<ShoppingCartOutlined style={{ color: '#52c41a' }} />}
                valueStyle={{ color: '#52c41a', fontSize: 22 }}
              />
              <TrendTag current={kpi.orders} previous={prevKpi.orders} />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Total Customers"
                value={kpi.customers ?? '—'}
                prefix={<UserOutlined style={{ color: '#722ed1' }} />}
                valueStyle={{ color: '#722ed1', fontSize: 22 }}
              />
              <TrendTag current={kpi.customers} previous={prevKpi.customers} />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Avg Order Value"
                value={kpi.aov != null ? fmt(kpi.aov) : '—'}
                formatter={(v) => v}
                prefix={<LineChartOutlined style={{ color: '#fa8c16' }} />}
                valueStyle={{ color: '#fa8c16', fontSize: 22 }}
              />
              <TrendTag current={kpi.aov} previous={prevKpi.aov} />
            </Card>
          </Col>
        </Row>

        {/* Charts row */}
        <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
          <Col xs={24} lg={12}>
            <Card size="small" title="Revenue by Month">
              {revenueX.length > 0 ? (
                <Plot
                  data={[{ x: revenueX, y: revenueY, type: 'bar', marker: { color: '#1890ff' } }]}
                  layout={plotLayout(`Revenue (${currencyLabel})`)}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: '100%' }}
                />
              ) : (
                <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>No data</div>
              )}
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card size="small" title="Profit by Month">
              {profitX.length > 0 ? (
                <Plot
                  data={[{
                    x: profitX,
                    y: profitY,
                    type: 'bar',
                    marker: { color: profitY.map((v) => (v >= 0 ? '#52c41a' : '#ff4d4f')) },
                  }]}
                  layout={plotLayout(`Profit (${currencyLabel})`)}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: '100%' }}
                />
              ) : (
                <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>No data</div>
              )}
            </Card>
          </Col>
        </Row>

        {/* Top products */}
        <Row gutter={[16, 16]}>
          <Col xs={24}>
            <Card size="small" title="Top 10 Products by Revenue">
              {productX.length > 0 ? (
                <Plot
                  data={[{
                    x: productY,
                    y: productX,
                    type: 'bar',
                    orientation: 'h',
                    marker: { color: '#722ed1' },
                  }]}
                  layout={{
                    margin: { t: 20, r: 20, b: 50, l: 200 },
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    xaxis: { title: currencyLabel, tickformat: currency === 'VND' ? ',.0f' : ',.2f' },
                    height: 320,
                  }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: '100%' }}
                />
              ) : (
                <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>No data</div>
              )}
            </Card>
          </Col>
        </Row>
      </Spin>
    </div>
  );
}
