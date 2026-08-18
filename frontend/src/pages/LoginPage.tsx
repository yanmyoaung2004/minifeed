export default function LoginPage() {
  return (
    <main className="auth-shell">
      <div className="auth-card">
        <header>
          <h1 className="logotype">
            Mini<span className="logotype-accent">Feed</span>
          </h1>
          <p className="auth-tagline">Say the small things.</p>
        </header>

        <form className="auth-form" onSubmit={(e) => e.preventDefault()}>
          <div className="field">
            <label className="field-label" htmlFor="identifier">
              Email or username
            </label>
            <input
              className="input"
              id="identifier"
              name="identifier"
              type="text"
              placeholder="you@example.com"
              autoComplete="username"
              disabled
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="password">
              Password
            </label>
            <input
              className="input"
              id="password"
              name="password"
              type="password"
              placeholder="••••••••"
              autoComplete="current-password"
              disabled
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled>
            Log in
          </button>
        </form>

        <p className="auth-tagline">Authentication UI lands in the next phase.</p>
      </div>
    </main>
  );
}