import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { userEvent } from '@testing-library/user-event';

import { AuthProvider, useAuth } from '../context/AuthContext';
import AuthPage from '../pages/AuthPage';
import { render, renderWithProviders, screen } from '../test/test-utils';

vi.mock('../api/auth', () => ({
  login: vi.fn(),
  signup: vi.fn(),
  getMe: vi.fn(),
  getOAuthProviders: vi.fn().mockResolvedValue({ providers: [] }),
}));

import * as authApi from '../api/auth';

const getMeMock = vi.mocked(authApi.getMe);

function AuthProbe() {
  const { isAuthenticated } = useAuth();
  return <div>{isAuthenticated ? 'authenticated' : 'anonymous'}</div>;
}

describe('OAuth callback handling', () => {
  it('stores ?token= in localStorage, strips it from the URL, and authenticates', async () => {
    getMeMock.mockResolvedValue({
      id: 5,
      username: 'john',
      email: 'john@example.com',
      created_at: '2026-01-01T00:00:00+00:00',
    });
    window.history.replaceState({}, '', '/?token=oauth-jwt-abc');

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <AuthProvider>
                <AuthProbe />
              </AuthProvider>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('authenticated')).toBeInTheDocument();
    expect(localStorage.getItem('access_token')).toBe('oauth-jwt-abc');
    expect(window.location.search).toBe('');
    expect(getMeMock).toHaveBeenCalled();
  });

  it('shows a friendly banner for ?error=denied and cleans the URL on dismiss', async () => {
    renderWithProviders(<AuthPage />, { route: '/login?error=denied' });

    expect(await screen.findByText('Sign-in cancelled.')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByText('Sign-in cancelled.')).not.toBeInTheDocument();
  });

  it('shows a friendly banner for ?error=invalid', async () => {
    renderWithProviders(<AuthPage />, { route: '/login?error=invalid' });

    expect(await screen.findByText('Sign-in failed — try again.')).toBeInTheDocument();
  });

  it('shows a friendly banner for ?error=not_configured', async () => {
    renderWithProviders(<AuthPage />, { route: '/login?error=not_configured' });

    expect(
      await screen.findByText("This sign-in option isn't available right now."),
    ).toBeInTheDocument();
  });
});