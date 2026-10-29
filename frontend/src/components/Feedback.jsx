import { AlertCircle, CheckCircle2, X } from 'lucide-react'

export function Toast({ toast, onClose }) {
  if (!toast) return null
  const Icon = toast.type === 'success' ? CheckCircle2 : AlertCircle
  return (
    <div className={`toast toast-${toast.type}`} role="status">
      <Icon size={18} />
      <span>{toast.message}</span>
      <button type="button" aria-label="Đóng thông báo" onClick={onClose}><X size={15} /></button>
    </div>
  )
}
