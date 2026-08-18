import { useEffect, useRef, useState } from 'react';

import type { Post } from '../api/types';
import PostCard from '../components/PostCard';
import PostComposer from '../components/PostComposer';
import FeedSkeletons from '../components/FeedSkeletons';
import { ErrorState, StaleBanner } from '../components/FeedStates';
import { useAuth } from '../context/AuthContext';
import { usePosts } from '../hooks/usePosts';

export default function FeedPage() {
  const { user, logout } = useAuth();
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const { posts, status, error, isStale, retry, refresh, addPostOptimistic } =
    usePosts(debouncedSearch);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const isSearching = debouncedSearch.length > 0;

  const focusComposer = () => {
    composerRef.current?.focus();
  };

  const handlePosted = (post: Post) => {
    if (isSearching) {
      refresh();
    } else {
      addPostOptimistic(post);
    }
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

        <label className="sr-only" htmlFor="feed-search">
          Search posts
        </label>
        <input
          id="feed-search"
          className="input search-input"
          type="search"
          placeholder="Search posts…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          autoComplete="off"
        />

        <PostComposer onPosted={handlePosted} inputRef={composerRef} />

        {status === 'loading' && <FeedSkeletons />}

        {status === 'error' && <ErrorState onRetry={retry} message={error} />}

        {status === 'ready' && posts.length === 0 && (
          <section className="empty-state">
            <h2 className="empty-state-title">
              {isSearching ? 'No posts match your search.' : 'No posts yet.'}
            </h2>
            <p className="empty-state-copy">
              {isSearching
                ? 'Try a different keyword.'
                : 'Be the first to share!'}
            </p>
            {!isSearching && (
              <button type="button" className="btn btn-primary" onClick={focusComposer}>
                Write a post
              </button>
            )}
          </section>
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