import axios from 'axios';
import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import OAuthButtons from '../components/OAuthButtons';
import { useAuth } from '../context/AuthContext';

type Mode = 'login' | 'signup';

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  denied: 'Sign-in cancelled.',
  invalid: 'Sign-in failed — try again.',
  not_configured: "This sign-in option isn't available right now.",
};

interface FieldErrors {
  username?: string;
  email?: string;
  identifier?: string;
  password?: string;
}

function validateUsername(value: string): string | undefined {
  if (!/^[a-zA-Z0-9_-]{3,30}$/.test(value)) {
    return '3–30 characters: letters, numbers, _ or -.';
  }
  return undefined;
}

function validateEmail(value: string): string | undefined {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
    return 'Enter a valid email address.';
  }
  return undefined;
}

function validatePassword(value: string): string | undefined {
  if (value.length < 6) {
    return 'At least 6 characters.';
  }
  return undefined;
}

export default function AuthPage() {
  const { isAuthenticated, isLoading, login, signup } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const oauthError = searchParams.get('error');
  const [oauthBanner, setOauthBanner] = useState<string | null>(
    oauthError ? (OAUTH_ERROR_MESSAGES[oauthError] ?? null) : null,
  );

  if (isLoading) {
    return (
      <div className="page-loader">
        <div className="spinner" aria-label="Loading" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/feed" replace />;
  }

  const from =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? '/feed';

  const switchMode = (next: Mode) => {
    setMode(next);
    setFieldErrors({});
    setFormError(null);
  };

  const dismissOauthBanner = () => {
    setOauthBanner(null);
    const params = new URLSearchParams(searchParams);
    params.delete('error');
    setSearchParams(params, { replace: true });
  };

  const validateField = (field: keyof FieldErrors, value: string) => {
    let error: string | undefined;
    if (field === 'username') error = validateUsername(value);
    else if (field === 'email') error = validateEmail(value);
    else if (field === 'password') error = validatePassword(value);
    else if (field === 'identifier' && !value.trim()) error = 'Enter your email or username.';
    setFieldErrors((prev) => ({ ...prev, [field]: error }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const errors: FieldErrors = {};
    if (mode === 'signup') {
      errors.username = validateUsername(username);
      errors.email = validateEmail(email);
    } else if (!identifier.trim()) {
      errors.identifier = 'Enter your email or username.';
    }
    errors.password = validatePassword(password);
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) {
      return;
    }

    setFormError(null);
    setIsSubmitting(true);
    try {
      if (mode === 'signup') {
        await signup({ username: username.trim(), email: email.trim(), password });
      } else {
        await login({ identifier: identifier.trim(), password });
      }
      navigate(from, { replace: true });
    } catch (error) {
      if (!axios.isAxiosError(error) || !error.response) {
        setFormError("Can't reach the server — check your connection.");
        return;
      }
      const status = error.response.status;
      const detail = error.response.data?.detail;
      if (status === 401) {
        setFormError('Invalid email or password.');
      } else if (status === 409) {
        const message = typeof detail === 'string' ? detail : undefined;
        if (message?.includes('email')) setFieldErrors({ email: message });
        else if (message?.includes('username')) setFieldErrors({ username: message });
        else setFormError(message ?? 'That account already exists.');
      } else if (status === 429) {
        setFormError('Too many attempts — try again in a moment.');
      } else if (status === 422 && Array.isArray(detail)) {
        const first = detail[0] as { loc?: (string | number)[]; msg?: string } | undefined;
        const field = typeof first?.loc?.[1] === 'string' ? first.loc[1] : undefined;
        if (field === 'username' || field === 'email' || field === 'password') {
          setFieldErrors({ [field]: first?.msg ?? 'Invalid value.' });
        } else {
          setFormError('Check the form and try again.');
        }
      } else {
        setFormError('Something went wrong — try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputClass = (hasError: boolean) => `input${hasError ? ' input-error' : ''}`;

  return (
    <main className="auth-shell">
      <div className="auth-card">
        <header>
          <h1 className="logotype">
            Mini<span className="logotype-accent">Feed</span>
          </h1>
          <p className="auth-tagline">Say the small things.</p>
        </header>

        {oauthBanner && (
          <div className="alert" role="status">
            <span>{oauthBanner}</span>
            <button
              type="button"
              className="alert-dismiss"
              aria-label="Dismiss"
              onClick={dismissOauthBanner}
            >
              ×
            </button>
          </div>
        )}

        {formError && (
          <div className="alert alert-error" role="alert">
            <span>{formError}</span>
            <button
              type="button"
              className="alert-dismiss"
              aria-label="Dismiss"
              onClick={() => setFormError(null)}
            >
              ×
            </button>
          </div>
        )}

        <div className="tab-toggle" role="tablist" aria-label="Authentication mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            className={mode === 'login' ? 'tab active' : 'tab'}
            onClick={() => switchMode('login')}
          >
            Log in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'signup'}
            className={mode === 'signup' ? 'tab active' : 'tab'}
            onClick={() => switchMode('signup')}
          >
            Sign up
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {mode === 'signup' && (
            <>
              <div className="field">
                <label className="field-label" htmlFor="username">
                  Username
                </label>
                <input
                  className={inputClass(Boolean(fieldErrors.username))}
                  id="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  onBlur={(event) => validateField('username', event.target.value)}
                  placeholder="janedoe"
                  autoComplete="username"
                  maxLength={30}
                  disabled={isSubmitting}
                />
                {fieldErrors.username && (
                  <p className="field-error" role="alert">
                    {fieldErrors.username}
                  </p>
                )}
              </div>
              <div className="field">
                <label className="field-label" htmlFor="email">
                  Email
                </label>
                <input
                  className={inputClass(Boolean(fieldErrors.email))}
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  onBlur={(event) => validateField('email', event.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  disabled={isSubmitting}
                />
                {fieldErrors.email && (
                  <p className="field-error" role="alert">
                    {fieldErrors.email}
                  </p>
                )}
              </div>
            </>
          )}

          {mode === 'login' && (
            <div className="field">
              <label className="field-label" htmlFor="identifier">
                Email or username
              </label>
              <input
                className={inputClass(Boolean(fieldErrors.identifier))}
                id="identifier"
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
                onBlur={(event) => validateField('identifier', event.target.value)}
                placeholder="you@example.com"
                autoComplete="username"
                disabled={isSubmitting}
              />
              {fieldErrors.identifier && (
                <p className="field-error" role="alert">
                  {fieldErrors.identifier}
                </p>
              )}
            </div>
          )}

          <div className="field">
            <label className="field-label" htmlFor="password">
              Password
            </label>
            <input
              className={inputClass(Boolean(fieldErrors.password))}
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              onBlur={(event) => validateField('password', event.target.value)}
              placeholder="••••••••"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              disabled={isSubmitting}
            />
            {fieldErrors.password && (
              <p className="field-error" role="alert">
                {fieldErrors.password}
              </p>
            )}
          </div>

          <button className="btn btn-primary" type="submit" disabled={isSubmitting}>
            {isSubmitting
              ? mode === 'login'
                ? 'Logging in…'
                : 'Creating account…'
              : mode === 'login'
                ? 'Log in'
                : 'Create account'}
          </button>
        </form>

        <OAuthButtons />
      </div>
    </main>
  );
}