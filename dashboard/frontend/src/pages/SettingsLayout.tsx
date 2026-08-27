import { NavLink, Outlet } from 'react-router-dom'

const subNavCls = (isActive: boolean) => 'he-nav-link' + (isActive ? ' he-nav-link--active' : '')

export function SettingsLayout() {
  return (
    <div>
      <header className="he-page-header">
        <h1 className="he-page-title">Settings</h1>
        <p className="he-lead">
          Detection paths, stored history, and links to analyst workflows. Use <strong>Detection paths</strong> for Zeek
          and bundle defaults.
        </p>
      </header>
      <nav className="he-row he-settings-subnav" style={{ flexWrap: 'wrap', gap: 8, marginBottom: '1.25rem' }} aria-label="Settings sections">
        <NavLink to="/settings" end className={({ isActive }) => subNavCls(isActive)} title="conn.log paths and bundle directories">
          Detection paths
        </NavLink>
        <NavLink to="/settings/history" className={({ isActive }) => subNavCls(isActive)} title="Stream jobs, API runs, batch scores">
          Detection history
        </NavLink>
        <NavLink to="/settings/workflow" className={({ isActive }) => subNavCls(isActive)} title="Alerts, cases, exports, and more">
          Workflow &amp; tools
        </NavLink>
      </nav>
      <Outlet />
    </div>
  )
}
