import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { DatePicker, Select, Spin, Card, Row, Col, Space, Button, Popover } from 'antd';
import { InfoCircleOutlined, SwapOutlined } from '@ant-design/icons';
import createPlotlyComponent from 'react-plotly.js/factory';
import { CHART_ANNOTATIONS } from '../constants/chartAnnotations';
import Plotly from 'plotly.js-dist-min';
import * as ChartsApi from '../api/charts';
import '../styles/charts.css';

const Plot = createPlotlyComponent(Plotly);

const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const EXCHANGE_RATE = 24708.655;

function ChartAnnotationButton({ annotationKey }) {
  const ann = CHART_ANNOTATIONS[annotationKey];
  if (!ann) return null;
  return (
    <Popover content={ann.content} title={ann.title} trigger="click" placement="leftBottom">
      <Button type="text" size="small" icon={<InfoCircleOutlined />} title="Xem công thức tính" style={{ color: '#1890ff' }} />
    </Popover>
  );
}

function toYMD(d) {
  if (!d) return null;
  const v = typeof d?.format === 'function' ? d.format('YYYY-MM-DD') : (typeof d === 'string' ? d : null);
  if (!v || v === 'Invalid Date' || !/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
  return v;
}

function buildResolved(year, month, fromDate, toDate) {
  const sd = toYMD(fromDate);
  const ed = toYMD(toDate);
  if (sd || ed) {
    let start = sd;
    let end = ed;
    if (start && end && start > end) {
      [start, end] = [end, start];
    }
    return { start_date: start || null, end_date: end || null };
  }
  if (year && year !== 'all') {
    const y = Number(year);
    if (month && month !== 'all') {
      const m = Number(month);
      const last = new Date(y, m, 0);
      const lastDay = last.getDate();
      if (lastDay <= 1) {
        return { start_date: null, end_date: null };
      }
      return {
        start_date: `${y}-${String(m).padStart(2, '0')}-01`,
        end_date: `${y}-${String(m).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`,
      };
    }
    return { start_date: `${y}-01-01`, end_date: `${y}-12-31` };
  }
  return { start_date: null, end_date: null };
}

const baseLayout = { plot_bgcolor: '#fafafa', paper_bgcolor: '#fff', height: 360, margin: { t: 40, r: 30, b: 60, l: 60 } };

export default function Charts() {
  const [year, setYear] = useState('all');
  const [month, setMonth] = useState('all');
  const [fromDate, setFromDate] = useState(null);
  const [toDate, setToDate] = useState(null);
  const [customerType, setCustomerType] = useState('all');
  const [currency, setCurrency] = useState('USD');

  // Currency conversion helpers
  const cv = useCallback((val) => {
    if (val == null) return null;
    return currency === 'VND' ? Number(val) * EXCHANGE_RATE : Number(val);
  }, [currency]);
  const sym = currency === 'VND' ? '₫' : '$';
  const fmtMoney = useCallback((val, decimals) => {
    if (val == null) return '—';
    const converted = currency === 'VND' ? Number(val) * EXCHANGE_RATE : Number(val);
    if (currency === 'VND') return `₫${Math.round(converted).toLocaleString('vi-VN')}`;
    const d = decimals != null ? decimals : 2;
    return `$${converted.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
  }, [currency]);
  const curUnit = currency === 'VND' ? 'VND' : 'USD';

  const [m1y, setM1y] = useState(new Date().getFullYear());
  const [m1m, setM1m] = useState(new Date().getMonth() + 1);
  const [m2y, setM2y] = useState(new Date().getFullYear() - 1);
  const [m2m, setM2m] = useState(new Date().getMonth() + 1);

  const resolved = useMemo(() => {
    return { ...buildResolved(year, month, fromDate, toDate), customer_type: customerType };
  }, [year, month, fromDate, toDate, customerType]);

  // KPIs
  const [kpi, setKpi] = useState({ revenue: null, orders: null, customers: null, aov: null });
  const [kpiLoad, setKpiLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setKpiLoad(true);
    Promise.all([
      ChartsApi.chartsTotalRevenue(resolved),
      ChartsApi.chartsTotalOrders(resolved),
      ChartsApi.chartsTotalCustomers(resolved),
      ChartsApi.chartsAov(resolved),
    ])
      .then(([r, o, c, a]) => {
        if (!active) return;
        setKpi({
          revenue: r?.data?.[0]?.['Total Revenue (USD)'],
          orders: o?.data?.[0]?.['Total Orders'],
          customers: c?.data?.[0]?.['Total Customers'],
          aov: a?.data?.[0]?.['AOV (USD)'],
        });
      })
      .catch(() => {
        if (!active) return;
        setKpi({ revenue: null, orders: null, customers: null, aov: null });
      })
      .finally(() => { if (active) setKpiLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Revenue by month
  const [revMonth, setRevMonth] = useState([]);
  const [revLoad, setRevLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setRevLoad(true);
    ChartsApi.chartsRevenueByMonth(resolved)
      .then((r) => { if (active) setRevMonth(r?.data || []); })
      .catch(() => { if (active) setRevMonth([]); })
      .finally(() => { if (active) setRevLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Profit by month
  const [profitMonth, setProfitMonth] = useState([]);
  const [profitLoad, setProfitLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setProfitLoad(true);
    ChartsApi.chartsProfitByMonth(resolved)
      .then((r) => { if (active) setProfitMonth(r?.data || []); })
      .catch(() => { if (active) setProfitMonth([]); })
      .finally(() => { if (active) setProfitLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // New vs Returning
  const [newReturn, setNewReturn] = useState([]);
  const [nrLoad, setNrLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setNrLoad(true);
    ChartsApi.chartsNewVsReturning(resolved)
      .then((r) => { if (active) setNewReturn(r?.data || []); })
      .catch(() => { if (active) setNewReturn([]); })
      .finally(() => { if (active) setNrLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // New customers over time
  const [newCust, setNewCust] = useState([]);
  const [ncLoad, setNcLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setNcLoad(true);
    ChartsApi.chartsNewCustomersOverTime(resolved)
      .then((r) => { if (active) setNewCust(r?.data || []); })
      .catch(() => { if (active) setNewCust([]); })
      .finally(() => { if (active) setNcLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Customers by location
  const [byLoc, setByLoc] = useState([]);
  const [locLoad, setLocLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setLocLoad(true);
    ChartsApi.chartsCustomersByLocation(resolved)
      .then((r) => { if (active) setByLoc(r?.data || []); })
      .catch(() => { if (active) setByLoc([]); })
      .finally(() => { if (active) setLocLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Retention
  const [ret, setRet] = useState(null);
  const [retLoad, setRetLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setRetLoad(true);
    ChartsApi.chartsRetention(resolved)
      .then((r) => { if (active) setRet(r?.data?.[0]?.['Retention Rate (%)']); })
      .catch(() => { if (active) setRet(null); })
      .finally(() => { if (active) setRetLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Sales by product
  const [byProd, setByProd] = useState([]);
  const [prodLoad, setProdLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setProdLoad(true);
    ChartsApi.chartsSalesByProduct(resolved)
      .then((r) => { if (active) setByProd(r?.data || []); })
      .catch(() => { if (active) setByProd([]); })
      .finally(() => { if (active) setProdLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // CAC
  const [cac, setCac] = useState(null);
  const [cacLoad, setCacLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setCacLoad(true);
    ChartsApi.chartsCac(resolved)
      .then((r) => { if (active) setCac(r?.data?.[0]?.['CAC (USD)']); })
      .catch(() => { if (active) setCac(null); })
      .finally(() => { if (active) setCacLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date]);

  // LTV (3 periods: 30, 60, 90 days)
  const [ltv30, setLtv30] = useState(null);
  const [ltv60, setLtv60] = useState(null);
  const [ltv90, setLtv90] = useState(null);
  const [ltvLoad, setLtvLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setLtvLoad(true);
    Promise.all([
      ChartsApi.chartsLtv(resolved, 30),
      ChartsApi.chartsLtv(resolved, 60),
      ChartsApi.chartsLtv(resolved, 90),
    ])
      .then(([r30, r60, r90]) => {
        if (!active) return;
        setLtv30(r30?.data?.[0] || null);
        setLtv60(r60?.data?.[0] || null);
        setLtv90(r90?.data?.[0] || null);
      })
      .catch(() => {
        if (!active) return;
        setLtv30(null); setLtv60(null); setLtv90(null);
      })
      .finally(() => { if (active) setLtvLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // CAC/CLV over time
  const [cacClv, setCacClv] = useState([]);
  const [cacClvLoad, setCacClvLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setCacClvLoad(true);
    ChartsApi.chartsCacClv(resolved)
      .then((r) => { if (active) setCacClv(r?.data || []); })
      .catch(() => { if (active) setCacClv([]); })
      .finally(() => { if (active) setCacClvLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date]);

  // Orders by month
  const [ordMonth, setOrdMonth] = useState([]);
  const [ordLoad, setOrdLoad] = useState(false);

  useEffect(() => {
    let active = true;
    setOrdLoad(true);
    ChartsApi.chartsOrdersByMonth(resolved)
      .then((r) => {
        if (!active) return;
        setOrdMonth(r?.data || []);
      })
      .catch(() => {
        if (!active) return;
        setOrdMonth([]);
      })
      .finally(() => { if (active) setOrdLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // AOV over time
  const [aovTime, setAovTime] = useState([]);
  const [aovLoad, setAovLoad] = useState(false);
  useEffect(() => {
    let active = true;
    setAovLoad(true);
    ChartsApi.chartsAovOverTime(resolved)
      .then((r) => { if (active) setAovTime(r?.data || []); })
      .catch(() => { if (active) setAovTime([]); })
      .finally(() => { if (active) setAovLoad(false); });
    return () => { active = false; };
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Revenue comparison
  const [cmp, setCmp] = useState({ data: [], comparison: {}, month1_name: '', month2_name: '' });
  const [cmpLoad, setCmpLoad] = useState(false);
  useEffect(() => {
    setCmpLoad(true);
    ChartsApi.chartsRevenueComparison(m1y, m1m, m2y, m2m)
      .then(setCmp)
      .catch(() => setCmp({ data: [], comparison: {}, month1_name: '', month2_name: '' }))
      .finally(() => setCmpLoad(false));
  }, [m1y, m1m, m2y, m2m]);

  const yearOpts = ['all', ...Array.from({ length: 8 }, (_, i) => 2020 + i)];
  const compYearOpts = Array.from({ length: 12 }, (_, i) => new Date().getFullYear() - 5 + i);
  const custOpts = [
    { value: 'all', label: 'All Customers' },
    { value: 'new', label: 'New Customers' },
    { value: 'return', label: 'Returning Customers' },
  ];

  const handleYearChange = (v) => {
    setYear(v);
    setFromDate(null);
    setToDate(null);
  };
  const handleMonthChange = (v) => {
    setMonth(v);
    setFromDate(null);
    setToDate(null);
  };
  const handleFromDateChange = (v) => {
    setFromDate(v);
    setYear('all');
    setMonth('all');
  };
  const handleToDateChange = (v) => {
    setToDate(v);
    setYear('all');
    setMonth('all');
  };

  return (
    <div className="charts-page">
      <Card className="charts-filters" size="small">
        <Space wrap size="middle" align="center">
          <Select
            value={year}
            onChange={handleYearChange}
            style={{ width: 120 }}
            options={[{ value: 'all', label: 'All years' }, ...yearOpts.filter((y) => y !== 'all').map((y) => ({ value: String(y), label: String(y) }))]}
          />
          <Select
            value={month}
            onChange={handleMonthChange}
            style={{ width: 140 }}
            options={[{ value: 'all', label: 'All months' }, ...monthNames.map((m, i) => ({ value: String(i + 1), label: m }))]}
          />
          <DatePicker placeholder="From" value={fromDate} onChange={handleFromDateChange} />
          <DatePicker placeholder="To" value={toDate} onChange={handleToDateChange} />
          <Select
            value={customerType}
            onChange={setCustomerType}
            style={{ width: 160 }}
            options={custOpts}
          />
          <Button
            type={currency === 'VND' ? 'primary' : 'default'}
            icon={<SwapOutlined />}
            onClick={() => setCurrency((c) => (c === 'USD' ? 'VND' : 'USD'))}
            style={{ fontWeight: 600 }}
          >
            {currency === 'USD' ? 'USD → VND' : 'VND → USD'}
          </Button>
        </Space>
      </Card>


      <Row gutter={[16, 16]} className="charts-kpi" style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card size="small" className="kpi-card">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="totalRevenue" />
              </div>
              <div className="kpi-label">Doanh thu</div>
            <Spin spinning={kpiLoad}>
              <div className="kpi-value">{fmtMoney(kpi.revenue)}</div>
            </Spin>
              <div className="kpi-sub">Tổng doanh thu ({curUnit})</div>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" className="kpi-card">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="totalOrders" />
              </div>
              <div className="kpi-label">Đơn hàng</div>
            <Spin spinning={kpiLoad}>
              <div className="kpi-value">{kpi.orders != null ? Number(kpi.orders).toLocaleString() : '—'}</div>
            </Spin>
              <div className="kpi-sub">Tổng số đơn hàng</div>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" className="kpi-card">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="totalCustomers" />
              </div>
              <div className="kpi-label">Khách hàng</div>
            <Spin spinning={kpiLoad}>
              <div className="kpi-value">{kpi.customers != null ? Number(kpi.customers).toLocaleString() : '—'}</div>
            </Spin>
              <div className="kpi-sub">Tổng số khách hàng</div>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" className="kpi-card">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="aov" />
              </div>
              <div className="kpi-label">AOV</div>
            <Spin spinning={kpiLoad}>
              <div className="kpi-value">{fmtMoney(kpi.aov)}</div>
            </Spin>
              <div className="kpi-sub">Giá trị đơn hàng trung bình ({curUnit})</div>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="Revenue by Month" className="chart-container">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="revenueByMonth" />
              </div>
              <Spin spinning={revLoad}>
              {revMonth.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: revMonth.map((r) => r.Month), y: revMonth.map((r) => cv(r['Revenue (USD)'])), type: 'bar', name: `Revenue (${curUnit})` }]}
                    layout={{ ...baseLayout, title: `Monthly Revenue (${curUnit})` }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
              </Spin>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Profit by Month" className="chart-container">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="profitByMonth" />
              </div>
              <Spin spinning={profitLoad}>
              {profitMonth.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: profitMonth.map((r) => r.Month), y: profitMonth.map((r) => cv(r['Profit (USD)'])), type: 'bar', name: `Profit (${curUnit})`, marker: { color: '#1890ff' } }]}
                    layout={{ ...baseLayout, title: `Monthly Profit (${curUnit})` }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
              </Spin>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="New vs Returning Customer Sales" className="chart-container">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="newVsReturning" />
              </div>
              <Spin spinning={nrLoad}>
              {newReturn.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ values: newReturn.map((r) => cv(r['Revenue (USD)'])), labels: newReturn.map((r) => r['Customer Type']), type: 'pie', hole: 0.4, marker: { colors: ['#FF6B6B', '#4ECDC4'] } }]}
                    layout={{ ...baseLayout, title: `Revenue by Customer Type (${curUnit})`, showlegend: true }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
              </Spin>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="New Customers Over Time" className="chart-container">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="newCustomersOverTime" />
              </div>
              <Spin spinning={ncLoad}>
              {newCust.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: newCust.map((r) => r.Date), y: newCust.map((r) => r['New Customers']), type: 'scatter', mode: 'lines+markers', name: 'New Customers', line: { color: '#FFA726', width: 2 } }]}
                    layout={{ ...baseLayout, title: 'New Customers Over Time' }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
              </Spin>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="Customers by Location (US States)" className="chart-container" style={{ marginBottom: 16 }}>
        <div style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
            <ChartAnnotationButton annotationKey="customersByLocation" />
          </div>
          <Spin spinning={locLoad}>
          {byLoc.length > 0 ? (
            <div className="plotly-chart-wrapper">
              <Plot
                data={[{ x: byLoc.map((r) => r.State), y: byLoc.map((r) => r.Customers), type: 'bar', name: 'Customers', marker: { color: '#9c27b0' } }]}
                layout={{ ...baseLayout, title: 'Customers by State', xaxis: { tickangle: -45 } }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
              />
            </div>
          ) : (
            <div className="charts-empty">No data</div>
          )}
          </Spin>
        </div>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card title="Customer Retention Rate" className="chart-container">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="retention" />
              </div>
            <Spin spinning={retLoad}>
              <div style={{ textAlign: 'center', padding: '32px 0' }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#1890ff' }}>
                  {ret != null ? `${Number(ret).toFixed(2)}%` : '—'}
                </div>
                <div style={{ fontSize: 12, color: '#999', marginTop: 8 }}>Retention (%)</div>
              </div>
            </Spin>
            </div>
          </Card>
        </Col>
        <Col span={16}>
          <Card title="Top 10 Products by Revenue" className="chart-container">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="salesByProduct" />
              </div>
              <Spin spinning={prodLoad}>
              {byProd.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: byProd.map((r) => cv(r['Revenue (USD)'])), y: byProd.map((r) => r.Product), type: 'bar', orientation: 'h', marker: { color: '#10b981' } }]}
                    layout={{ ...baseLayout, title: `Top 10 by Revenue (${curUnit})`, xaxis: { title: `Revenue (${curUnit})` }, yaxis: { title: '' } }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
              </Spin>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="Customer Acquisition Cost (CAC)" className="chart-container" style={{ marginBottom: 16 }}>
        <div style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
            <ChartAnnotationButton annotationKey="cac" />
          </div>
          <Spin spinning={cacLoad}>
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#9c27b0' }}>
                {fmtMoney(cac)}
              </div>
              <div style={{ fontSize: 12, color: '#999', marginTop: 8 }}>CAC ({curUnit})</div>
            </div>
          </Spin>
        </div>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {[
          { period: 30, data: ltv30, color: '#00bcd4' },
          { period: 60, data: ltv60, color: '#0097a7' },
          { period: 90, data: ltv90, color: '#00796b' },
        ].map(({ period, data, color }) => (
          <Col span={8} key={period}>
            <Card title={`LTV (${period} ngày)`} className="chart-container">
              <div style={{ position: 'relative' }}>
                <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                  <ChartAnnotationButton annotationKey="ltv" />
                </div>
                <Spin spinning={ltvLoad}>
                  <div style={{ textAlign: 'center', padding: '16px 0' }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color }}>
                      {fmtMoney(data?.['LTV (USD)'])}
                    </div>
                    <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>LTV ({curUnit})</div>
                  </div>
                  <Row gutter={8} style={{ marginTop: 8 }}>
                    <Col span={12}>
                      <div style={{ textAlign: 'center', padding: 8, background: '#fafafa', borderRadius: 6 }}>
                        <div style={{ fontSize: 11, color: '#666' }}>AOV</div>
                        <div style={{ fontSize: 16, fontWeight: 600 }}>
                          {fmtMoney(data?.['AOV (USD)'])}
                        </div>
                      </div>
                    </Col>
                    <Col span={12}>
                      <div style={{ textAlign: 'center', padding: 8, background: '#fafafa', borderRadius: 6 }}>
                        <div style={{ fontSize: 11, color: '#666' }}>Avg Freq</div>
                        <div style={{ fontSize: 16, fontWeight: 600 }}>
                          {data?.['Avg Purchase Frequency'] != null ? Number(data['Avg Purchase Frequency']).toFixed(2) : '—'}
                        </div>
                      </div>
                    </Col>
                  </Row>
                </Spin>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Card title="Monthly LTV/CAC Ratio (30d / 60d / 90d)" className="chart-container" style={{ marginBottom: 16 }}>
        <div style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
            <ChartAnnotationButton annotationKey="cacClvRatio" />
          </div>
        <Spin spinning={cacClvLoad}>
          {cacClv.length > 0 ? (
            <div className="plotly-chart-wrapper">
              <Plot
                data={[
                  { x: cacClv.map((r) => r.Month), y: cacClv.map((r) => cv(r['CAC (USD)'])), type: 'bar', name: `CAC (${curUnit})`, marker: { color: '#9C27B0', opacity: 0.5 } },
                  { x: cacClv.map((r) => r.Month), y: cacClv.map((r) => r['LTV(30d)/CAC']), type: 'scatter', mode: 'lines+markers', name: 'LTV(30d)/CAC', yaxis: 'y2', line: { color: '#00bcd4', width: 2 } },
                  { x: cacClv.map((r) => r.Month), y: cacClv.map((r) => r['LTV(60d)/CAC']), type: 'scatter', mode: 'lines+markers', name: 'LTV(60d)/CAC', yaxis: 'y2', line: { color: '#FFA726', width: 2 } },
                  { x: cacClv.map((r) => r.Month), y: cacClv.map((r) => r['LTV(90d)/CAC']), type: 'scatter', mode: 'lines+markers', name: 'LTV(90d)/CAC', yaxis: 'y2', line: { color: '#4CAF50', width: 2 } },
                ]}
                layout={{
                  ...baseLayout,
                  yaxis: { title: `CAC (${curUnit})` },
                  yaxis2: { overlaying: 'y', side: 'right', title: 'LTV/CAC (x)' },
                  legend: { x: 0, y: 1.15, orientation: 'h' },
                }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
              />
            </div>
          ) : (
            <div className="charts-empty">No data</div>
          )}
        </Spin>
        </div>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="Total Orders by Month" className="chart-container">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="ordersByMonth" />
              </div>
            <Spin spinning={ordLoad}>
              {ordMonth.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: ordMonth.map((r) => r.Month), y: ordMonth.map((r) => r.Orders), type: 'bar', marker: { color: '#22c55e' } }]}
                    layout={{ ...baseLayout, title: 'Orders by Month' }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
              </Spin>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Average Order Value Over Time" className="chart-container">
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
                <ChartAnnotationButton annotationKey="aovOverTime" />
              </div>
            <Spin spinning={aovLoad}>
              {aovTime.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: aovTime.map((r) => r.Date), y: aovTime.map((r) => cv(r['AOV (USD)'])), type: 'scatter', mode: 'lines+markers', line: { color: '#FF5722', width: 2 } }]}
                    layout={{ ...baseLayout, title: `AOV Over Time (${curUnit})` }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
              </Spin>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="Revenue Comparison by Month" className="chart-container">
        <div style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', top: 0, right: 0, zIndex: 1 }}>
            <ChartAnnotationButton annotationKey="revenueComparison" />
          </div>
        <Space wrap style={{ marginBottom: 16 }}>
          <Select value={m1y} onChange={setM1y} style={{ width: 100 }} options={compYearOpts.map((y) => ({ value: y, label: String(y) }))} />
          <Select value={m1m} onChange={setM1m} style={{ width: 130 }} options={monthNames.map((m, i) => ({ value: i + 1, label: m }))} />
          <span>vs</span>
          <Select value={m2y} onChange={setM2y} style={{ width: 100 }} options={compYearOpts.map((y) => ({ value: y, label: String(y) }))} />
          <Select value={m2m} onChange={setM2m} style={{ width: 130 }} options={monthNames.map((m, i) => ({ value: i + 1, label: m }))} />
        </Space>
        <Spin spinning={cmpLoad}>
          {cmp.data?.length > 0 ? (
            <>
              <div className="plotly-chart-wrapper" style={{ marginBottom: 16 }}>
                <Plot
                  data={[
                    { x: cmp.data.filter((r) => r.Month === 'Month 1').map((r) => r.Day), y: cmp.data.filter((r) => r.Month === 'Month 1').map((r) => cv(r['Revenue (USD)'])), type: 'scatter', mode: 'lines+markers', name: `${cmp.month1_name}`, line: { color: '#FF6B6B', width: 2 } },
                    { x: cmp.data.filter((r) => r.Month === 'Month 2').map((r) => r.Day), y: cmp.data.filter((r) => r.Month === 'Month 2').map((r) => cv(r['Revenue (USD)'])), type: 'scatter', mode: 'lines+markers', name: `${cmp.month2_name}`, line: { color: '#4ECDC4', width: 2 } },
                  ]}
                  layout={{ ...baseLayout, title: `Daily Revenue Comparison (${curUnit})`, xaxis: { title: 'Day of Month' }, yaxis: { title: `Revenue (${curUnit})` }, legend: { x: 1, y: 1.1, orientation: 'h' } }}
                  config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                />
              </div>
              <Row gutter={16}>
                <Col span={8}>
                  <div style={{ textAlign: 'center', padding: 12, background: '#fafafa', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Order Total %</div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{cmp.comparison?.orders_pct != null ? `${Number(cmp.comparison.orders_pct).toFixed(1)}%` : 'N/A'}</div>
                  </div>
                </Col>
                <Col span={8}>
                  <div style={{ textAlign: 'center', padding: 12, background: '#fafafa', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Revenue %</div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{cmp.comparison?.revenue_pct != null ? `${Number(cmp.comparison.revenue_pct).toFixed(1)}%` : 'N/A'}</div>
                  </div>
                </Col>
                <Col span={8}>
                  <div style={{ textAlign: 'center', padding: 12, background: '#fafafa', borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Profit %</div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{cmp.comparison?.profit_pct != null ? `${Number(cmp.comparison.profit_pct).toFixed(1)}%` : 'N/A'}</div>
                  </div>
                </Col>
              </Row>
            </>
          ) : (
            <div className="charts-empty">No data</div>
          )}
        </Spin>
        </div>
      </Card>
    </div>
  );
}
