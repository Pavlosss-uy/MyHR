import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { fileURLToPath } from "url";
import { componentTagger } from "lovable-tagger";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
    server: {
        host: "::",
        port: 8080,
        hmr: {
            overlay: false,
        },
        // NOTE: No COOP/COEP headers here on purpose. The Silero VAD runs in
        // single-thread mode (ort.env.wasm.numThreads = 1, see src/hooks/useVAD.js),
        // so it does NOT need SharedArrayBuffer / cross-origin isolation. Setting
        // Cross-Origin-Opener-Policy: same-origin breaks Firebase/Google sign-in
        // popups (it severs window.opener), so we must NOT set it.
        proxy: {
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api/, ""),
            },
        },
    },
    plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
}));
