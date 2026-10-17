import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // No proxy needed — the frontend API layer (src/api/axios.js) already
    // uses the absolute base URL configured via VITE_API_BASE_URL.
    // 
    // IMPORTANT: Proxying paths like /dashboard, /upload, /query etc. was
    // intercepting the React Router client-side routes, causing pages to
    // break after login (the browser would receive the backend JSON response
    // instead of the React SPA HTML).
  },
})
