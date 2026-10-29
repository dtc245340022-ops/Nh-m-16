export function messageFromError(error) {
  const status = error.response?.status
  const detail = error.response?.data?.detail
  const validation = Array.isArray(detail)
    ? detail.map((item) => `${item.loc?.at(-1) || 'Dữ liệu'}: ${item.msg}`).join('. ')
    : detail
  if (status === 401) return validation || 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
  if (status === 403) return validation || 'Bạn không có quyền thực hiện thao tác này.'
  if (status === 404) return validation || 'Dữ liệu không còn tồn tại.'
  if (status === 409) return validation || 'Dữ liệu bị xung đột. Vui lòng tải lại và thử lại.'
  if (status === 422) return validation || 'Dữ liệu chưa hợp lệ. Vui lòng kiểm tra các trường.'
  return validation || error.message || 'Không thể kết nối máy chủ.'
}
