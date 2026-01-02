/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        charcoal: 'oklch(var(--charcoal) / <alpha-value>)',
        surface: 'oklch(var(--surface) / <alpha-value>)',
        'surface-muted': 'oklch(var(--surface-muted) / <alpha-value>)',
        line: 'oklch(var(--line) / <alpha-value>)',
        mint: 'oklch(var(--mint) / <alpha-value>)',
        error: 'oklch(var(--error) / <alpha-value>)',
        'text-primary': 'oklch(var(--text-primary) / <alpha-value>)',
        'text-secondary': 'oklch(var(--text-secondary) / <alpha-value>)',
      },
      fontFamily: {
        display: ['Sora', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['Sora', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      spacing: {
        'phi-1': '0.5rem',
        'phi-2': '0.8125rem',
        'phi-3': '1.3125rem',
        'phi-4': '2.125rem',
        'phi-5': '3.4375rem',
        'phi-6': '5.5625rem',
        'phi-7': '9rem',
        'phi-8': '14.5625rem',
      },
    },
  },
  plugins: [],
};
