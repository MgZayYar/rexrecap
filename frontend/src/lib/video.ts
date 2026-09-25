export type Video = {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  created_at: string;
};

export function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
