import { Component, type ErrorInfo, type PropsWithChildren } from 'react'

type ErrorState = { failed: boolean }

export class ErrorBoundary extends Component<PropsWithChildren, ErrorState> {
  state: ErrorState = { failed: false }

  static getDerivedStateFromError(): ErrorState {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // No backend secrets are shipped to the client. Connect an error-monitoring
    // service here later if needed; never send lesson content or staff cookies.
    console.error('The learner site could not render.', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <main className="section-shell detail-shell" role="alert">
        <p className="eyebrow">LET’S TRY THAT AGAIN</p>
        <h1>This page couldn’t load.</h1>
        <p>A site update or an unexpected error may have interrupted the page. Reload to get the latest version.</p>
        <button className="button button-primary" type="button" onClick={() => window.location.reload()}>Reload the page</button>
        <p><a className="text-link" href="/">Return to the home page</a></p>
      </main>
    )
  }
}
