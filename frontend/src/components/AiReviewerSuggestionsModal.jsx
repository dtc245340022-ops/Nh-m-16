import { AlertTriangle, LoaderCircle, Sparkles, UserRound, X } from 'lucide-react'

export default function AiReviewerSuggestionsModal({ paper, state, onClose }) {
  return (
    <div className="modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="form-modal ai-reviewer-modal" role="dialog" aria-modal="true" aria-labelledby="ai-reviewer-title">
        <div className="modal-heading">
          <div>
            <span className="eyebrow"><Sparkles size={13} /> HỖ TRỢ AI · BÀI BÁO #{paper.id}</span>
            <h2 id="ai-reviewer-title">Gợi ý người phản biện</h2>
          </div>
          <button type="button" className="icon-button" aria-label="Đóng" onClick={onClose}><X size={18} /></button>
        </div>
        <p className="ai-summary-paper-title">{paper.title}</p>
        {state.loading && (
          <div className="ai-summary-loading" role="status">
            <span className="ai-loading-icon"><LoaderCircle size={23} /></span>
            <strong>Đang đối chiếu nội dung và chuyên môn…</strong>
            <span>Chỉ phản biện có hồ sơ trong hệ thống mới được xét.</span>
          </div>
        )}
        {state.error && (
          <div className="ai-summary-error" role="alert">
            <AlertTriangle size={18} />
            <div><strong>Chưa thể tạo gợi ý</strong><span>{state.error}</span></div>
          </div>
        )}
        {state.result && (
          <div className="ai-reviewer-results">
            {state.result.suggestions.length ? state.result.suggestions.map((reviewer) => (
              <article className="ai-reviewer-card" key={reviewer.reviewer_id}>
                <div className="ai-reviewer-identity">
                  <span className="ai-reviewer-avatar"><UserRound size={18} /></span>
                  <div><strong>{reviewer.full_name}</strong><span>Mã phản biện #{reviewer.reviewer_id}</span></div>
                </div>
                <div className="ai-reviewer-expertise"><strong>Chuyên môn</strong><span>{reviewer.expertise}</span></div>
                <div className="ai-reviewer-reason"><strong>Lý do gợi ý</strong><p>{reviewer.reason}</p></div>
              </article>
            )) : (
              <div className="ai-reviewer-empty">
                Không tìm thấy ứng viên phù hợp còn khả dụng. Có thể chưa có hồ sơ phản biện phù hợp hoặc các ứng viên đã được phân công/tới giới hạn.
              </div>
            )}
            <div className="ai-warning"><AlertTriangle size={17} /><span>{state.result.warning}</span></div>
          </div>
        )}
        <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Đóng</button></div>
      </section>
    </div>
  )
}
