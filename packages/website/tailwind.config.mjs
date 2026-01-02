/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        charcoal: '#0B0B0B',
        surface: '#151515',
        mint: '#6FFFE3',
        error: '#FF6B6B',
        'text-primary': '#F7F6F2',
        'text-secondary': '#9B9B97',
      },
      fontFamily: {
        display: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
        sans: ['Space Grotesk', 'ui-sans-serif', 'system-ui', 'sans-serif'],
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
