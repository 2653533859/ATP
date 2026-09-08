/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_ORIGIN?: string
  readonly VITE_ENABLE_PROTOTYPE_DATA?: 'true' | 'false'
}
