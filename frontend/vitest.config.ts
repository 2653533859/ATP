import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        url: 'http://localhost:5173/',
      },
    },
    include: ['src/**/*.spec.ts'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,vue}'],
      exclude: ['src/**/*.spec.ts', 'src/test/**', 'src/env.d.ts', 'src/main.ts'],
      // 覆盖率棘轮：数值与调整规则以 docs/coverage-baseline-2026-q13.md 为准
      // （单一事实来源；每次批次调整需同步该文档，保留 ≥0.25pt 本地余量）。
      thresholds: {
        statements: 31.5,
        branches: 26.5,
        functions: 24.5,
        lines: 32.5,
      },
    },
  },
})
