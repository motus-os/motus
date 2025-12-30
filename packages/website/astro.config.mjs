// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
export default defineConfig({
  site: 'https://motus-os.github.io',
  base: '/motus-website/',
  integrations: [tailwind()],
});
