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
      fontSize: {
        xs: ['var(--step--2)', { lineHeight: '1.4' }],
        sm: ['var(--step--1)', { lineHeight: '1.5' }],
        base: ['var(--step-0)', { lineHeight: '1.6' }],
        lg: ['var(--step-1)', { lineHeight: '1.5' }],
        xl: ['var(--step-2)', { lineHeight: '1.4' }],
        '2xl': ['var(--step-3)', { lineHeight: '1.3' }],
        '3xl': ['var(--step-4)', { lineHeight: '1.2' }],
        '4xl': ['var(--step-5)', { lineHeight: '1.15' }],
        '5xl': ['var(--step-6)', { lineHeight: '1.1' }],
        '6xl': ['var(--step-7)', { lineHeight: '1.05' }],
      },
      maxWidth: {
        measure: 'var(--measure)',
        page: 'var(--page)',
        narrow: 'var(--page-narrow)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        '2xl': 'var(--radius-xl)',
      },
      boxShadow: {
        soft: 'var(--shadow-1)',
        lift: 'var(--shadow-2)',
      },
      transitionDuration: {
        fast: 'var(--duration-fast)',
        base: 'var(--duration-base)',
        slow: 'var(--duration-slow)',
      },
      transitionTimingFunction: {
        standard: 'var(--ease-standard)',
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
