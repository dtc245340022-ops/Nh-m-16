import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Search } from 'lucide-react'
import { api } from '../api.js'
import FormModal from './FormModal.jsx'
import { Toast } from './Feedback.jsx'
import { messageFromError } from './errorMessages.js'
import { ResourceTable } from './ResourceTable.jsx'

function payloadFrom(values, fields) {
  return Object.fromEntries(fields
    .filter((field) => values[field.name] !== '' && values[field.name] !== undefined)
    .map((field) => {
      const value = values[field.name]
      if (field.type === 'number') return [field.name, Number(value)]
      if (field.type === 'datetime-local') return [field.name, new Date(value).toISOString()]
      if (field.type === 'select' && field.options?.some((option) => typeof option.value === 'number')) {
        return [field.name, Number(value)]
      }
      return [field.name, value]
    }))
}

export default function ResourceManager({
  config,
  user,
  extraActions,
  headerActions,
  filters,
  emptyText,
}) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState(null)
  const [modalRecord, setModalRecord] = useState(undefined)
  const [options, setOptions] = useState({})
  const [search, setSearch] = useState('')
  const [searchMode, setSearchMode] = useState('title')
  const [query, setQuery] = useState({})

  const isOrganizer = user.role === 'organizer' || user.role === 'admin'
  const fetchRows = useCallback(async (params = query) => {
    try {
      const response = await api.get(config.path, { params })
      if (!Array.isArray(response.data)) throw new Error('Dữ liệu API không đúng định dạng.')
      setRows(response.data)
      setError('')
    } catch (requestError) {
      setRows([])
      setError(messageFromError(requestError))
    } finally {
      setLoading(false)
    }
  }, [config.path, query])

  useEffect(() => {
    let active = true
    api.get(config.path, { params: query })
      .then(({ data }) => {
        if (!active) return
        if (!Array.isArray(data)) throw new Error('Dữ liệu API không đúng định dạng.')
        setRows(data)
        setError('')
      })
      .catch((requestError) => {
        if (!active) return
        setRows([])
        setError(messageFromError(requestError))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [config.path, query])

  useEffect(() => {
    let active = true
    const sources = config.optionSources || []
    if (!sources.length) return undefined
    Promise.all(sources.map(async (source) => {
      const response = await api.get(source.path)
      return [source.key, response.data]
    }))
      .then((entries) => {
        if (active) setOptions(Object.fromEntries(entries))
      })
      .catch((requestError) => {
        if (active) setToast({ type: 'error', message: messageFromError(requestError) })
      })
    return () => { active = false }
  }, [config.optionSources])

  const fields = useMemo(() => config.fields(options), [config, options])
  const canCreate = typeof config.canCreate === 'function'
    ? config.canCreate(user)
    : Boolean(config.canCreate)
  const canEdit = (row) => typeof config.canEdit === 'function'
    ? config.canEdit(row, user)
    : Boolean(config.canEdit)
  const canDelete = (row) => typeof config.canDelete === 'function'
    ? config.canDelete(row, user)
    : Boolean(config.canDelete)
  const visibleRows = useMemo(() => {
    if (config.searchParams || !search.trim()) return rows
    const term = search.trim().toLocaleLowerCase('vi')
    return rows.filter((row) => Object.values(row)
      .some((value) => String(value ?? '').toLocaleLowerCase('vi').includes(term)))
  }, [config.searchParams, rows, search])

  async function save(values) {
    setBusy(true)
    try {
      const data = payloadFrom(values, fields)
      const payload = config.toPayload ? config.toPayload(data, modalRecord, user) : data
      if (modalRecord) await api.put(`${config.path}/${config.idOf?.(modalRecord) ?? modalRecord.id}`, payload)
      else await api.post(config.path, payload)
      setModalRecord(undefined)
      setToast({ type: 'success', message: modalRecord ? 'Đã cập nhật thông tin.' : 'Đã tạo bản ghi mới.' })
      setLoading(true)
      await fetchRows()
      config.onSaved?.(modalRecord)
    } catch (requestError) {
      setToast({ type: 'error', message: messageFromError(requestError) })
    } finally {
      setBusy(false)
    }
  }

  async function remove(row) {
    if (!window.confirm(config.confirmDelete || 'Bạn có chắc chắn muốn xóa bản ghi này?')) return
    try {
      await api.delete(`${config.path}/${config.idOf?.(row) ?? row.id}`)
      setToast({ type: 'success', message: 'Đã xóa bản ghi.' })
      setLoading(true)
      await fetchRows()
    } catch (requestError) {
      setToast({ type: 'error', message: messageFromError(requestError) })
    }
  }

  function applySearch(event) {
    event.preventDefault()
    if (!config.searchParams) return
    const next = config.searchParams ? config.searchParams(search, query, searchMode) : (search.trim() ? { search: search.trim() } : {})
    setQuery(next)
    setLoading(true)
  }

  return (
    <div className="page-stack">
      <section className="crud-panel">
        <div className="crud-toolbar">
          <div className="crud-toolbar-copy">
            <h2>{config.heading}</h2>
            <span>{config.description}</span>
          </div>
          <div className="crud-toolbar-actions">
            {headerActions?.({ reload: () => fetchRows(), isOrganizer, user })}
            {canCreate && (
              <button type="button" className="primary-button compact-button" onClick={() => setModalRecord(null)}>
                <Plus size={16} /> {config.createLabel || 'Thêm mới'}
              </button>
            )}
          </div>
        </div>
        <form className="crud-searchbar" onSubmit={applySearch}>
          <label className="search-input-wrap">
            <Search size={17} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={config.searchPlaceholder || 'Tìm kiếm…'} />
          </label>
          {filters?.({ query, setQuery, searchMode, setSearchMode })}
          <button type="submit" className="secondary-button">Tìm kiếm</button>
          {Object.keys(query).length > 0 && (
            <button type="button" className="text-button" onClick={() => {
              setSearch('')
              setQuery({})
              setLoading(true)
            }}>Xóa lọc</button>
          )}
        </form>
        {error && <div className="page-message error">{error}</div>}
        <ResourceTable
          rows={visibleRows}
          columns={config.columns}
          loading={loading}
          emptyText={emptyText || config.emptyText}
          canEdit={canEdit}
          canDelete={canDelete}
          onEdit={setModalRecord}
          onDelete={remove}
          renderActions={extraActions ? (row) => extraActions(row, { user, reload: () => fetchRows() }) : undefined}
        />
        <div className="crud-table-footer">{visibleRows.length} bản ghi</div>
      </section>
      {modalRecord !== undefined && (
        <FormModal
          title={modalRecord ? (config.editTitle || 'Cập nhật thông tin') : (config.createTitle || 'Thêm bản ghi')}
          fields={fields}
          record={modalRecord}
          onClose={() => setModalRecord(undefined)}
          onSubmit={save}
          busy={busy}
        />
      )}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  )
}
