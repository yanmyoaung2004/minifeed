import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { userEvent } from '@testing-library/user-event';

import AuthPage from '../pages/AuthPage';
import { renderWithProviders, screen, waitFor } from '../test/test-utils';

vi.mock('../api/auth', () => ({
  login: vi.fn(),
  signup: vi.fn(),
  getMe: vi.fn(),
  getOAuthProviders: vi.fn().mockResolvedValue({ providers: [] }),
}));

import * as authApi from '../api/auth';

const loginMock = vi.mocked(authApi.login);
const signupMock = vi.mocked(authApi.signup);
const getMeMock = vi.mocked(authApi.getMe);

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
  loginMock.mockReset();
  signupMock.mockReset();
  getMeMock.mockReset().mockResolvedValue({
    id: 1,
    username: 'yan',
    email: 'yan@example.com',
    created_at: '2026-01-01T00:00:00+00:00',
  });
});

describe('AuthPage', () => {
  it('renders login form by default and toggles to signup mode', async () => {
    renderWithProviders(<AuthPage />);
    expect(await screen.findByLabelText('Email or username')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('tab', { name: 'Sign up' }));
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.queryByLabelText('Email or username')).not.toBeInTheDocument();
  });

  it('shows inline validation errors for invalid email and short password', async () => {
    renderWithProviders(<AuthPage />);
    await userEvent.click(await screen.findByRole('tab', { name: 'Sign up' }));

    const email = screen.getByLabelText('Email');
    const password = screen.getByLabelText('Password');
    await userEvent.type(email, 'not-an-email');
    await userEvent.type(password, '123');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.getByText('At least 6 characters.')).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it('shows generic error alert on 401 from login', async () => {
    loginMock.mockRejectedValue(axiosError(401, { detail: 'Invalid credentials' }));
    renderWithProviders(<AuthPage />);

    await userEvent.type(await screen.findByLabelText('Email or username'), 'yan@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrongpass');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.');
  });

  it('disables submit and shows submitting state while login is pending', async () => {
    loginMock.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<AuthPage />);

    await userEvent.type(await screen.findByLabelText('Email or username'), 'yan@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'secret123');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    const button = await screen.findByRole('button', { name: 'Logging in…' });
    expect(button).toBeDisabled();
  });

  it('maps 409 conflict to an inline field error during signup', async () => {
    signupMock.mockRejectedValue(axiosError(409, { detail: 'email already registered' }));
    renderWithProviders(<AuthPage />);
    await userEvent.click(await screen.findByRole('tab', { name: 'Sign up' }));

    await userEvent.type(screen.getByLabelText('Username'), 'newuser');
    await userEvent.type(screen.getByLabelText('Email'), 'taken@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'secret123');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(await screen.findByText('email already registered')).toBeInTheDocument();
  });

  it('shows a network error banner when the server is unreachable', async () => {
    loginMock.mockRejectedValue(new axios.AxiosError('Network Error'));
    renderWithProviders(<AuthPage />);

    await userEvent.type(await screen.findByLabelText('Email or username'), 'yan@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'secret123');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Can't reach the server — check your connection.",
    );
  });

  it('logs in successfully and persists the token', async () => {
    loginMock.mockResolvedValue({ access_token: 'jwt-token', token_type: 'bearer' });
    renderWithProviders(<AuthPage />);

    await userEvent.type(await screen.findByLabelText('Email or username'), 'yan@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'secret123');
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }));

    await waitFor(() => {
      expect(localStorage.getItem('access_token')).toBe('jwt-token');
    });
  });
});