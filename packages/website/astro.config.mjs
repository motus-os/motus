// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
const site = process.env.ASTRO_SITE || 'https://motus-os.github.io/motus';
const base =
  process.env.ASTRO_BASE ||
  (process.env.NODE_ENV === 'development' ? '/' : '/motus/');

export default defineConfig({
  site,
  base,
  integrations: [tailwind()],
});
