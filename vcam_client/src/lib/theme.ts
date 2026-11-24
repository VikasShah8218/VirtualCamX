/**
 * Theme switching. The colors themselves live in src/theme.css (one [data-theme] block per theme).
 * To add a theme: add a block in theme.css and an entry here.
 */
export const THEMES = [
  { id: "dusk", label: "Dusk slate", description: "Soft dark (default)" },
  { id: "midnight", label: "Midnight", description: "Deep dark for control rooms" },
  { id: "daylight", label: "Daylight", description: "Light, for bright rooms" },
] as const

export type ThemeId = (typeof THEMES)[number]["id"]

const KEY = "vcamx.theme" // also read by the inline script in index.html / camera.html

export function currentTheme(): ThemeId {
  const t = document.documentElement.dataset.theme
  return (THEMES.some((x) => x.id === t) ? t : __DEFAULT_THEME__) as ThemeId
}

export function applyTheme(id: ThemeId) {
  document.documentElement.dataset.theme = id
  try {
    localStorage.setItem(KEY, id)
  } catch {
    // private mode: theme still applies for this page
  }
}
