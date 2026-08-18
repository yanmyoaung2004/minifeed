import { useEffect, useState } from 'react';

import { getOAuthProviders } from '../api/auth';

const PROVIDER_LABELS: Record<string, string> = {
  github: 'Continue with GitHub',
  google: 'Continue with Google',
};

const PROVIDER_NAMES: Record<string, string> = {
  github: 'GitHub',
  google: 'Google',
};

export default function OAuthButtons() {
  const [providers, setProviders] = useState<string[]>([]);
  const [redirecting, setRedirecting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getOAuthProviders()
      .then((data) => {
        if (!cancelled) setProviders(data.providers);
      })
      .catch(() => {
        if (!cancelled) setProviders([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (providers.length === 0) {
    return null;
  }

  return (
    <div className="oauth-group">
      <div className="oauth-divider" aria-hidden="true">
        <span>or</span>
      </div>
      {providers.map((provider) => (
        <button
          key={provider}
          type="button"
          className="btn btn-ghost oauth-button"
          disabled={redirecting !== null}
          onClick={() => {
            setRedirecting(provider);
            window.location.href = `/auth/oauth/${provider}`;
          }}
        >
          {redirecting === provider
            ? `Redirecting to ${PROVIDER_NAMES[provider] ?? provider}…`
            : (PROVIDER_LABELS[provider] ?? `Continue with ${provider}`)}
        </button>
      ))}
    </div>
  );
}