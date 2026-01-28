import React, { useState, useMemo, useEffect } from 'react';
import { DatePicker, Select, InputNumber, Spin, Card, Row, Col, Space } from 'antd';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';
import * as ChartsApi from '../api/charts';
import '../styles/charts.css';

const Plot = createPlotlyComponent(Plotly);

const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function toYMD(d) {
  if (!d) return null;
  const v = typeof d?.format === 'function' ? d.format('YYYY-MM-DD') : d;
  return v || null;
}

function buildResolved(year, month, fromDate, toDate) {
  if (fromDate || toDate) {
    return { start_date: toYMD(fromDate), end_date: toYMD(toDate) };
  }
  if (year && year !== 'all') {
    const y = Number(year);
    if (month && month !== 'all') {
      const m = Number(month);
      const last = new Date(y, m, 0);
      return {
        start_date: `${y}-${String(m).padStart(2, '0')}-01`,
        end_date: `${y}-${String(m).padStart(2, '0')}-${String(last.getDate()).padStart(2, '0')}`,
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
  const [lifespan, setLifespan] = useState(12);
  const [m1y, setM1y] = useState(new Date().getFullYear());
  const [m1m, setM1m] = useState(new Date().getMonth() + 1);
  const [m2y, setM2y] = useState(new Date().getFullYear() - 1);
  const [m2m, setM2m] = useState(new Date().getMonth() + 1);

  const resolved = useMemo(
    () => ({ ...buildResolved(year, month, fromDate, toDate), customer_type: customerType, customer_lifespan_months: lifespan }),
    [year, month, fromDate, toDate, customerType, lifespan]
  );

  // KPIs
  const [kpi, setKpi] = useState({ revenue: null, orders: null, customers: null, aov: null });
  const [kpiLoad, setKpiLoad] = useState(false);
  useEffect(() => {
    setKpiLoad(true);
    Promise.all([
      ChartsApi.chartsTotalRevenue(resolved),
      ChartsApi.chartsTotalOrders(resolved),
      ChartsApi.chartsTotalCustomers(resolved),
      ChartsApi.chartsAov(resolved),
    ])
      .then(([r, o, c, a]) => {
        setKpi({
          revenue: r?.data?.[0]?.['Total Revenue (USD)'],
          orders: o?.data?.[0]?.['Total Orders'],
          customers: c?.data?.[0]?.['Total Customers'],
          aov: a?.data?.[0]?.['AOV (USD)'],
        });
      })
      .catch(() => {
        setKpi({ revenue: null, orders: null, customers: null, aov: null });
      })
      .finally(() => setKpiLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Revenue by month
  const [revMonth, setRevMonth] = useState([]);
  const [revLoad, setRevLoad] = useState(false);
  useEffect(() => {
    setRevLoad(true);
    ChartsApi.chartsRevenueByMonth(resolved)
      .then((r) => setRevMonth(r?.data || []))
      .catch(() => setRevMonth([]))
      .finally(() => setRevLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Profit by month
  const [profitMonth, setProfitMonth] = useState([]);
  const [profitLoad, setProfitLoad] = useState(false);
  useEffect(() => {
    setProfitLoad(true);
    ChartsApi.chartsProfitByMonth(resolved)
      .then((r) => setProfitMonth(r?.data || []))
      .catch(() => setProfitMonth([]))
      .finally(() => setProfitLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // New vs Returning
  const [newReturn, setNewReturn] = useState([]);
  const [nrLoad, setNrLoad] = useState(false);
  useEffect(() => {
    setNrLoad(true);
    ChartsApi.chartsNewVsReturning(resolved)
      .then((r) => setNewReturn(r?.data || []))
      .catch(() => setNewReturn([]))
      .finally(() => setNrLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // New customers over time
  const [newCust, setNewCust] = useState([]);
  const [ncLoad, setNcLoad] = useState(false);
  useEffect(() => {
    setNcLoad(true);
    ChartsApi.chartsNewCustomersOverTime(resolved)
      .then((r) => setNewCust(r?.data || []))
      .catch(() => setNewCust([]))
      .finally(() => setNcLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Customers by location
  const [byLoc, setByLoc] = useState([]);
  const [locLoad, setLocLoad] = useState(false);
  useEffect(() => {
    setLocLoad(true);
    ChartsApi.chartsCustomersByLocation(resolved)
      .then((r) => setByLoc(r?.data || []))
      .catch(() => setByLoc([]))
      .finally(() => setLocLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Retention
  const [ret, setRet] = useState(null);
  const [retLoad, setRetLoad] = useState(false);
  useEffect(() => {
    setRetLoad(true);
    ChartsApi.chartsRetention(resolved)
      .then((r) => setRet(r?.data?.[0]?.['Retention Rate (%)']))
      .catch(() => setRet(null))
      .finally(() => setRetLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // Sales by product
  const [byProd, setByProd] = useState([]);
  const [prodLoad, setProdLoad] = useState(false);
  useEffect(() => {
    setProdLoad(true);
    ChartsApi.chartsSalesByProduct(resolved)
      .then((r) => setByProd(r?.data || []))
      .catch(() => setByProd([]))
      .finally(() => setProdLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // CAC
  const [cac, setCac] = useState(null);
  const [cacLoad, setCacLoad] = useState(false);
  useEffect(() => {
    setCacLoad(true);
    ChartsApi.chartsCac(resolved)
      .then((r) => setCac(r?.data?.[0]?.['CAC (USD)']))
      .catch(() => setCac(null))
      .finally(() => setCacLoad(false));
  }, [resolved.start_date, resolved.end_date]);

  // CLV
  const [clv, setClv] = useState(null);
  const [clvLoad, setClvLoad] = useState(false);
  useEffect(() => {
    setClvLoad(true);
    ChartsApi.chartsClv(resolved)
      .then((r) => setClv(r?.data?.[0]?.['CLV (USD)']))
      .catch(() => setClv(null))
      .finally(() => setClvLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type, resolved.customer_lifespan_months]);

  // CAC/CLV over time
  const [cacClv, setCacClv] = useState([]);
  const [cacClvLoad, setCacClvLoad] = useState(false);
  useEffect(() => {
    setCacClvLoad(true);
    ChartsApi.chartsCacClv(resolved)
      .then((r) => setCacClv(r?.data || []))
      .catch(() => setCacClv([]))
      .finally(() => setCacClvLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_lifespan_months]);

  // Orders by month
  const [ordMonth, setOrdMonth] = useState([]);
  const [ordLoad, setOrdLoad] = useState(false);
  useEffect(() => {
    setOrdLoad(true);
    ChartsApi.chartsOrdersByMonth(resolved)
      .then((r) => setOrdMonth(r?.data || []))
      .catch(() => setOrdMonth([]))
      .finally(() => setOrdLoad(false));
  }, [resolved.start_date, resolved.end_date, resolved.customer_type]);

  // AOV over time
  const [aovTime, setAovTime] = useState([]);
  const [aovLoad, setAovLoad] = useState(false);
  useEffect(() => {
    setAovLoad(true);
    ChartsApi.chartsAovOverTime(resolved)
      .then((r) => setAovTime(r?.data || []))
      .catch(() => setAovTime([]))
      .finally(() => setAovLoad(false));
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

  return (
    <div className="charts-page">
      <Card className="charts-filters" size="small">
        <Space wrap size="middle" align="center">
          <Select
            value={year}
            onChange={setYear}
            style={{ width: 120 }}
            options={[{ value: 'all', label: 'All years' }, ...yearOpts.filter((y) => y !== 'all').map((y) => ({ value: String(y), label: String(y) }))]}
          />
          <Select
            value={month}
            onChange={setMonth}
            style={{ width: 140 }}
            options={[{ value: 'all', label: 'All months' }, ...monthNames.map((m, i) => ({ value: String(i + 1), label: m }))]}
          />
          <DatePicker placeholder="From" value={fromDate} onChange={setFromDate} />
          <DatePicker placeholder="To" value={toDate} onChange={setToDate} />
          <Select
            value={customerType}
            onChange={setCustomerType}
            style={{ width: 160 }}
            options={custOpts}
          />
          <Space>
            <span style={{ fontSize: 13, color: '#666' }}>Lifespan (mo):</span>
            <InputNumber min={1} max={60} value={lifespan} onChange={setLifespan} style={{ width: 72 }} />
          </Space>
        </Space>
      </Card>

      <Row gutter={[16, 16]} className="charts-kpi" style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card size="small" className="kpi-card">
            <div className="kpi-label">Doanh thu</div>
            <Spin spinning={kpiLoad}>
              <div className="kpi-value">{kpi.revenue != null ? `$${Number(kpi.revenue).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}</div>
            </Spin>
            <div className="kpi-sub">Tổng doanh thu</div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" className="kpi-card">
            <div className="kpi-label">Đơn hàng</div>
            <Spin spinning={kpiLoad}>
              <div className="kpi-value">{kpi.orders != null ? Number(kpi.orders).toLocaleString() : '—'}</div>
            </Spin>
            <div className="kpi-sub">Tổng số đơn hàng</div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" className="kpi-card">
            <div className="kpi-label">Khách hàng</div>
            <Spin spinning={kpiLoad}>
              <div className="kpi-value">{kpi.customers != null ? Number(kpi.customers).toLocaleString() : '—'}</div>
            </Spin>
            <div className="kpi-sub">Tổng số khách hàng</div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" className="kpi-card">
            <div className="kpi-label">AOV</div>
            <Spin spinning={kpiLoad}>
              <div className="kpi-value">{kpi.aov != null ? `$${Number(kpi.aov).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}</div>
            </Spin>
            <div className="kpi-sub">Giá trị đơn hàng trung bình</div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="Revenue by Month" className="chart-container">
            <Spin spinning={revLoad}>
              {revMonth.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: revMonth.map((r) => r.Month), y: revMonth.map((r) => r['Revenue (USD)']), type: 'bar', name: 'Revenue (USD)' }]}
                    layout={{ ...baseLayout, title: 'Monthly Revenue (USD)' }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
            </Spin>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Profit by Month" className="chart-container">
            <Spin spinning={profitLoad}>
              {profitMonth.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: profitMonth.map((r) => r.Month), y: profitMonth.map((r) => r['Profit (USD)']), type: 'bar', name: 'Profit (USD)', marker: { color: '#1890ff' } }]}
                    layout={{ ...baseLayout, title: 'Monthly Profit (USD)' }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
            </Spin>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="New vs Returning Customer Sales" className="chart-container">
            <Spin spinning={nrLoad}>
              {newReturn.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ values: newReturn.map((r) => r['Revenue (USD)']), labels: newReturn.map((r) => r['Customer Type']), type: 'pie', hole: 0.4, marker: { colors: ['#FF6B6B', '#4ECDC4'] } }]}
                    layout={{ ...baseLayout, title: 'Revenue by Customer Type', showlegend: true }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
            </Spin>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="New Customers Over Time" className="chart-container">
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
          </Card>
        </Col>
      </Row>

      <Card title="Customers by Location (US States)" className="chart-container" style={{ marginBottom: 16 }}>
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
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card title="Customer Retention Rate" className="chart-container">
            <Spin spinning={retLoad}>
              <div style={{ textAlign: 'center', padding: '32px 0' }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#1890ff' }}>
                  {ret != null ? `${Number(ret).toFixed(2)}%` : '—'}
                </div>
                <div style={{ fontSize: 12, color: '#999', marginTop: 8 }}>Retention (%)</div>
              </div>
            </Spin>
          </Card>
        </Col>
        <Col span={16}>
          <Card title="Top 10 Products by Revenue" className="chart-container">
            <Spin spinning={prodLoad}>
              {byProd.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: byProd.map((r) => r['Revenue (USD)']), y: byProd.map((r) => r.Product), type: 'bar', orientation: 'h', marker: { color: '#10b981' } }]}
                    layout={{ ...baseLayout, title: 'Top 10 by Revenue', xaxis: { title: 'Revenue (USD)' }, yaxis: { title: '' } }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
            </Spin>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="Customer Acquisition Cost (CAC)" className="chart-container">
            <Spin spinning={cacLoad}>
              <div style={{ textAlign: 'center', padding: '32px 0' }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#9c27b0' }}>
                  {cac != null ? `$${Number(cac).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                </div>
                <div style={{ fontSize: 12, color: '#999', marginTop: 8 }}>CAC (USD)</div>
              </div>
            </Spin>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Customer Lifetime Value (CLV)" className="chart-container">
            <Spin spinning={clvLoad}>
              <div style={{ textAlign: 'center', padding: '32px 0' }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#00bcd4' }}>
                  {clv != null ? `$${Number(clv).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                </div>
                <div style={{ fontSize: 12, color: '#999', marginTop: 8 }}>CLV (USD)</div>
              </div>
            </Spin>
          </Card>
        </Col>
      </Row>

      <Card title="Monthly CAC vs CLV with CLV/CAC Ratio" className="chart-container" style={{ marginBottom: 16 }}>
        <Spin spinning={cacClvLoad}>
          {cacClv.length > 0 ? (
            <div className="plotly-chart-wrapper">
              <Plot
                data={[
                  { x: cacClv.map((r) => r.Month), y: cacClv.map((r) => r['CAC (USD)']), type: 'bar', name: 'CAC (USD)', marker: { color: '#9C27B0' } },
                  { x: cacClv.map((r) => r.Month), y: cacClv.map((r) => r['CLV (USD)']), type: 'bar', name: 'CLV (USD)', marker: { color: '#00BCD4' } },
                  { x: cacClv.map((r) => r.Month), y: cacClv.map((r) => r['CLV/CAC (x)']), type: 'scatter', mode: 'lines+markers', name: 'CLV/CAC (x)', yaxis: 'y2', line: { color: '#FFA726', width: 2 } },
                ]}
                layout={{ ...baseLayout, barmode: 'group', yaxis2: { overlaying: 'y', side: 'right', title: 'CLV/CAC (x)' }, legend: { x: 1, y: 1.1, orientation: 'h' } }}
                config={{ displayModeBar: true, displaylogo: false, responsive: true }}
              />
            </div>
          ) : (
            <div className="charts-empty">No data</div>
          )}
        </Spin>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="Total Orders by Month" className="chart-container">
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
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Average Order Value Over Time" className="chart-container">
            <Spin spinning={aovLoad}>
              {aovTime.length > 0 ? (
                <div className="plotly-chart-wrapper">
                  <Plot
                    data={[{ x: aovTime.map((r) => r.Date), y: aovTime.map((r) => r['AOV (USD)']), type: 'scatter', mode: 'lines+markers', line: { color: '#FF5722', width: 2 } }]}
                    layout={{ ...baseLayout, title: 'AOV Over Time (USD)' }}
                    config={{ displayModeBar: true, displaylogo: false, responsive: true }}
                  />
                </div>
              ) : (
                <div className="charts-empty">No data</div>
              )}
            </Spin>
          </Card>
        </Col>
      </Row>

      <Card title="Revenue Comparison by Month" className="chart-container">
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
                    { x: cmp.data.filter((r) => r.Month === 'Month 1').map((r) => r.Day), y: cmp.data.filter((r) => r.Month === 'Month 1').map((r) => r['Revenue (USD)']), type: 'scatter', mode: 'lines+markers', name: `${cmp.month1_name}`, line: { color: '#FF6B6B', width: 2 } },
                    { x: cmp.data.filter((r) => r.Month === 'Month 2').map((r) => r.Day), y: cmp.data.filter((r) => r.Month === 'Month 2').map((r) => r['Revenue (USD)']), type: 'scatter', mode: 'lines+markers', name: `${cmp.month2_name}`, line: { color: '#4ECDC4', width: 2 } },
                  ]}
                  layout={{ ...baseLayout, title: 'Daily Revenue Comparison', xaxis: { title: 'Day of Month' }, yaxis: { title: 'Revenue (USD)' }, legend: { x: 1, y: 1.1, orientation: 'h' } }}
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
      </Card>
    </div>
  );
}
