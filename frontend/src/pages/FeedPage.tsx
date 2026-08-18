import { useRef } from 'react';

import PostCard from '../components/PostCard';
import PostComposer from '../components/PostComposer';
import FeedSkeletons from '../components/FeedSkeletons';
import { EmptyState, ErrorState, StaleBanner } from '../components/FeedStates';
import { useAuth } from '../context/AuthContext';
import { usePosts } from '../hooks/usePosts';

export default function FeedPage() {
  const { user, logout } = useAuth();
  const { posts, status, error, isStale, retry, addPostOptimistic } = usePosts();
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  const focusComposer = () => {
    composerRef.current?.focus();
  };

  return (
    <div className="feed-shell">
      <header className="topbar">
        <h1 className="logotype">
          Mini<span className="logotype-accent">Feed</span>
        </h1>
        <div className="topbar-user">
          {user && <span className="user-badge">{user.username}</span>}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            aria-label="Refresh feed"
            onClick={retry}
          >
            Refresh
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      <div className="feed-column">
        {isStale && <StaleBanner onRefresh={retry} />}

        <PostComposer onPosted={addPostOptimistic} inputRef={composerRef} />

        {status === 'loading' && <FeedSkeletons />}

        {status === 'error' && <ErrorState onRetry={retry} message={error} />}

        {status === 'ready' && posts.length === 0 && (
          <EmptyState onCompose={focusComposer} />
        )}

        {status === 'ready' && posts.length > 0 && (
          <div className="post-list">
            {posts.map((post) => (
              <PostCard key={post.id} post={post} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}