# Frontend — Next.js 16 + React 19 + antd, built and served with bun.
# Base image + npm registry both go through CN mirrors (docker.1ms.run / npmmirror).
FROM docker.1ms.run/oven/bun:1

# Build-time inlined browser API base. The browser runs on the host and hits the
# host-published API port, so 127.0.0.1:8918 is correct (same as local dev).
ENV NEXT_PUBLIC_API_BASE=http://127.0.0.1:8918 \
    NEXT_TELEMETRY_DISABLED=1

# npm registry → npmmirror (CN). bun reads bunfig.toml for install registry.
RUN printf 'install.registry = "https://registry.npmmirror.com"\n' > /root/.bunfig.toml
ENV BUN_CONFIG_REGISTRY=https://registry.npmmirror.com

WORKDIR /app

# Cap node/bun heap during build — this container runs inside an 8G colima VM
# shared with the API container. react-compiler builds spike hard.
ENV NODE_OPTIONS=--max-old-space-size=2048

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

RUN bun run build

EXPOSE 3917
CMD ["bun", "run", "start", "--", "-p", "3917"]
