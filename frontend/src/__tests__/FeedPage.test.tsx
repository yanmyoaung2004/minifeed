import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { fireEvent } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { userEvent } from '@testing-library/user-event';

import FeedPage from '../pages/FeedPage';
import { renderWithProviders, screen, waitFor } from '../test/test-utils';

vi.mock('../api/posts', () => ({
  getPosts: vi.fn(),
  createPost: vi.fn(),
}));

vi.mock('../api/auth', () => ({
  login: vi.fn(),
  signup: vi.fn(),
  getMe: vi.fn(),
  getOAuthProviders: vi.fn().mockResolvedValue({ providers: [] }),
}));

import * as postsApi from '../api/posts';

const getPostsMock = vi.mocked(postsApi.getPosts);
const createPostMock = vi.mocked(postsApi.createPost);

const POSTS = [
  {
    id: 2,
    content: 'second post',
    created_at: '2026-08-18T09:00:00+00:00',
    author: { id: 1, username: 'yan' },
  },
  {
    id: 1,
    content: 'first post',
    created_at: '2026-08-18T08:00:00+00:00',
    author: { id: 1, username: 'yan' },
  },
];

function axiosError(status: number, data: unknown): AxiosError {
  return new axios.AxiosError(
    'Request failed',
    'ERR_BAD_RESPONSE',
    undefined,
    undefined,
    {
      status,
      data,
      statusText: 'error',
      headers: {},
      config: {} as InternalAxiosRequestConfig,
    },
  );
}

beforeEach(() => {
  getPostsMock.mockReset();
  createPostMock.mockReset();
});

describe('FeedPage', () => {
  it('renders skeletons then post cards on successful fetch', async () => {
    getPostsMock.mockResolvedValue({ posts: POSTS, cacheStatus: 'MISS' });
    renderWithProviders(<FeedPage />);

    expect(screen.getByLabelText('Loading posts')).toBeInTheDocument();

    expect(await screen.findByText('second post')).toBeInTheDocument();
    expect(screen.getByText('first post')).toBeInTheDocument();
    expect(screen.queryByLabelText('Loading posts')).not.toBeInTheDocument();
  });

  it('renders the empty state when the feed is empty', async () => {
    getPostsMock.mockResolvedValue({ posts: [], cacheStatus: 'MISS' });
    renderWithProviders(<FeedPage />);

    expect(await screen.findByText('No posts yet.')).toBeInTheDocument();
    expect(screen.getByText('Be the first to share!')).toBeInTheDocument();
  });

  it('renders error state with a working retry button', async () => {
    getPostsMock
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce({ posts: POSTS, cacheStatus: 'MISS' });
    renderWithProviders(<FeedPage />);

    expect(await screen.findByText("Couldn't load posts.")).toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('second post')).toBeInTheDocument();
  });

  it('keeps posts and shows a stale banner when refresh fails after data loaded', async () => {
    getPostsMock
      .mockResolvedValueOnce({ posts: POSTS, cacheStatus: 'HIT' })
      .mockRejectedValueOnce(new Error('refresh failed'));
    renderWithProviders(<FeedPage />);

    expect(await screen.findByText('second post')).toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh feed' }));

    expect(
      await screen.findByText("Couldn't refresh — showing earlier posts."),
    ).toBeInTheDocument();
    expect(screen.getByText('second post')).toBeInTheDocument();
  });

  it('disables submit for empty and over-limit content, and clears on success', async () => {
    getPostsMock.mockResolvedValue({ posts: [], cacheStatus: 'MISS' });
    createPostMock.mockResolvedValue({
      id: 3,
      content: 'hello world',
      created_at: '2026-08-18T10:00:00+00:00',
      author: { id: 1, username: 'yan' },
    });
    const user = userEvent.setup();
    renderWithProviders(<FeedPage />);

    const textarea = (await screen.findByPlaceholderText("What's on your mind?")) as HTMLTextAreaElement;
    const submit = screen.getByRole('button', { name: 'Post' });
    expect(submit).toBeDisabled();

    fireEvent.change(textarea, { target: { value: '   ' } });
    expect(submit).toBeDisabled();

    fireEvent.change(textarea, { target: { value: 'x'.repeat(501) } });
    expect(screen.getByText('-1/500')).toBeInTheDocument();
    expect(submit).toBeDisabled();

    fireEvent.change(textarea, { target: { value: 'hello world' } });
    await user.click(submit);

    await waitFor(() => {
      expect(textarea.value).toBe('');
    });
    expect(await screen.findByText('hello world')).toBeInTheDocument();
  });

  it('shows the rate limit banner when post creation returns 429', async () => {
    getPostsMock.mockResolvedValue({ posts: [], cacheStatus: 'MISS' });
    createPostMock.mockRejectedValue(axiosError(429, { detail: 'Rate limit exceeded' }));
    const user = userEvent.setup();
    renderWithProviders(<FeedPage />);

    const textarea = (await screen.findByPlaceholderText("What's on your mind?")) as HTMLTextAreaElement;
    await user.type(textarea, 'spam');
    await user.click(screen.getByRole('button', { name: 'Post' }));

    expect(
      await screen.findByText('Too many requests — try again in a moment.'),
    ).toBeInTheDocument();
    expect(textarea.value).toBe('spam');
  });
});