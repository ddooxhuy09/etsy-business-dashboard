import React from 'react';
import { Button, Popover } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';

/**
 * Hiển thị tiêu đề cột kèm nút annotation (info).
 * @param {string} title - Tên cột hiển thị
 * @param {ReactNode|object} annotation - Nội dung Popover. Có thể là ReactNode hoặc { title, content }
 */
export default function TableColumnTitle({ title, annotation }) {
  if (!annotation) {
    return title;
  }
  const content = typeof annotation === 'object' && annotation !== null && !React.isValidElement(annotation)
    ? annotation.content
    : annotation;
  const popoverTitle = typeof annotation === 'object' && annotation !== null && annotation.title != null
    ? annotation.title
    : title;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {title}
      <Popover content={content} title={popoverTitle} trigger="click" placement="top">
        <Button
          type="text"
          size="small"
          icon={<InfoCircleOutlined />}
          title="Xem giải thích"
          style={{ color: '#1890ff', padding: '0 4px', minWidth: 24, height: 24 }}
          onClick={(e) => e.stopPropagation()}
        />
      </Popover>
    </span>
  );
}
