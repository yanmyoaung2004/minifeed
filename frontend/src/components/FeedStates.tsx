interface EmptyStateProps {
  onCompose: () => void;
}

export function EmptyState({ onCompose }: EmptyStateProps) {
  return (
    <section className="empty-state">
      <h2 className="empty-state-title">No posts yet.</h2>
      <p className="empty-state-copy">Be the first to share!</p>
      <button type="button" className="btn btn-primary" onClick={onCompose}>
        Write a post
      </button>
    </section>
  );
}

interface ErrorStateProps {
  onRetry: () => void;
  message?: string | null;
}

export function ErrorState({ onRetry, message }: ErrorStateProps) {
  return (
    <section className="empty-state" role="alert">
      <h2 className="empty-state-title">{message ?? "Couldn't load posts."}</h2>
      <p className="empty-state-copy">Something went wrong on our side.</p>
      <button type="button" className="btn btn-primary" onClick={onRetry}>
        Retry
      </button>
    </section>
  );
}

interface StaleBannerProps {
  onRefresh: () => void;
}

export function StaleBanner({ onRefresh }: StaleBannerProps) {
  return (
    <div className="alert" role="status">
      <span>Couldn't refresh — showing earlier posts.</span>
      <button type="button" className="btn btn-ghost btn-sm" onClick={onRefresh}>
        Retry
      </button>
    </div>
  );
}