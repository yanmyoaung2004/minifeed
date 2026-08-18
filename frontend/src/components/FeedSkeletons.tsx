interface FeedSkeletonsProps {
  count?: number;
}

export default function FeedSkeletons({ count = 3 }: FeedSkeletonsProps) {
  return (
    <div className="skeleton-list" aria-label="Loading posts" aria-busy="true">
      {Array.from({ length: count }).map((_, index) => (
        <div className="skeleton-row" key={index}>
          <div className="skeleton-avatar" />
          <div className="skeleton-lines">
            <div className="skeleton-line skeleton-line-short" />
            <div className="skeleton-line" />
            <div className="skeleton-line skeleton-line-medium" />
          </div>
        </div>
      ))}
    </div>
  );
}