import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BookUser, RefreshCw, Sparkles, Users } from 'lucide-react'
import { api } from '../api.js'
import AiReviewerSuggestionsModal from '../components/AiReviewerSuggestionsModal.jsx'
import AiSummaryModal from '../components/AiSummaryModal.jsx'
import FormModal from '../components/FormModal.jsx'
import { Toast } from '../components/Feedback.jsx'
import { messageFromError } from '../components/errorMessages.js'
import ResourceManager from '../components/ResourceManager.jsx'
import { ResourceTable } from '../components/ResourceTable.jsx'

const organizer = (user) => user.role === 'organizer' || user.role === 'admin'
const author = (user) => user.role === 'author'
const reviewer = (user) => user.role === 'reviewer'
const NO_OPTION_SOURCES = []

const conferenceConfig = {
  path: '/conferences',
  heading: 'Danh sách hội nghị',
  description: 'Quản lý thông tin, thời gian và các mốc hạn của hội nghị.',
  columns: ['title', 'venue', 'starts_at', 'ends_at', 'submission_deadline', 'registration_deadline'],
  canCreate: organizer,
  canEdit: organizer,
  canDelete: organizer,
  fields: () => [
    { name: 'title', label: 'Tên hội nghị', required: true, maxLength: 200, wide: true },
    { name: 'description', label: 'Mô tả', type: 'textarea', wide: true },
    { name: 'venue', label: 'Địa điểm', maxLength: 255 },
    { name: 'starts_at', label: 'Bắt đầu', type: 'datetime-local', required: true },
    { name: 'ends_at', label: 'Kết thúc', type: 'datetime-local', required: true },
    { name: 'submission_deadline', label: 'Hạn nộp bài', type: 'datetime-local', required: true },
    { name: 'review_deadline', label: 'Hạn phản biện', type: 'datetime-local', required: true },
    { name: 'registration_deadline', label: 'Hạn đăng ký', type: 'datetime-local', required: true },
  ],
}

const paperConfig = {
  path: '/papers',
  heading: 'Bài báo khoa học',
  description: 'Theo dõi bài báo theo phạm vi quyền của tài khoản; trạng thái do quy trình backend quản lý.',
  columns: ['title', 'keywords', 'status', 'conference_id', 'session_id'],
  canCreate: author,
  canEdit: (_row, user) => author(user),
  canDelete: (_row, user) => author(user),
  searchPlaceholder: 'Tìm theo tiêu đề hoặc từ khóa…',
  searchParams: (search, query, mode) => ({ ...query, ...(search.trim() ? { [mode]: search.trim() } : {}) }),
  optionSources: [
    { key: 'conferences', path: '/conferences' },
    { key: 'sessions', path: '/sessions' },
  ],
  fields: (options) => [
    { name: 'title', label: 'Tiêu đề bài báo', required: true, maxLength: 300, wide: true },
    { name: 'abstract', label: 'Tóm tắt', type: 'textarea', required: true, wide: true, rows: 5 },
    { name: 'keywords', label: 'Từ khóa', placeholder: 'Ví dụ: trí tuệ nhân tạo, khoa học dữ liệu', wide: true },
    { name: 'conference_id', label: 'Hội nghị', type: 'select', required: true, options: (options.conferences || []).map((item) => ({ value: item.id, label: `${item.title} (#${item.id})` })) },
    { name: 'session_id', label: 'Phiên trình bày', type: 'select', options: (options.sessions || []).map((item) => ({ value: item.id, label: `${item.title} (#${item.id})` })), hint: 'Có thể để trống nếu chưa xếp phiên.' },
  ],
}

const sessionConfig = {
  path: '/sessions',
  heading: 'Phiên trình bày',
  description: 'Lịch trình phiên phải nằm trong thời gian hội nghị và không trùng phòng.',
  columns: ['title', 'room', 'starts_at', 'ends_at', 'conference_id'],
  canCreate: organizer,
  canEdit: organizer,
  canDelete: organizer,
  optionSources: [{ key: 'conferences', path: '/conferences' }],
  fields: (options) => [
    { name: 'title', label: 'Tên phiên', required: true, maxLength: 200 },
    { name: 'room', label: 'Phòng', maxLength: 100 },
    { name: 'conference_id', label: 'Hội nghị', type: 'select', required: true, options: (options.conferences || []).map((item) => ({ value: item.id, label: `${item.title} (#${item.id})` })) },
    { name: 'starts_at', label: 'Bắt đầu', type: 'datetime-local', required: true },
    { name: 'ends_at', label: 'Kết thúc', type: 'datetime-local', required: true },
  ],
}

const registrationConfig = {
  path: '/registrations',
  heading: 'Đăng ký tham dự',
  description: 'Tác giả quản lý đăng ký của mình; ban tổ chức theo dõi và cập nhật trạng thái tham dự.',
  columns: ['conference_id', 'user_id', 'status', 'registered_at'],
  canCreate: author,
  canEdit: (row, user) => organizer(user) || (author(user) && row.user_id === user.id),
  canDelete: (row, user) => organizer(user) || (author(user) && row.user_id === user.id),
  optionSources: [{ key: 'conferences', path: '/conferences' }],
  fields: (options, user) => [
    { name: 'conference_id', label: 'Hội nghị', type: 'select', required: true, options: (options.conferences || []).map((item) => ({ value: item.id, label: `${item.title} (#${item.id})` })) },
    { name: 'status', label: 'Trạng thái', type: 'select', required: true, options: organizer(user)
      ? [{ value: 'registered', label: 'Đã đăng ký' }, { value: 'cancelled', label: 'Đã hủy' }, { value: 'attended', label: 'Đã tham dự' }]
      : [{ value: 'registered', label: 'Đã đăng ký' }, { value: 'cancelled', label: 'Đã hủy' }] },
  ],
}

function ResourcePage({ config, user }) {
  const resolvedConfig = useMemo(() => ({
    ...config,
    fields: (options) => config.fields(options, user),
  }), [config, user])
  return <ResourceManager config={resolvedConfig} user={user} />
}

export function ConferencePage({ user }) {
  return <ResourcePage config={conferenceConfig} user={user} />
}

export function SessionPage({ user }) {
  return <ResourcePage config={sessionConfig} user={user} />
}

export function RegistrationPage({ user }) {
  return <ResourcePage config={registrationConfig} user={user} />
}

function PaperAuthors({ paper, user, onClose }) {
  const [authors, setAuthors] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState(null)
  const [addSelf, setAddSelf] = useState(false)
  const [authorId, setAuthorId] = useState('')
  const canAddOthers = organizer(user)
  const canManageOwn = author(user)
  const load = useCallback(async () => {
    try {
      const response = await api.get(`/papers/${paper.id}/authors`)
      setAuthors(response.data)
      setError('')
      setAddSelf(response.data.some((item) => item.user_id === user.id))
    } catch (requestError) {
      setError(messageFromError(requestError))
    } finally {
      setLoading(false)
    }
  }, [paper.id, user.id])
  useEffect(() => {
    let active = true
    api.get(`/papers/${paper.id}/authors`)
      .then(({ data }) => {
        if (!active) return
        setAuthors(data)
        setError('')
        setAddSelf(data.some((item) => item.user_id === user.id))
      })
      .catch((requestError) => {
        if (active) setError(messageFromError(requestError))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [paper.id, user.id])

  async function add(userId) {
    setBusy(true)
    setError('')
    try {
      await api.post(`/papers/${paper.id}/authors`, { user_id: userId })
      setToast({ type: 'success', message: 'Đã thêm tác giả.' })
      setAuthorId('')
      await load()
    } catch (requestError) {
      setToast({ type: 'error', message: messageFromError(requestError) })
    } finally {
      setBusy(false)
    }
  }

  async function remove(authorIdToRemove) {
    if (!window.confirm('Gỡ tác giả này khỏi bài báo?')) return
    setError('')
    try {
      await api.delete(`/papers/${paper.id}/authors/${authorIdToRemove}`)
      setToast({ type: 'success', message: 'Đã gỡ tác giả khỏi bài báo.' })
      await load()
    } catch (requestError) {
      setToast({ type: 'error', message: messageFromError(requestError) })
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="form-modal authors-modal" role="dialog" aria-modal="true" aria-labelledby="authors-title">
        <div className="modal-heading">
          <div><span className="eyebrow">BÀI BÁO #{paper.id}</span><h2 id="authors-title">Quản lý tác giả</h2></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Đóng"><span aria-hidden="true">×</span></button>
        </div>
        <p className="modal-context">{paper.title}</p>
        {error && <div className="page-message error">{error}</div>}
        {loading ? <div className="crud-loading"><span className="spinner" /> Đang tải tác giả…</div> : (
          <ul className="author-list">
            {authors.length ? authors.map((item) => (
              <li key={item.user_id}>
                <div><strong>{item.full_name}</strong><span>{item.email} · Tài khoản #{item.user_id}{item.is_corresponding ? ' · Liên hệ chính' : ''}</span></div>
                {(canAddOthers || (canManageOwn && item.user_id === user.id)) && (
                  <button type="button" className="row-action danger" onClick={() => remove(item.user_id)} aria-label="Gỡ tác giả">×</button>
                )}
              </li>
            )) : <li className="author-list-empty">Chưa có liên kết tác giả.</li>}
          </ul>
        )}
        {canAddOthers && (
          <form className="author-add-form" onSubmit={(event) => {
            event.preventDefault()
            if (Number(authorId) > 0) add(Number(authorId))
          }}>
            <label className="form-field"><span>Mã tài khoản tác giả</span><input type="number" min="1" value={authorId} onChange={(event) => setAuthorId(event.target.value)} required /></label>
            <button type="submit" className="secondary-button" disabled={busy}>{busy ? 'Đang thêm…' : 'Thêm tác giả'}</button>
          </form>
        )}
        {canManageOwn && !addSelf && (
          <button type="button" className="secondary-button add-self-button" disabled={busy} onClick={() => add(user.id)}>
            <Users size={16} /> Thêm tài khoản của tôi
          </button>
        )}
        <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Đóng</button></div>
        <Toast toast={toast} onClose={() => setToast(null)} />
      </section>
    </div>
  )
}

export function PaperPage({ user }) {
  const [selectedPaper, setSelectedPaper] = useState(null)
  const [aiSummary, setAiSummary] = useState(null)
  const [aiReviewerSuggestions, setAiReviewerSuggestions] = useState(null)
  const [aiRequestInFlight, setAiRequestInFlight] = useState(false)
  const aiRequestLock = useRef(false)

  async function summarize(paper) {
    if (aiRequestLock.current) return
    aiRequestLock.current = true
    setAiRequestInFlight(true)
    const requestState = { paper, loading: true, result: null, error: '' }
    setAiSummary(requestState)
    try {
      const { data } = await api.post(`/ai/summarize-paper/${paper.id}`)
      setAiSummary((current) => current === requestState
        ? { paper, loading: false, result: data, error: '' }
        : current)
    } catch (requestError) {
      const error = messageFromError(requestError)
      setAiSummary((current) => current === requestState
        ? { paper, loading: false, result: null, error }
        : current)
    } finally {
      aiRequestLock.current = false
      setAiRequestInFlight(false)
    }
  }

  async function suggestReviewers(paper) {
    if (aiRequestLock.current) return
    aiRequestLock.current = true
    setAiRequestInFlight(true)
    const requestState = { paper, loading: true, result: null, error: '' }
    setAiReviewerSuggestions(requestState)
    try {
      const { data } = await api.post(`/ai/suggest-reviewers/${paper.id}`)
      setAiReviewerSuggestions((current) => current === requestState
        ? { paper, loading: false, result: data, error: '' }
        : current)
    } catch (requestError) {
      const error = messageFromError(requestError)
      setAiReviewerSuggestions((current) => current === requestState
        ? { paper, loading: false, result: null, error }
        : current)
    } finally {
      aiRequestLock.current = false
      setAiRequestInFlight(false)
    }
  }
  const filters = ({ query, setQuery, searchMode, setSearchMode }) => (
    <>
      <select aria-label="Tìm trong tiêu đề hoặc từ khóa" value={searchMode} onChange={(event) => setSearchMode(event.target.value)}>
        <option value="title">Tiêu đề</option><option value="keyword">Từ khóa</option>
      </select>
      <select aria-label="Lọc trạng thái bài báo" value={query.status || ''} onChange={(event) => setQuery({ ...query, ...(event.target.value ? { status: event.target.value } : { status: undefined }) })}>
        <option value="">Mọi trạng thái</option>
        {[
          ['draft', 'Bản nháp'],
          ['submitted', 'Đã gửi'],
          ['under_review', 'Đang phản biện'],
          ['accepted', 'Được chấp nhận'],
          ['rejected', 'Bị từ chối'],
        ].map(([status, label]) => <option key={status} value={status}>{label}</option>)}
      </select>
    </>
  )
  return (
    <>
      <ResourceManager
        config={{ ...paperConfig, fields: (options) => paperConfig.fields(options) }}
        user={user}
        filters={filters}
        extraActions={(paper, { user: currentUser }) => (
          <>
            <button type="button" className="ai-row-button" title="Tóm tắt bằng AI" aria-label="Tóm tắt bài báo bằng AI" disabled={aiRequestInFlight} onClick={() => summarize(paper)}>
              <Sparkles size={14} /><span>AI tóm tắt</span>
            </button>
            {organizer(currentUser) && (
              <button type="button" className="ai-reviewer-row-button" title="Gợi ý người phản biện bằng AI" aria-label="AI gợi ý người phản biện" disabled={aiRequestInFlight} onClick={() => suggestReviewers(paper)}>
                <Users size={14} /><span>AI gợi ý phản biện</span>
              </button>
            )}
            {(organizer(currentUser) || author(currentUser)) && (
              <button type="button" className="row-action" title="Quản lý tác giả" aria-label="Quản lý tác giả" onClick={() => setSelectedPaper(paper)}>
                <BookUser size={15} />
              </button>
            )}
          </>
        )}
      />
      {selectedPaper && <PaperAuthors paper={selectedPaper} user={user} onClose={() => setSelectedPaper(null)} />}
      {aiSummary && <AiSummaryModal paper={aiSummary.paper} state={aiSummary} onClose={() => setAiSummary(null)} />}
      {aiReviewerSuggestions && (
        <AiReviewerSuggestionsModal
          paper={aiReviewerSuggestions.paper}
          state={aiReviewerSuggestions}
          onClose={() => setAiReviewerSuggestions(null)}
        />
      )}
    </>
  )
}

function Tabs({ tabs, active, onChange }) {
  return <div className="crud-tabs" role="tablist">{tabs.map((tab) => (
    <button key={tab.id} type="button" className={active === tab.id ? 'active' : ''} onClick={() => onChange(tab.id)} role="tab" aria-selected={active === tab.id}>{tab.label}</button>
  ))}</div>
}

function ManagedTable({ path, columns, fields, user, createAllowed, editAllowed, deleteAllowed, createLabel, emptyText, optionSources = NO_OPTION_SOURCES, renderActions, searchPlaceholder, onRowsChange }) {
  const [rows, setRows] = useState([])
  const [options, setOptions] = useState({})
  const [loading, setLoading] = useState(true)
  const [modalRecord, setModalRecord] = useState(undefined)
  const [busy, setBusy] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState(null)
  const formFields = useMemo(() => fields(options, user, modalRecord), [fields, options, modalRecord, user])
  const visibleRows = useMemo(() => {
    const term = search.trim().toLocaleLowerCase('vi')
    return term ? rows.filter((row) => Object.values(row).some((value) => String(value ?? '').toLocaleLowerCase('vi').includes(term))) : rows
  }, [rows, search])
  const load = useCallback(async () => {
    try {
      const response = await api.get(path)
      setRows(response.data)
      setError('')
      onRowsChange?.(response.data)
    } catch (requestError) {
      setRows([])
      setError(messageFromError(requestError))
    } finally {
      setLoading(false)
    }
  }, [onRowsChange, path])
  useEffect(() => {
    let active = true
    api.get(path)
      .then(({ data }) => {
        if (!active) return
        setRows(data)
        setError('')
        onRowsChange?.(data)
      })
      .catch((requestError) => {
        if (!active) return
        setRows([])
        setError(messageFromError(requestError))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [onRowsChange, path])
  useEffect(() => {
    let active = true
    Promise.all(optionSources.map(async (source) => [source.key, (await api.get(source.path)).data]))
      .then((entries) => { if (active) setOptions(Object.fromEntries(entries)) })
      .catch((requestError) => { if (active) setToast({ type: 'error', message: messageFromError(requestError) }) })
    return () => { active = false }
  }, [optionSources])

  async function save(values) {
    setBusy(true)
    setError('')
    try {
      const payload = Object.fromEntries(formFields
        .filter((field) => values[field.name] !== '')
        .map((field) => [field.name, field.type === 'number' ? Number(values[field.name])
          : field.type === 'datetime-local' ? new Date(values[field.name]).toISOString()
            : field.type === 'select' && field.options?.some((option) => typeof option.value === 'number') ? Number(values[field.name])
              : values[field.name]]))
      if (modalRecord) await api.put(`${path}/${modalRecord.id ?? modalRecord.user_id ?? modalRecord.assignment_id}`, payload)
      else await api.post(path, payload)
      setModalRecord(undefined)
      setToast({ type: 'success', message: modalRecord ? 'Đã cập nhật thông tin.' : 'Đã thêm dữ liệu.' })
      setLoading(true)
      await load()
    } catch (requestError) {
      setToast({ type: 'error', message: messageFromError(requestError) })
    } finally {
      setBusy(false)
    }
  }
  async function remove(row) {
    if (!window.confirm('Bạn có chắc chắn muốn xóa bản ghi này?')) return
    try {
      await api.delete(`${path}/${row.id ?? row.user_id ?? row.assignment_id}`)
      setToast({ type: 'success', message: 'Đã xóa bản ghi.' })
      setLoading(true)
      await load()
    } catch (requestError) {
      setToast({ type: 'error', message: messageFromError(requestError) })
    }
  }
  function submitSearch(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    load()
  }

  return (
    <section className="crud-panel">
      <div className="crud-toolbar">
        <div className="crud-toolbar-copy"><h2>{createLabel?.heading || ''}</h2><span>{visibleRows.length} bản ghi</span></div>
        {createAllowed && <button className="primary-button compact-button" type="button" onClick={() => setModalRecord(null)}><Users size={16} /> {createLabel?.button || 'Thêm mới'}</button>}
      </div>
      <form className="crud-searchbar" onSubmit={submitSearch}>
        <label className="search-input-wrap"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={searchPlaceholder || 'Tìm kiếm…'} /></label>
        <button className="secondary-button" type="submit">Tìm kiếm</button>
        <button className="icon-button" type="button" aria-label="Tải lại" onClick={() => { setLoading(true); setError(''); load() }}><RefreshCw size={16} /></button>
      </form>
      {error && <div className="page-message error">{error}</div>}
      <ResourceTable rows={visibleRows} columns={columns} loading={loading} emptyText={emptyText} canEdit={editAllowed} canDelete={deleteAllowed} onEdit={setModalRecord} onDelete={remove} renderActions={renderActions} />
      {modalRecord !== undefined && <FormModal title={modalRecord ? 'Cập nhật thông tin' : (createLabel?.title || 'Thêm mới')} fields={formFields} record={modalRecord} onClose={() => setModalRecord(undefined)} onSubmit={save} busy={busy} />}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </section>
  )
}

const reviewerCreateFields = () => [
  { name: 'user_id', label: 'Mã tài khoản phản biện', type: 'number', min: 1, required: true, hint: 'Nhập ID của tài khoản đã có vai trò reviewer.' },
  { name: 'expertise', label: 'Chuyên môn', type: 'textarea', required: true, wide: true },
  { name: 'max_assignments', label: 'Số phân công tối đa', type: 'number', min: 1, required: true },
]
const reviewerUpdateFields = () => [
  { name: 'expertise', label: 'Chuyên môn', type: 'textarea', required: true, wide: true },
  { name: 'max_assignments', label: 'Số phân công tối đa', type: 'number', min: 1, required: true },
]
const assignmentFields = (options) => [
  { name: 'paper_id', label: 'Bài báo', type: 'select', required: true, options: (options.papers || []).map((row) => ({ value: row.id, label: `${row.title} (#${row.id})` })) },
  { name: 'reviewer_id', label: 'Phản biện', type: 'select', required: true, options: (options.reviewers || []).map((row) => ({ value: row.user_id, label: `${row.full_name} (#${row.user_id})` })) },
  { name: 'deadline', label: 'Hạn phản biện', type: 'datetime-local', required: true },
]
const assignmentUpdateFields = () => [
  { name: 'deadline', label: 'Hạn phản biện', type: 'datetime-local', required: true },
  { name: 'status', label: 'Trạng thái', type: 'select', required: true, options: [
    { value: 'assigned', label: 'Đã phân công' }, { value: 'in_progress', label: 'Đang thực hiện' },
    { value: 'completed', label: 'Hoàn thành' }, { value: 'declined', label: 'Đã từ chối' },
  ] },
]
const reviewFields = (options) => [
  { name: 'assignment_id', label: 'Mã phân công của bạn', type: 'select', required: true, options: (options.assignments || [])
    .filter((row) => ['assigned', 'in_progress'].includes(row.status) && new Date(row.deadline) > new Date())
    .map((row) => ({ value: row.id, label: `Phân công #${row.id} · Bài báo #${row.paper_id}` })) },
  { name: 'comments', label: 'Nhận xét', type: 'textarea', required: true, wide: true, rows: 5 },
  { name: 'recommendation', label: 'Kết quả đề xuất', type: 'select', required: true, options: [
    { value: 'accept', label: 'Chấp nhận' }, { value: 'minor_revision', label: 'Sửa nhỏ' },
    { value: 'major_revision', label: 'Sửa lớn' }, { value: 'reject', label: 'Từ chối' },
  ] },
  { name: 'score', label: 'Điểm đánh giá (1–5)', type: 'number', min: 1, max: 5, required: true },
]
const reviewUpdateFields = () => reviewFields({ assignments: [] }).slice(1)

export function ReviewPage({ user }) {
  const isOrganizer = organizer(user)
  const isReviewer = reviewer(user)
  const [tab, setTab] = useState(isOrganizer ? 'profiles' : 'assignments')
  const profileFields = useCallback((_options, _currentUser, record) => record ? reviewerUpdateFields() : reviewerCreateFields(), [])
  const assignmentFormFields = useCallback((options, _currentUser, record) => record ? assignmentUpdateFields() : assignmentFields(options), [])
  const reviewFormFields = useCallback((options, _currentUser, record) => record ? reviewUpdateFields() : reviewFields(options), [])

  if (!isOrganizer && !isReviewer) {
    return <div className="page-stack"><div className="page-message error">Tài khoản không có quyền truy cập chức năng phản biện.</div></div>
  }
  return (
    <div className="page-stack">
      <section className="crud-panel review-panel">
        <div className="crud-toolbar"><div className="crud-toolbar-copy"><h2>Quản lý phản biện khoa học</h2><span>Hồ sơ, phân công và đánh giá theo quyền tài khoản.</span></div></div>
        <Tabs
          active={tab}
          onChange={setTab}
          tabs={[
            ...(isOrganizer ? [{ id: 'profiles', label: 'Hồ sơ phản biện' }, { id: 'assignments', label: 'Phân công' }] : [{ id: 'assignments', label: 'Bài được giao' }]),
            { id: 'reviews', label: 'Đánh giá' },
          ]}
        />
      </section>
      {tab === 'profiles' && isOrganizer && (
        <ManagedTable
          path="/reviewers"
          columns={['user_id', 'full_name', 'email', 'expertise', 'max_assignments']}
          fields={profileFields}
          user={user}
          createAllowed
          editAllowed={() => true}
          deleteAllowed={() => true}
          createLabel={{ heading: 'Hồ sơ phản biện', button: 'Thêm hồ sơ', title: 'Tạo hồ sơ phản biện' }}
          optionSources={[]}
          emptyText="Chưa có hồ sơ phản biện."
        />
      )}
      {tab === 'assignments' && (
        <ManagedTable
          path="/review-assignments"
          columns={['id', 'paper_id', 'reviewer_id', 'deadline', 'status']}
          fields={assignmentFormFields}
          user={user}
          createAllowed={isOrganizer}
          editAllowed={isOrganizer ? () => true : undefined}
          deleteAllowed={isOrganizer ? () => true : undefined}
          createLabel={{ heading: 'Phân công bài báo', button: 'Tạo phân công', title: 'Tạo phân công' }}
          optionSources={isOrganizer ? [{ key: 'papers', path: '/papers' }, { key: 'reviewers', path: '/reviewers' }] : []}
          emptyText={isReviewer ? 'Bạn chưa có bài báo được phân công.' : 'Chưa có phân công.'}
        />
      )}
      {tab === 'reviews' && (
        <ManagedTable
          path="/reviews"
          columns={['id', 'assignment_id', 'recommendation', 'score', 'comments', 'submitted_at']}
          fields={reviewFormFields}
          user={user}
          createAllowed={isReviewer}
          editAllowed={isReviewer ? () => true : undefined}
          deleteAllowed={undefined}
          createLabel={{ heading: 'Đánh giá phản biện', button: 'Gửi đánh giá', title: 'Gửi đánh giá' }}
          optionSources={isReviewer ? [{ key: 'assignments', path: '/review-assignments' }] : []}
          emptyText={isReviewer ? 'Bạn chưa gửi đánh giá nào.' : 'Chưa có đánh giá.'}
        />
      )}
    </div>
  )
}
