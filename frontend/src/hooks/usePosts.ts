import { useCallback, useEffect, useRef, useState } from 'react';

import { getPosts } from '../api/posts';
import type { Post } from '../api/types';

export type FeedStatus = 'loading' | 'ready' | 'error';

export interface UsePostsResult {
  posts: Post[];
  status: FeedStatus;
  error: string | null;
  isStale: boolean;
  retry: () => void;
  refresh: () => void;
  addPostOptimistic: (post: Post) => void;
}

export function usePosts(search: string = ''): UsePostsResult {
  const [posts, setPosts] = useState<Post[]>([]);
  const [status, setStatus] = useState<FeedStatus>('loading');
  const [error, setError] = useState<string | null>(null);
  const [isStale, setIsStale] = useState(false);
  const postsRef = useRef<Post[]>([]);
  const searchRef = useRef(search);

  useEffect(() => {
    postsRef.current = posts;
  }, [posts]);

  useEffect(() => {
    searchRef.current = search;
  }, [search]);

  const load = useCallback(async () => {
    try {
      const { posts: fresh } = await getPosts(searchRef.current);
      postsRef.current = fresh;
      setPosts(fresh);
      setStatus('ready');
      setError(null);
      setIsStale(false);
    } catch {
      if (postsRef.current.length > 0) {
        setIsStale(true);
      } else {
        setStatus('error');
        setError("Couldn't load posts.");
      }
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, search]);

  const retry = useCallback(() => {
    if (postsRef.current.length === 0) {
      setStatus('loading');
      setError(null);
    }
    load();
  }, [load]);

  const refresh = useCallback(() => {
    load();
  }, [load]);

  const addPostOptimistic = useCallback((post: Post) => {
    postsRef.current = [post, ...postsRef.current];
    setPosts((prev) => [post, ...prev]);
  }, []);

  return { posts, status, error, isStale, retry, refresh, addPostOptimistic };
}