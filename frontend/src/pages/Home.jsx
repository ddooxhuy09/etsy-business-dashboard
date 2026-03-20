import React, { useState, useEffect } from 'react';
import { Card, Form, Select, Button, Table, Spin, message, Alert, Space, Upload, Modal, Badge, Tag, Row, Col, Input, DatePicker } from 'antd';
import { UploadOutlined, PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, PlusOutlined, UnorderedListOutlined, DeleteOutlined, CloseOutlined, FolderAddOutlined, FolderOutlined } from '@ant-design/icons';
import { fetchImportFiles, uploadImportFiles, runImportEtl, fetchExpectedColumns, deleteImportFile, FILE_LABELS, FILE_DISPLAY_NAMES, fetchImportPeriods, createImportPeriod } from '../api/importApi';

const YEARS = Array.from({ length: 15 }, (_, i) => 2020 + i);
const MONTHS = [
  { value: 1, label: 'Tháng 1' }, { value: 2, label: 'Tháng 2' }, { value: 3, label: 'Tháng 3' },
  { value: 4, label: 'Tháng 4' }, { value: 5, label: 'Tháng 5' }, { value: 6, label: 'Tháng 6' },
  { value: 7, label: 'Tháng 7' }, { value: 8, label: 'Tháng 8' }, { value: 9, label: 'Tháng 9' },
  { value: 10, label: 'Tháng 10' }, { value: 11, label: 'Tháng 11' }, { value: 12, label: 'Tháng 12' },
];

const FILE_ORDER = ['statement', 'direct_checkout', 'listing', 'sold_order_items', 'sold_orders', 'deposits'];

function fmtFilename(key, year, month) {
  const pat = FILE_LABELS[key] || '';
  return pat.replace('{year}', year).replace('{month}', String(month).padStart(2, '0'));
}

function fmtSize(n) {
  if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + ' MB';
  if (n >= 1024) return (n / 1024).toFixed(1) + ' KB';
  return n + ' B';
}

export default function Home() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [periods, setPeriods] = useState([]);
  const [periodMetadata, setPeriodMetadata] = useState({}); // { "2025-01": { etl_done_at, file_count }, ... }
  const [period, setPeriod] = useState(null);
  const [fileStatus, setFileStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [etlLoading, setEtlLoading] = useState(false);
  const [etlResult, setEtlResult] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState({});
  const [uploadKey, setUploadKey] = useState(0);
  const [uploadValidation, setUploadValidation] = useState(null);
  const [expectedColsModal, setExpectedColsModal] = useState(false);
  const [expectedCols, setExpectedCols] = useState(null);
  const [deletingFiles, setDeletingFiles] = useState(new Set());

  useEffect(() => {
    // Load danh sách folder kỳ dữ liệu có trong data/raw
    fetchImportPeriods()
      .then((data) => {
        const ps = data.periods || [];
        const metadata = data.metadata || {};
        if (!ps || ps.length === 0) {
          setPeriods([]);
          setPeriodMetadata({});
          setPeriod(null);
          setFileStatus(null);
          return;
        }
        ps.sort();
        setPeriods(ps);
        setPeriodMetadata(metadata);
        const latest = ps[ps.length - 1];
        setPeriod((prev) => prev || latest);
        const [y, m] = latest.split('-').map((v) => parseInt(v, 10));
        setYear(y);
        setMonth(m);
      })
      .catch((error) => {
        const status = error?.response?.status;
        const detail = error?.response?.data?.detail || error?.message || 'Unknown error';
        if (status === 401) {
          Modal.error({
            title: 'Lỗi xác thực (401 Unauthorized)',
            content: (
              <div>
                <p><strong>Nguyên nhân:</strong> Token JWT không hợp lệ, đã hết hạn, hoặc không được gửi kèm request.</p>
                <p><strong>URL:</strong> /api/import/periods</p>
                <p><strong>Chi tiết:</strong> {detail}</p>
                <p><strong>Giải pháp:</strong> Vui lòng đăng nhập lại để lấy token mới.</p>
              </div>
            ),
            width: 600,
          });
        } else {
          message.error(`Không tải được danh sách kỳ dữ liệu: ${detail}`);
        }
      });
  }, []);

  // Fetch files chỉ khi đổi kỳ (chọn trong bảng hoặc tạo kỳ mới). Đổi year/month dropdown không reset kỳ.
  useEffect(() => {
    if (!period) return;
    const [y, m] = period.split('-').map((v) => parseInt(v, 10));
    if (!y || !m) return;
    setLoading(true);
    fetchImportFiles(y, m)
      .then((r) => setFileStatus(r))
      .catch((error) => {
        const status = error?.response?.status;
        const detail = error?.response?.data?.detail || error?.message || 'Unknown error';
        if (status === 401) {
          Modal.error({
            title: 'Lỗi xác thực (401 Unauthorized)',
            content: (
              <div>
                <p><strong>Nguyên nhân:</strong> Token JWT không hợp lệ, đã hết hạn, hoặc không được gửi kèm request.</p>
                <p><strong>URL:</strong> /api/import/files</p>
                <p><strong>Chi tiết:</strong> {detail}</p>
                <p><strong>Giải pháp:</strong> Vui lòng đăng nhập lại để lấy token mới.</p>
              </div>
            ),
            width: 600,
          });
        } else {
          message.error(`Không tải được danh sách file: ${detail}`);
        }
      })
      .finally(() => setLoading(false));
  }, [period]);

  const handleSelectPeriod = (p) => {
    setPeriod(p);
    const [y, m] = p.split('-').map((v) => parseInt(v, 10));
    setYear(y);
    setMonth(m);
  };

  const handleCreatePeriod = async () => {
    try {
      const res = await createImportPeriod(year, month);
      const ps = res.periods || [];
      if (ps.length === 0) return;
      ps.sort();
      setPeriods(ps);
      // Reload metadata sau khi tạo period mới
      fetchImportPeriods()
        .then((data) => {
          setPeriodMetadata(data.metadata || {});
        })
        .catch(() => {});
      const newly = res.period || ps[ps.length - 1];
      setPeriod(newly);
      const [y, m] = newly.split('-').map((v) => parseInt(v, 10));
      setYear(y);
      setMonth(m);
      message.success(`Đã tạo folder kỳ dữ liệu ${newly}`);
    } catch {
      message.error('Tạo folder kỳ dữ liệu thất bại');
    }
  };

  const onFileSelect = (key, file) => {
    setSelectedFiles((s) => ({ ...s, [key]: file || null }));
  };

  const onUpload = async () => {
    const toSend = Object.fromEntries(Object.entries(selectedFiles).filter(([, v]) => v && v instanceof File));
    if (Object.keys(toSend).length === 0) {
      message.warning('Chọn ít nhất một file để tải lên');
      return;
    }
    setUploading(true);
    setUploadValidation(null);
    try {
      const r = await uploadImportFiles(periodYear, periodMonth, toSend);
      const validation = r.validation || {};
      const hasErrors = Object.values(validation).some((v) => !v.ok && v.errors?.length > 0);

      if (hasErrors) {
        // Có lỗi validation - không lưu file
        setUploadValidation(validation);
        const errorCount = Object.values(validation).filter((v) => !v.ok).length;
        message.error(`${errorCount} file có lỗi định dạng. Vui lòng kiểm tra và sửa lại.`);
      } else {
        // Không có lỗi - thành công
        const savedCount = r.saved?.length || 0;
        if (savedCount > 0) {
          message.success(`Đã lưu ${savedCount} file`);
          setSelectedFiles({});
          setUploadKey((k) => k + 1);
          const st = await fetchImportFiles(periodYear, periodMonth);
          setFileStatus(st);
        } else {
          message.warning('Không có file nào được lưu');
        }
      }
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Tải lên thất bại');
    } finally {
      setUploading(false);
    }
  };

  const openExpectedColsModal = () => {
    setExpectedColsModal(true);
    if (!expectedCols) fetchExpectedColumns().then((d) => setExpectedCols(d.columns_by_key || {})).catch(() => setExpectedCols({}));
  };

  const onRunEtl = async () => {
    setEtlLoading(true);
    setEtlResult(null);
    try {
      const r = await runImportEtl(periodYear, periodMonth, { force: false });
      setEtlResult(r);
        if (r.ok) {
          message.success(r.skipped ? 'Đã bỏ qua (không thay đổi)' : 'Process chạy xong');
          const st = await fetchImportFiles(periodYear, periodMonth);
          setFileStatus(st);
          // Reload metadata để cập nhật etl_done_at cho period này
          fetchImportPeriods()
            .then((data) => {
              setPeriodMetadata(data.metadata || {});
            })
            .catch(() => {});
        } else {
          message.error(r.message || 'Process lỗi');
        }
    } catch (e) {
      setEtlResult({ ok: false, message: e?.message || 'Lỗi kết nối' });
      message.error('Chạy process thất bại');
    } finally {
      setEtlLoading(false);
    }
  };

  const onDeleteFile = async (key, filename) => {
    const deleteKey = `${key}:${filename}`;
    setDeletingFiles((prev) => new Set(prev).add(deleteKey));
    try {
      await deleteImportFile(periodYear, periodMonth, key, filename);
      message.success(`Đã xóa file ${filename}`);
      const st = await fetchImportFiles(periodYear, periodMonth);
      setFileStatus(st);
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Xóa file thất bại');
    } finally {
      setDeletingFiles((prev) => {
        const next = new Set(prev);
        next.delete(deleteKey);
        return next;
      });
    }
  };

  const [periodYear, periodMonth] = period
    ? period.split('-').map((v) => parseInt(v, 10))
    : [null, null];
  const periodDisplay = period || `${year}-${String(month).padStart(2, '0')}`;

  // Directory listing columns for periods
  const periodCols = [
    {
      title: 'Name',
      key: 'name',
      dataIndex: 'period',
      render: (p) => (
        <Space>
          <FolderOutlined style={{ color: '#1890ff' }} />
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              handleSelectPeriod(p);
            }}
            style={{ color: period === p ? '#1890ff' : 'inherit', fontWeight: period === p ? 'bold' : 'normal' }}
          >
            {p}/
          </a>
        </Space>
      ),
    },
    {
      title: 'Last Modified',
      key: 'modified',
      dataIndex: 'modified',
      width: 180,
      render: (date) => date || '-',
    },
    {
      title: 'Description',
      key: 'description',
      render: (_, record) => {
        const status = record.etl_done_at ? (
          <Badge status="success" text="Đã process" />
        ) : (
          <Badge status="default" text="Chưa process" />
        );
        const fileCount = record.file_count || 0;
        return (
          <Space>
            {status}
            <span style={{ color: '#888', fontSize: 12 }}>{fileCount} files</span>
          </Space>
        );
      },
    },
  ];

  const fileTableCols = [
    {
      title: 'Tên', dataIndex: 'displayName', key: 'name', width: 200,
      render: (_, r) => (
        <div>
          <div>{FILE_DISPLAY_NAMES[r.key] || r.key}</div>
          <div style={{ fontSize: 11, color: '#888' }}>→ {r.filename}</div>
        </div>
      )
    },
    {
      title: 'Trạng thái', dataIndex: 'exists', key: 'exists', width: 280,
      render: (exists, r) => {
        if (!exists) return <span style={{ color: '#999' }}><CloseCircleOutlined /> Chưa có</span>;
        const names = (r.files?.length ? r.files.map((f) => f.filename) : [r.filename]).filter(Boolean).join(', ');
        return (
          <span style={{ color: '#52c41a' }}>
            <CheckCircleOutlined /> Đã có: {names || '—'} ({fmtSize(r.size)})
          </span>
        );
      }
    },
    {
      title: 'Chọn file', key: 'input', width: 400,
      render: (_, r) => {
        const chosen = selectedFiles[r.key];
        const files = r.exists && r.files?.length ? r.files : (r.exists ? [{ filename: r.filename, size: r.size }] : []);
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Space key={`${uploadKey}-${r.key}`} wrap>
              <Upload
                accept=".csv"
                showUploadList={false}
                beforeUpload={(file) => { onFileSelect(r.key, file); return false; }}
                maxCount={1}
              >
                <Button type="default" icon={<PlusOutlined />}>Chọn file</Button>
              </Upload>
              {chosen && (
                <Space>
                  <span style={{ fontSize: 12, color: '#52c41a' }}>{chosen.name}</span>
                  <Button
                    type="link"
                    danger
                    size="small"
                    icon={<CloseOutlined />}
                    onClick={() => onFileSelect(r.key, null)}
                    style={{ padding: 0, height: 'auto', fontSize: 12 }}
                    title="Bỏ chọn file"
                  >
                    Gỡ
                  </Button>
                </Space>
              )}
            </Space>
            {files.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {files.map((f, idx) => {
                  const deleteKey = `${r.key}:${f.filename}`;
                  const isDeleting = deletingFiles.has(deleteKey);
                  return (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                      <span style={{ color: '#666' }}>{f.filename}</span>
                      <Button
                        type="link"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        loading={isDeleting}
                        onClick={() => {
                          Modal.confirm({
                            title: 'Xác nhận xóa file',
                            content: `Bạn có chắc muốn xóa file "${f.filename}"?`,
                            okText: 'Xóa',
                            okType: 'danger',
                            cancelText: 'Hủy',
                            onOk: () => onDeleteFile(r.key, f.filename),
                          });
                        }}
                        style={{ padding: 0, height: 'auto', fontSize: 12 }}
                      >
                        Xóa
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      }
    },
  ];

  const fileTableRows = FILE_ORDER.map((key) => ({
    key,
    displayName: FILE_DISPLAY_NAMES[key] || key,
    filename: fileStatus?.files?.[key]?.filename || fmtFilename(key, periodYear ?? year, periodMonth ?? month),
    exists: fileStatus?.files?.[key]?.exists ?? false,
    size: fileStatus?.files?.[key]?.size ?? 0,
    uploaded_at: fileStatus?.files?.[key]?.uploaded_at,
    files: fileStatus?.files?.[key]?.files ?? [],
  }));

  // Period rows with metadata từ API (cho tất cả periods, không chỉ period hiện tại)
  const periodRows = periods.map((p) => {
    const meta = periodMetadata[p] || {};
    const fileCount = meta.file_count ?? 0;
    const etlDoneAt = meta.etl_done_at ?? null;
    // Nếu là period hiện tại, ưu tiên dùng fileStatus (có thể mới cập nhật)
    if (p === period && fileStatus) {
      const currentFileCount = Object.values(fileStatus.files || {}).filter((f) => f?.exists).length;
      return {
        key: p,
        period: p,
        modified: '-', // TODO: Add last modified from API
        file_count: currentFileCount > 0 ? currentFileCount : fileCount,
        etl_done_at: fileStatus.etl_done_at ?? etlDoneAt,
      };
    }
    return {
      key: p,
      period: p,
      modified: '-', // TODO: Add last modified from API
      file_count: fileCount,
      etl_done_at: etlDoneAt,
    };
  });

  return (
    <div style={{ padding: '0 8px' }}>
      <Card title="Import CSV theo tháng" style={{ marginBottom: 16 }}>
        <p style={{ color: '#666', marginBottom: 16 }}>
          Quản lý dữ liệu theo kỳ (năm-tháng). Chọn kỳ để tải lên các file CSV. Sau khi đủ file, bấm <strong>Chạy process</strong> để load vào database.
        </p>

        {/* Directory Listing of Periods */}
        <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col flex="auto">
              <strong>Danh sách kỳ dữ liệu</strong>
            </Col>
            <Col>
              <Space>
                <Select
                  value={year}
                  onChange={setYear}
                  options={YEARS.map((y) => ({ value: y, label: y }))}
                  style={{ width: 100 }}
                />
                <Select
                  value={month}
                  onChange={setMonth}
                  options={MONTHS}
                  style={{ width: 120 }}
                />
                <Button icon={<FolderAddOutlined />} onClick={handleCreatePeriod}>
                  Tạo kỳ mới
                </Button>
              </Space>
            </Col>
          </Row>
          <Table
            columns={periodCols}
            dataSource={periodRows}
            pagination={false}
            size="small"
            scroll={{ x: 'max-content' }}
            onRow={(record) => ({
              onClick: () => handleSelectPeriod(record.period),
              style: { cursor: 'pointer', background: period === record.period ? '#e6f7ff' : 'transparent' },
            })}
            locale={{ emptyText: 'Chưa có kỳ dữ liệu nào. Tạo kỳ mới để bắt đầu.' }}
          />
        </Card>

        {/* File Upload Section - Only show when period is selected */}
        {period && (
          <Card size="small" title={`Kỳ: ${period}`} style={{ marginBottom: 16 }}>
            <p style={{ fontSize: 12, color: '#888', marginBottom: 12 }}>
              <strong>Import đọc/ghi tại:</strong>{' '}
              <code style={{ background: '#f5f5f5', padding: '2px 6px', borderRadius: 4 }}>dashboard/data/raw/{period}/</code>
              {' '}<strong>Mỗi loại file có thể tải lên thêm nhiều lần (không ghi đè).</strong>
            </p>

            <Spin spinning={loading}>
              <Table
                columns={fileTableCols}
                dataSource={fileTableRows}
                pagination={false}
                size="small"
                scroll={{ x: 'max-content' }}
                style={{ marginBottom: 16 }}
              />
            </Spin>

            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <strong>Trạng thái process:</strong>
              {fileStatus?.etl_done_at ? (
                <Badge status="success" text={
                  <span style={{ color: '#52c41a' }}>
                    Đã process lúc {new Date(fileStatus.etl_done_at).toLocaleString('vi-VN')}
                  </span>
                } />
              ) : (
                <Badge status="default" text={<span style={{ color: '#999' }}>Chưa process</span>} />
              )}
            </div>
            {uploadValidation && Object.values(uploadValidation).some((v) => !v.ok) && (
              <Alert
                type="error"
                style={{ marginBottom: 12 }}
                message="Lỗi định dạng file (sai hoặc thiếu cột) - File không được lưu"
                description={
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {Object.entries(uploadValidation)
                      .filter(([, v]) => !v.ok && v.errors?.length)
                      .map(([k]) => (
                        <li key={k} style={{ marginBottom: 8 }}>
                          <strong style={{ color: '#ff4d4f' }}>{FILE_DISPLAY_NAMES[k] || k}:</strong>
                          <ul style={{ marginTop: 4, paddingLeft: 20 }}>
                            {uploadValidation[k].errors.map((err, idx) => (
                              <li key={idx} style={{ color: '#ff4d4f' }}>{err}</li>
                            ))}
                          </ul>
                        </li>
                      ))}
                  </ul>
                }
              />
            )}
            <Space wrap>
              <Button type="primary" icon={<UploadOutlined />} loading={uploading} onClick={onUpload}>
                Tải lên các file đã chọn
              </Button>
              <Button type="default" icon={<PlayCircleOutlined />} loading={etlLoading} onClick={onRunEtl}>
                Chạy process
              </Button>
              <Button type="link" icon={<UnorderedListOutlined />} onClick={openExpectedColsModal}>
                Cột raw mong đợi
              </Button>
            </Space>
          </Card>
        )}
      </Card>

      <Modal
        title="Tên cột raw (header CSV) theo từng loại file"
        open={expectedColsModal}
        onCancel={() => setExpectedColsModal(false)}
        footer={null}
        width={640}
      >
        {expectedCols ? (
          <div style={{ maxHeight: 400, overflow: 'auto' }}>
            {Object.entries(expectedCols).map(([key, cols]) => (
              <div key={key} style={{ marginBottom: 16 }}>
                <strong>{FILE_DISPLAY_NAMES[key] || key}</strong> <span style={{ color: '#888', fontSize: 12 }}>({key})</span>
                <div style={{ fontSize: 12, fontFamily: 'monospace', background: '#f9f9f9', padding: 8, borderRadius: 4, marginTop: 4 }}>
                  {Array.isArray(cols) ? cols.join(', ') : '(không dùng trong process)'}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Spin />
        )}
      </Modal>

      {etlResult && (
        <Card title="Kết quả process" size="small">
          {etlResult.ok ? (
            <Alert type="success" message={etlResult.message} />
          ) : (
            <Alert type="error" message={etlResult.message} description={etlResult.stderr || etlResult.stdout} />
          )}
        </Card>
      )}
    </div>
  );
}
