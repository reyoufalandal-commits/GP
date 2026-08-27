import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { BundleReadinessBanner } from '../components/BundleReadinessBanner'
import { SystemStatusStrip } from '../components/SystemStatusStrip'
import { useLiveEvents } from '../hooks/useLiveEvents'
import { isMlFocusLayout } from './layoutConfig'

const navCls = (isActive: boolean) => 'he-nav-link' + (isActive ? ' he-nav-link--active' : '')

export function Shell() {
  const { user, useApiKey } = useAuth()
  const { last, connected } = useLiveEvents(!!user && !useApiKey)
  const mlFocus = isMlFocusLayout()

  return (
    <div className="he-layout">
      <a
        href="#main-content"
        className="he-skip-link"
        onClick={(e) => {
          e.preventDefault()
          const el = document.getElementById('main-content')
          el?.focus({ preventScroll: true })
          el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }}
      >
        Skip to main content
      </a>
      <aside className="he-sidebar" aria-label="Primary">
        <div className="he-brand">
          <img src="/logo.png" alt="logo" className="he-sidebar-logo" />
          
          <div className="he-brand-text">
            <span className="he-brand-name">Hawk-Eye</span>
            <span className="he-brand-tag">Dashboard</span>
          </div>
        </div>
        <div className="he-nav-section">
          <div className="he-nav-label">Run</div>
          <NavLink
            to="/start"
            title="Step-by-step: health check, samples, and where to click next."
            className={({ isActive }) => navCls(isActive)}
          >
            Start here
          </NavLink>
          <NavLink
            to="/"
            end
            title="Paste or upload data, run scoring and see results."
            className={({ isActive }) => navCls(isActive)}
          >
            Model lab
          </NavLink>
          <NavLink
            to="/stream"
            title="Timed capture from a server log path; live rows then a summary."
            className={({ isActive }) => navCls(isActive)}
          >
            Live stream
          </NavLink>
        </div>
        <div className="he-nav-section">
          <div className="he-nav-label">System</div>
          <NavLink to="/ops" title="API health and raw metrics." className={({ isActive }) => navCls(isActive)}>
            Ops / health
          </NavLink>
          <NavLink to="/settings" title="Detection paths, history, and workflow links." className={({ isActive }) => navCls(isActive)}>
            Settings
          </NavLink>
          <NavLink
            to="/guide"
            title="Press → See → Then for every main screen (demo / defense)."
            className={({ isActive }) => navCls(isActive)}
          >
            Demo flow
          </NavLink>
          <NavLink to="/session" title="Session, refresh token, logout." className={({ isActive }) => navCls(isActive)}>
            Session
          </NavLink>
        </div>
        <div className="he-sidebar-footer">
          <div>{user?.username}</div>
          <div className="he-muted">Role: {user?.role}</div>
          <span
            className={connected ? 'he-pill he-pill--live' : 'he-pill he-pill--off'}
            title={
              connected
                ? `Subscribed to server events.${last ? ` Last: ${last.type}` : ''}`
                : 'Event feed off (API key mode or disconnected).'
            }
          >
            {connected ? '● live' : '○ events off'}
          </span>
          {!mlFocus && last ? (
            <div className="he-sidebar-last-event" title={last.type}>
              Last event: {last.type}
            </div>
          ) : null}
        </div>
      </aside>
      <main id="main-content" className="he-main" tabIndex={-1}>
        <SystemStatusStrip />
        <BundleReadinessBanner />
        <Outlet />
      </main>
    </div>
  )
}
