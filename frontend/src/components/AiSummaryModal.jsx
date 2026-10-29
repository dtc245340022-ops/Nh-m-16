import { AlertTriangle, CheckCircle2, LoaderCircle, Sparkles, X } from 'lucide-react'

export default function AiSummaryModal({ paper, state, onClose }) {
  return (
    <div className="modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="form-modal ai-summary-modal" role="dialog" aria-modal="true" aria-labelledby="ai-summary-title">
        <div className="modal-heading">
          <div>
            <span className="eyebrow"><Sparkles size={13} /> HỖ TRỢ AI · BÀI BÁO #{paper.id}</span>
            <h2 id="ai-summary-title">Tóm tắt bài báo</h2>
          </div>
          <button type="button" className="icon-button" aria-label="Đóng" onClick={onClose}><X size={18} /></button>
        </div>
        <p className="ai-summary-paper-title">{paper.title}</p>
        {state.loading && (
          <div className="ai-summary-loading" role="status">
            <span className="ai-loading-icon"><LoaderCircle size={23} /></span>
            <strong>AI đang đọc nội dung bài báo…</strong>
            <span>Vui lòng đợi trong giây lát.</span>
          </div>
        )}
        {state.error && (
          <div className="ai-summary-error" role="alert">
            <AlertTriangle size={18} />
            <div><strong>Chưa thể tạo bản tóm tắt</strong><span>{state.error}</span></div>
          </div>
        )}
        {state.result && (
          <div className="ai-summary-result">
            <section className="ai-result-section">
              <h3><CheckCircle2 size={16} /> Tóm tắt ngắn gọn</h3>
              <p>{state.result.summary}</p>
            </section>
            <section className="ai-result-section">
              <h3>Các ý chính</h3>
              <ul>{state.result.key_points.map((point, index) => <li key={`${index}-${point}`}>{point}</li>)}</ul>
            </section>
            <section className="ai-result-section">
              <h3>Từ khóa quan trọng</h3>
              {state.result.important_keywords.length ? (
                <div className="ai-keyword-list">{state.result.important_keywords.map((keyword, index) => <span key={`${index}-${keyword}`}>{keyword}</span>)}</div>
              ) : <p className="ai-no-keywords">Không trích xuất được từ khóa bổ sung.</p>}
            </section>
            <div className="ai-warning"><AlertTriangle size={17} /><span>{state.result.warning}</span></div>
          </div>
        )}
        <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Đóng</button></div>
      </section>
    </div>
  )
}
