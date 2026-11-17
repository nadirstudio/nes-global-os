/** Production builds are a static export served by Caddy; /api is proxied to FastAPI.
 *  In development, /api is rewritten to the local backend. */
const isProd = process.env.NODE_ENV === "production";
const config = isProd
  ? { output: "export", trailingSlash: true, images: { unoptimized: true } }
  : {
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${process.env.NES_API_URL || "http://127.0.0.1:8000"}/api/:path*` }];
      },
    };
export default config;
