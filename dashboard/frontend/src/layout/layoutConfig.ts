export type DashboardLayoutMode = 'full' | 'ml_focus'

/** Set `VITE_DASHBOARD_LAYOUT=ml_focus` to hide SOC pages and show model ops only. */
export function dashboardLayoutMode(): DashboardLayoutMode {
  const v = import.meta.env.VITE_DASHBOARD_LAYOUT
  return v === 'ml_focus' ? 'ml_focus' : 'full'
}

export function isMlFocusLayout(): boolean {
  return dashboardLayoutMode() === 'ml_focus'
}
