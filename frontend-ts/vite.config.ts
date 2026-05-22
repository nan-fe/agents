import { defineConfig, type PluginOption, type UserConfig } from "vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import babel from "@rolldown/plugin-babel";

export default defineConfig(async ({ command }): Promise<UserConfig> => {
  const plugins: PluginOption[] = [
    react(),
    babel({
      presets: [reactCompilerPreset()],
    }),
  ];

  if (process.env.ANALYZE === "true") {
    const { visualizer } = await import("rollup-plugin-visualizer");

    plugins.push(
      visualizer({
        filename: "dist/stats.html",
        open: false,
        gzipSize: true,
        brotliSize: true,
      }) as PluginOption,
    );
  }

  return {
    plugins,
    build: {
      target: "baseline-widely-available",
      modulePreload: {
        polyfill: false,
      },
      assetsInlineLimit: 4096,
      cssCodeSplit: true,
      cssMinify: "lightningcss",
      minify: command === "build" ? "oxc" : false,
      reportCompressedSize: true,
      sourcemap: false,
    },
    server: {
      proxy: {
        "/dialog": "http://localhost:8000",
        "/session": "http://localhost:8000",
      },
    },
  };
});
