/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        charcoal: '#0E0E0E',
        surface: '#1A1A1A',
        mint: '#66FFDE',
        error: '#FF6B6B',
        'text-primary': '#FFFFFF',
        'text-secondary': '#A0A0A0',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
};
