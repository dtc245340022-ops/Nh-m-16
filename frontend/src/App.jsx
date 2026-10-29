import { useEffect, useMemo, useState } from 'react'
import {
  ArrowDownRight,
  ArrowUpRight,
  Bell,
  BookOpen,
  CalendarDays,
  ChevronDown,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  Settings2,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react'
import {
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { useAuth } from './auth-context.js'
import { api } from './api.js'
import {
  ConferencePage,
  PaperPage,
  RegistrationPage,
  ReviewPage,
  SessionPage,
} from './pages/ManagementPages.jsx'
import './App.css'

const roleNames = {
  organizer: 'Ban tổ chức',
  author: 'Tác giả',
  reviewer: 'Phản biện',
  admin: 'Quản trị viên',
}

const navigationByRole = {
  organizer: [
    { label: 'Tổng quan', path: '/', icon: LayoutDashboard },
    { label: 'Hội nghị', path: '/conferences', icon: CalendarDays },
    { label: 'Bài báo', path: '/papers', icon: FileText },
    { label: 'Phản biện', path: '/reviews', icon: ClipboardCheck },
    { label: 'Phiên trình bày', path: '/sessions', icon: BookOpen },
    { label: 'Đăng ký', path: '/registrations', icon: Users },
    { label: 'Thống kê', path: '/statistics', icon: Settings2 },
  ],
  author: [
    { label: 'Tổng quan', path: '/', icon: LayoutDashboard },
    { label: 'Hội nghị', path: '/conferences', icon: CalendarDays },
    { label: 'Bài báo', path: '/papers', icon: FileText },
    { label: 'Đăng ký', path: '/registrations', icon: Users },
  ],
  reviewer: [
    { label: 'Tổng quan', path: '/', icon: LayoutDashboard },
    { label: 'Hội nghị', path: '/conferences', icon: CalendarDays },
    { label: 'Bài báo được giao', path: '/papers', icon: FileText },
    { label: 'Phản biện', path: '/reviews', icon: ClipboardCheck },
  ],
}

const sectionConfig = {
  '/conferences': {
    title: 'Hội nghị',
    subtitle: 'Danh sách các hội nghị khoa học trong hệ thống.',
    endpoints: [{ label: 'Hội nghị', path: '/conferences' }],
    columns: ['title', 'venue', 'starts_at', 'ends_at'],
  },
  '/papers': {
    title: 'Bài báo khoa học',
    subtitle: 'Các bài báo bạn có quyền xem trong hệ thống.',
    endpoints: [{ label: 'Bài báo', path: '/papers' }],
    columns: ['title', 'keywords', 'status', 'conference_id'],
  },
  '/sessions': {
    title: 'Phiên trình bày',
    subtitle: 'Lịch trình các phiên thuộc hội nghị.',
    endpoints: [{ label: 'Phiên trình bày', path: '/sessions' }],
    columns: ['title', 'room', 'starts_at', 'ends_at', 'conference_id'],
  },
  '/registrations': {
    title: 'Đăng ký tham dự',
    subtitle: 'Danh sách đăng ký được giới hạn theo quyền tài khoản.',
    endpoints: [{ label: 'Đăng ký', path: '/registrations' }],
    columns: ['conference_id', 'user_id', 'status', 'registered_at'],
  },
  '/reviews': {
    title: 'Phản biện khoa học',
    subtitle: 'Phân công và đánh giá phản biện trong phạm vi quyền của bạn.',
    endpoints: [
      { label: 'Phân công', path: '/review-assignments' },
      { label: 'Đánh giá', path: '/reviews' },
    ],
    columns: ['paper_id', 'reviewer_id', 'status', 'deadline'],
    secondaryColumns: ['assignment_id', 'recommendation', 'score', 'comments'],
  },
  '/statistics': {
    title: 'Thống kê hệ thống',
    subtitle: 'Số liệu được tải trực tiếp từ API backend.',
    endpoints: [{ label: 'Thống kê', path: '/statistics' }],
  },
}

const metricConfig = [
  { key: 'conferences', label: 'Hội nghị', icon: CalendarDays, color: 'blue' },
  { key: 'papers', label: 'Bài báo', icon: FileText, color: 'mint' },
  { key: 'reviewers', label: 'Phản biện', icon: Users, color: 'violet' },
  { key: 'registrations', label: 'Đăng ký', icon: ClipboardCheck, color: 'amber' },
  { key: 'accepted_papers', label: 'Bài được chấp nhận', icon: ArrowUpRight, color: 'mint' },
  { key: 'rejected_papers', label: 'Bài bị từ chối', icon: ArrowDownRight, color: 'rose' },
  { key: 'overdue_reviews', label: 'Phản biện quá hạn', icon: Bell, color: 'amber' },
]

const fieldLabels = {
  title: 'Tiêu đề',
  venue: 'Địa điểm',
  starts_at: 'Bắt đầu',
  ends_at: 'Kết thúc',
  keywords: 'Từ khóa',
  status: 'Trạng thái',
  conference_id: 'Mã hội nghị',
  room: 'Phòng',
  user_id: 'Mã tài khoản',
  registered_at: 'Ngày đăng ký',
  paper_id: 'Mã bài báo',
  reviewer_id: 'Mã phản biện',
  deadline: 'Hạn phản biện',
  assignment_id: 'Mã phân công',
  recommendation: 'Kết quả',
  score: 'Điểm',
  comments: 'Nhận xét',
}

const statusLabels = {
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

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Có' : 'Không'
  if (typeof value === 'string' && statusLabels[value]) return statusLabels[value]
  if (typeof value === 'string' && /^\d{4}-\d\d-\d\dT/.test(value)) {
    return new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))
  }
  return String(value)
}

function PageMessage({ children, variant = 'info' }) {
  return <div className={`page-message ${variant}`}>{children}</div>
}

function MetricCard({ metric, value }) {
  const Icon = metric.icon
  return (
    <article className="metric-card">
      <div className={`metric-icon ${metric.color}`}><Icon size={19} /></div>
      <p>{metric.label}</p>
      <strong>{value}</strong>
      <span className="metric-note">Dữ liệu hệ thống</span>
    </article>
  )
}

function TableSection({ label, rows, columns }) {
  if (!Array.isArray(rows)) {
    return <PageMessage variant="error">Dữ liệu trả về không đúng định dạng.</PageMessage>
  }
  return (
    <section className="data-card">
      <div className="data-card-heading">
        <div>
          <h2>{label}</h2>
          <span>{rows.length} bản ghi</span>
        </div>
        <button className="icon-button" type="button" aria-label="Tìm kiếm">
          <Search size={17} />
        </button>
      </div>
      {rows.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><FileText size={22} /></div>
          <strong>Chưa có dữ liệu</strong>
          <span>Danh sách sẽ hiển thị tại đây khi có bản ghi.</span>
        </div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>{columns.map((column) => <th key={column}>{fieldLabels[column] || column.replaceAll('_', ' ')}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.id ?? `${row.assignment_id ?? 'row'}-${index}`}>
                  {columns.map((column) => (
                    <td key={column}>
                      {column === 'status' ? (
                        <span className={`status-pill status-${row[column]}`}>
                          {formatValue(row[column])}
                        </span>
                      ) : (
                        <span className={column === 'title' ? 'table-primary' : ''}>
                          {formatValue(row[column])}
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function usePageData(endpoints) {
  const [result, setResult] = useState({ key: '', loading: true, entries: [], error: '' })
  const endpointKey = JSON.stringify(endpoints)
  const loading = result.key !== endpointKey || result.loading

  useEffect(() => {
    let active = true
    const requestEndpoints = JSON.parse(endpointKey)
    Promise.all(
      requestEndpoints.map(async (endpoint) => {
        const response = await api.get(endpoint.path)
        return { ...endpoint, data: response.data }
      }),
    )
      .then((entries) => {
        if (active) setResult({ key: endpointKey, loading: false, entries, error: '' })
      })
      .catch((error) => {
        if (!active) return
        const status = error.response?.status
        const message = status === 403
          ? 'Tài khoản của bạn không có quyền xem mục này.'
          : error.response?.data?.detail || 'Không thể tải dữ liệu. Vui lòng thử lại.'
        setResult({ key: endpointKey, loading: false, entries: [], error: message })
      })
    return () => { active = false }
  }, [endpointKey])

  return { ...result, loading }
}

function DataPage({ config }) {
  const { entries, loading, error } = usePageData(config.endpoints)
  return (
    <div className="page-stack">
      {loading && <PageMessage>Đang tải dữ liệu từ hệ thống…</PageMessage>}
      {error && <PageMessage variant="error">{error}</PageMessage>}
      {!loading && !error && entries.map((entry, index) => (
        <TableSection
          key={entry.path}
          label={entry.label}
          rows={Array.isArray(entry.data) ? entry.data : [entry.data]}
          columns={
            index === 1 && config.secondaryColumns
              ? config.secondaryColumns
              : config.columns || Object.keys(entry.data || {})
          }
        />
      ))}
      <p className="read-only-note">
        <ShieldCheck size={15} /> Số liệu được tải trực tiếp từ API; quyền truy cập được kiểm soát ở máy chủ.
      </p>
    </div>
  )
}

function Dashboard({ user }) {
  const [state, setState] = useState({ loading: true, metrics: [], error: '' })
  const isOrganizer = user.role === 'organizer' || user.role === 'admin'

  useEffect(() => {
    let active = true
    const sources = isOrganizer
      ? [{ path: '/statistics', label: 'statistics' }]
      : user.role === 'author'
        ? [
            { path: '/papers', label: 'papers' },
            { path: '/registrations', label: 'registrations' },
          ]
        : [
            { path: '/review-assignments', label: 'assignments' },
            { path: '/reviews', label: 'reviews' },
          ]

    Promise.all(
      sources.map(async (source) => ({
        ...source,
        data: (await api.get(source.path)).data,
      })),
    )
      .then((responses) => {
        if (!active) return
        const metrics = isOrganizer
          ? metricConfig.map((metric) => ({
              ...metric,
              value: responses[0].data[metric.key],
            }))
          : responses.map((response) => ({
              key: response.label,
              label: response.label === 'papers' ? 'Bài báo của tôi'
                : response.label === 'registrations' ? 'Đăng ký tham dự'
                  : response.label === 'assignments' ? 'Bài được phân công'
                    : 'Đánh giá đã gửi',
              value: Array.isArray(response.data) ? response.data.length : 0,
              icon: response.label === 'papers' ? FileText
                : response.label === 'registrations' ? Users
                  : ClipboardCheck,
              color: 'blue',
            }))
        setState({ loading: false, metrics, error: '' })
      })
      .catch((error) => {
        if (!active) return
        setState({
          loading: false,
          metrics: [],
          error: error.response?.status === 403
            ? 'Tài khoản chưa được cấp quyền xem số liệu tổng quan.'
            : error.response?.data?.detail || 'Không thể tải dữ liệu tổng quan.',
        })
      })
    return () => { active = false }
  }, [isOrganizer, user.role])

  const greetingName = user.full_name?.trim().split(/\s+/).at(-1) || user.email
  return (
    <div className="dashboard-content">
      <section className="welcome-panel">
        <div className="welcome-copy">
          <span className="eyebrow">KHÔNG GIAN LÀM VIỆC</span>
          <h2>Xin chào, {greetingName} <span aria-hidden="true">👋</span></h2>
          <p>
            {isOrganizer
              ? 'Theo dõi toàn cảnh hoạt động hội nghị và các công việc cần quan tâm.'
              : user.role === 'author'
                ? 'Theo dõi bài báo và thông tin tham dự hội nghị của bạn.'
                : 'Theo dõi các bài báo được phân công và tiến độ phản biện.'}
          </p>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <div className="art-orbit orbit-one" />
          <div className="art-orbit orbit-two" />
          <div className="art-paper"><BookOpen size={36} /></div>
          <span className="art-dot dot-one" />
          <span className="art-dot dot-two" />
        </div>
      </section>

      <div className="section-title-row">
        <div>
          <span className="eyebrow">TỔNG QUAN</span>
          <h2>{isOrganizer ? 'Chỉ số hoạt động' : 'Hoạt động của bạn'}</h2>
        </div>
        <span className="live-indicator"><i /> Dữ liệu trực tiếp</span>
      </div>

      {state.loading && <PageMessage>Đang đồng bộ dữ liệu…</PageMessage>}
      {state.error && <PageMessage variant="error">{state.error}</PageMessage>}
      {!state.loading && !state.error && (
        <div className={`metrics-grid ${isOrganizer ? 'organizer-metrics' : 'personal-metrics'}`}>
          {state.metrics.map((metric) => (
            <MetricCard key={metric.key} metric={metric} value={metric.value ?? '—'} />
          ))}
        </div>
      )}

      <section className="bottom-note">
        <div className="bottom-note-icon"><ShieldCheck size={19} /></div>
        <div>
          <strong>Không gian làm việc an toàn</strong>
          <p>Dữ liệu được hiển thị theo quyền truy cập của tài khoản {roleNames[user.role] || user.role}.</p>
        </div>
      </section>
    </div>
  )
}

function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
    } catch (loginError) {
      const status = loginError.response?.status
      setError(status === 401
        ? 'Email hoặc mật khẩu chưa chính xác.'
        : loginError.response?.data?.detail || 'Không thể kết nối máy chủ. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-aside">
        <Link to="/" className="brand login-brand">
          <span className="brand-mark"><BookOpen size={21} /></span>
          <span>CONFERENCE<span className="brand-light">HUB</span></span>
        </Link>
        <div className="login-aside-copy">
          <span className="eyebrow light-eyebrow">NỀN TẢNG HỌC THUẬT</span>
          <h1>Kết nối tri thức.<br /><span>Lan tỏa nghiên cứu.</span></h1>
          <p>Không gian làm việc dành cho ban tổ chức, tác giả và chuyên gia phản biện khoa học.</p>
        </div>
        <div className="login-decoration" aria-hidden="true">
          <div className="login-decoration-card"><BookOpen size={42} /></div>
          <div className="login-decoration-line" />
          <span className="login-decoration-label">RESEARCH · CONNECT · GROW</span>
        </div>
        <span className="login-copyright">© 2026 ConferenceHub · Hệ thống quản lý hội nghị khoa học</span>
      </div>
      <section className="login-main">
        <div className="login-form-wrap">
          <span className="eyebrow">CHÀO MỪNG TRỞ LẠI</span>
          <h2>Đăng nhập</h2>
          <p className="login-description">Nhập thông tin tài khoản để tiếp tục.</p>
          {error && <PageMessage variant="error">{error}</PageMessage>}
          <form className="login-form" onSubmit={handleSubmit}>
            <label htmlFor="email">Địa chỉ email</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              placeholder="ten@donvi.edu.vn"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <div className="password-label">
              <label htmlFor="password">Mật khẩu</label>
            </div>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="Nhập mật khẩu"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            <button className="primary-button login-submit" type="submit" disabled={submitting}>
              {submitting ? <span className="spinner" /> : 'Đăng nhập'}
            </button>
          </form>
          <div className="login-security"><ShieldCheck size={16} /> Kết nối được bảo vệ bằng xác thực an toàn</div>
        </div>
      </section>
    </main>
  )
}

function ApplicationLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [today] = useState(() => new Date())
  const navigation = useMemo(
    () => navigationByRole[user.role] || navigationByRole.organizer,
    [user.role],
  )
  const currentPage = navigation.find((item) => item.path === location.pathname)
  const title = currentPage?.label || sectionConfig[location.pathname]?.title || 'Tổng quan'

  return (
    <div className="app-shell">
      {mobileOpen && <button className="sidebar-backdrop" onClick={() => setMobileOpen(false)} aria-label="Đóng menu" />}
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <Link to="/" className="brand">
            <span className="brand-mark"><BookOpen size={20} /></span>
            <span>CONFERENCE<span className="brand-light">HUB</span></span>
          </Link>
          <button className="mobile-close icon-button" onClick={() => setMobileOpen(false)} aria-label="Đóng menu">
            <X size={18} />
          </button>
        </div>
        <div className="workspace-label">KHÔNG GIAN LÀM VIỆC</div>
        <nav className="side-nav" aria-label="Điều hướng chính">
          {navigation.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                <Icon size={18} strokeWidth={1.8} />
                <span>{item.label}</span>
                {item.path === '/' && <span className="nav-active-dot" />}
              </NavLink>
            )
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-help">
            <div className="help-mark"><ShieldCheck size={18} /></div>
            <div><strong>Hỗ trợ học thuật</strong><span>Không gian bảo mật</span></div>
          </div>
          <button className="sidebar-logout" onClick={logout}>
            <LogOut size={17} /><span>Đăng xuất</span>
          </button>
          <div className="sidebar-version">CONFERENCEHUB <span>v1.0</span></div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu icon-button" onClick={() => setMobileOpen(true)} aria-label="Mở menu">
              <Menu size={20} />
            </button>
            <div className="breadcrumb"><span>Không gian làm việc</span><i>/</i><strong>{title}</strong></div>
          </div>
          <div className="topbar-actions">
            <span className="topbar-date">{new Intl.DateTimeFormat('vi-VN', { dateStyle: 'long' }).format(today)}</span>
            <button className="icon-button notification-button" aria-label="Thông báo"><Bell size={18} /><i /></button>
            <div className="topbar-divider" />
            <div className="account-menu">
              <div className="avatar">{(user.full_name || user.email).slice(0, 1).toUpperCase()}</div>
              <div className="account-info"><strong>{user.full_name}</strong><span>{roleNames[user.role] || user.role}</span></div>
              <ChevronDown size={15} className="account-chevron" />
            </div>
          </div>
        </header>

        <main className="page-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">{location.pathname === '/' ? 'BẢNG ĐIỀU KHIỂN' : 'QUẢN LÝ HỌC THUẬT'}</span>
              <h1>{title}</h1>
            </div>
            <div className="heading-date"><CalendarDays size={16} /> {new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' }).format(today)}</div>
          </div>
          <Routes>
            <Route path="/" element={<Dashboard user={user} />} />
            {Object.entries(sectionConfig).map(([path, config]) => (
              <Route
                key={path}
                path={path}
                element={
                  path === '/conferences' ? <ConferencePage user={user} />
                    : path === '/papers' ? <PaperPage user={user} />
                      : path === '/sessions' ? <SessionPage user={user} />
                        : path === '/registrations' ? <RegistrationPage user={user} />
                          : path === '/reviews' ? <ReviewPage user={user} />
                            : <DataPage config={config} />
                }
              />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <footer className="app-footer">
          <span>© 2026 ConferenceHub</span>
          <span>Hệ thống quản lý hội nghị khoa học</span>
        </footer>
      </div>
    </div>
  )
}

function AuthenticatedApp() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return <div className="app-loading"><span className="spinner" /> Đang kiểm tra phiên đăng nhập…</div>
  }
  if (!user && location.pathname !== '/login') return <Navigate to="/login" replace />
  if (user && location.pathname === '/login') return <Navigate to="/" replace />
  return user ? <ApplicationLayout /> : <LoginPage />
}

export default function App() {
  return <AuthenticatedApp />
}
