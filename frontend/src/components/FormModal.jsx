import { useEffect, useState } from 'react'
import { X } from 'lucide-react'

function localDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

function initialForm(fields, record) {
  return Object.fromEntries(fields.map((field) => {
    const value = record?.[field.name] ?? field.defaultValue ?? ''
    return [field.name, field.type === 'datetime-local' ? localDateTime(value) : value]
  }))
}

export default function FormModal({ title, fields, record, onClose, onSubmit, busy }) {
  const [values, setValues] = useState(() => initialForm(fields, record))
  const [validationError, setValidationError] = useState('')

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape' && !busy) onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [busy, onClose])

  function update(name, value) {
    setValues((current) => ({ ...current, [name]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    setValidationError('')
    const missing = fields.find((field) => field.required && !String(values[field.name] ?? '').trim())
    if (missing) {
      setValidationError(`Vui lòng nhập ${missing.label.toLocaleLowerCase('vi')}.`)
      return
    }
    for (const field of fields) {
      if (field.type === 'datetime-local' && values[field.name]) {
        const date = new Date(values[field.name])
        if (Number.isNaN(date.getTime())) {
          setValidationError(`${field.label} không hợp lệ.`)
          return
        }
      }
      if (field.type === 'number' && values[field.name] !== '') {
        const number = Number(values[field.name])
        if (!Number.isFinite(number) || number < (field.min ?? 0)) {
          setValidationError(`${field.label} phải lớn hơn hoặc bằng ${field.min ?? 0}.`)
          return
        }
        if (field.max !== undefined && number > field.max) {
          setValidationError(`${field.label} không được lớn hơn ${field.max}.`)
          return
        }
      }
    }
    await onSubmit(values)
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !busy) onClose()
    }}>
      <section className="form-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal-heading">
          <div><span className="eyebrow">QUẢN LÝ HỌC THUẬT</span><h2 id="modal-title">{title}</h2></div>
          <button type="button" className="icon-button" aria-label="Đóng" onClick={onClose} disabled={busy}><X size={18} /></button>
        </div>
        <form onSubmit={submit}>
          <div className="modal-fields">
            {fields.map((field) => (
              <label className={`form-field ${field.wide ? 'field-wide' : ''}`} key={field.name}>
                <span>{field.label}{field.required && <i> *</i>}</span>
                {field.type === 'select' ? (
                  <select
                    value={values[field.name]}
                    required={field.required}
                    onChange={(event) => update(field.name, event.target.value)}
                  >
                    <option value="">{field.placeholder || 'Chọn…'}</option>
                    {field.options?.map((option) => (
                      <option key={String(option.value)} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                ) : field.type === 'textarea' ? (
                  <textarea
                    rows={field.rows || 4}
                    value={values[field.name]}
                    required={field.required}
                    maxLength={field.maxLength}
                    placeholder={field.placeholder}
                    onChange={(event) => update(field.name, event.target.value)}
                  />
                ) : (
                  <input
                    type={field.type || 'text'}
                    min={field.min}
                    max={field.max}
                    maxLength={field.maxLength}
                    step={field.step}
                    required={field.required}
                    value={values[field.name]}
                    placeholder={field.placeholder}
                    onChange={(event) => update(field.name, event.target.value)}
                  />
                )}
                {field.hint && <small>{field.hint}</small>}
              </label>
            ))}
          </div>
          {validationError && <p className="form-validation-error">{validationError}</p>}
          <div className="modal-actions">
            <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>Hủy</button>
            <button type="submit" className="primary-button" disabled={busy}>
              {busy ? 'Đang lưu…' : 'Lưu thông tin'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
