/**
 * Shared zh-TW display labels. API values (status, source_type) stay as-is in
 * requests and CSS class names; only the visible text goes through here.
 */
const STATUS_LABELS = {
  completed: "已完成",
  completed_with_errors: "部分失敗",
  failed: "失敗",
  processing: "處理中",
  pending: "等待中",
};

const SOURCE_LABELS = {
  image: "圖片",
  video: "影片",
};

export function statusLabel(status) {
  return STATUS_LABELS[status] || status || "-";
}

export function sourceLabel(sourceType) {
  return SOURCE_LABELS[sourceType] || sourceType || "-";
}
