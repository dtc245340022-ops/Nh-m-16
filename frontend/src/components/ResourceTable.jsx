import { Edit3, Trash2 } from 'lucide-react'

const labels = {
  id: 'Mã',
  title: 'Tiêu đề',
  description: 'Mô tả',
  venue: 'Địa điểm',
  starts_at: 'Bắt đầu',
  ends_at: 'Kết thúc',
  submission_deadline: 'Hạn nộp bài',
  review_deadline: 'Hạn phản biện',
  registration_deadline: 'Hạn đăng ký',
  conference_id: 'Hội nghị',
  submitted_by: 'Tác giả gửi',
  session_id: 'Phiên trình bày',
  abstract: 'Tóm tắt',
  keywords: 'Từ khóa',
  status: 'Trạng thái',
  room: 'Phòng',
  registered_at: 'Ngày đăng ký',
  user_id: 'Tài khoản',
  full_name: 'Họ và tên',
  email: 'Email',
  expertise: 'Chuyên môn',
  max_assignments: 'Giới hạn phân công',
  paper_id: 'Bài báo',
  reviewer_id: 'Phản biện',
  assigned_by: 'Người phân công',
  deadline: 'Hạn phản biện',
  assignment_id: 'Phân công',
  recommendation: 'Kết quả',
  score: 'Điểm',
  comments: 'Nhận xét',
  author_order: 'Thứ tự',
  is_corresponding: 'Liên hệ chính',
}

const statuses = {
  draft: 'Bản nháp',
  submitted: 'Đã gửi',
  under_review: 'Đang phản biện',
  accepted: 'Được chấp nhận',
  rejected: 'Bị từ chối',
  assigned: 'Đã phân công',
  in_progress: 'Đang thực hiện',
  completed: 'Hoàn thành',
  declined: 'Đã từ chối',
  registered: 'Đã đăng ký',
  cancelled: 'Đã hủy',
  attended: 'Đã tham dự',
  accept: 'Chấp nhận',
  minor_revision: 'Sửa nhỏ',
  major_revision: 'Sửa lớn',
  reject: 'Từ chối',
}

function formatCell(value, key) {
  if (value === null || value === undefined || value === '') return '—'
  if (key === 'status' || key === 'recommendation') return statuses[value] || value
  if (key === 'is_corresponding') return value ? 'Có' : 'Không'
  if (typeof value === 'string' && /^\d{4}-\d\d-\d\dT/.test(value)) {
    return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  }
  return String(value)
}

export function ResourceTable({
  rows,
  columns,
  loading,
  emptyText = 'Chưa có dữ liệu phù hợp.',
  canEdit,
  canDelete,
  onEdit,
  onDelete,
  renderActions,
}) {
  if (loading) return <div className="crud-loading"><span className="spinner" /> Đang tải dữ liệu…</div>
  if (!rows.length) {
    return <div className="crud-empty"><span className="empty-icon">∅</span><strong>Danh sách đang trống</strong><span>{emptyText}</span></div>
  }
  return (
    <div className="crud-table-scroll">
      <table className="crud-table">
        <thead><tr>{columns.map((column) => <th key={column}>{labels[column] || column}</th>)}<th className="actions-heading">Thao tác</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id ?? row.user_id ?? row.assignment_id}>
              {columns.map((column) => (
                <td key={column}>
                  {column === 'status' ? (
                    <span className={`status-pill status-${row[column]}`}>{formatCell(row[column], column)}</span>
                  ) : (
                    <span className={column === 'title' ? 'table-primary' : ''} title={String(row[column] ?? '')}>
                      {formatCell(row[column], column)}
                    </span>
                  )}
                </td>
              ))}
              <td>
                <div className="row-actions">
                  {renderActions?.(row)}
                  {canEdit?.(row) && <button className="row-action" type="button" onClick={() => onEdit(row)} aria-label="Chỉnh sửa"><Edit3 size={15} /></button>}
                  {canDelete?.(row) && <button className="row-action danger" type="button" onClick={() => onDelete(row)} aria-label="Xóa"><Trash2 size={15} /></button>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
