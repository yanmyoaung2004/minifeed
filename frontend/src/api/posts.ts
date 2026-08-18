import { apiClient } from './client';
import type { Post, PostCreate } from './types';

export interface PostsResponse {
  posts: Post[];
  cacheStatus: string | null;
}

export async function getPosts(): Promise<PostsResponse> {
  const response = await apiClient.get<Post[]>('/posts');
  return {
    posts: response.data,
    cacheStatus: response.headers['x-cache'] ?? null,
  };
}

export async function createPost(content: string): Promise<Post> {
  const payload: PostCreate = { content };
  const { data } = await apiClient.post<Post>('/posts', payload);
  return data;
}