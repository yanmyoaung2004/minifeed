export default function FeedPage() {
  return (
    <div className="feed-shell">
      <header className="topbar">
        <h1 className="logotype">
          Mini<span className="logotype-accent">Feed</span>
        </h1>
        <span className="auth-tagline">Feed UI lands in the next phase.</span>
      </header>

      <div className="feed-column">
        <section className="composer" aria-label="New post">
          <textarea
            className="input"
            placeholder="What's on your mind?"
            maxLength={500}
            disabled
          />
          <div className="composer-footer">
            <span className="character-count">0/500</span>
            <button className="btn btn-primary" type="button" disabled>
              Post
            </button>
          </div>
        </section>

        <section className="empty-state">
          <h2 className="empty-state-title">No posts yet.</h2>
          <p className="empty-state-copy">Be the first to post.</p>
        </section>
      </div>
    </div>
  );
}