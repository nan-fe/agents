FROM node:22-alpine AS deps

WORKDIR /app

RUN npm install -g pnpm@10.30.3

COPY package.json pnpm-lock.yaml ./
COPY prisma ./prisma
RUN pnpm install --frozen-lockfile

FROM node:22-alpine AS builder

WORKDIR /app

RUN npm install -g pnpm@10.30.3
RUN apk add --no-cache openssl

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG STUDIO_UPSTREAM_URL=http://frontend:80
ARG API_UPSTREAM_URL=http://backend:8000
ARG NEXT_PUBLIC_SENTRY_DSN=""
ARG SENTRY_DSN=""
ARG SENTRY_APPLICATION_ID=frontend-share
ENV NODE_ENV=production
ENV DATABASE_URL="postgresql://postgres:postgres@postgres:5432/xhs_auth"
ENV STUDIO_UPSTREAM_URL=${STUDIO_UPSTREAM_URL}
ENV API_UPSTREAM_URL=${API_UPSTREAM_URL}
ENV NEXT_PUBLIC_SENTRY_DSN=${NEXT_PUBLIC_SENTRY_DSN}
ENV SENTRY_DSN=${SENTRY_DSN}
ENV SENTRY_APPLICATION_ID=${SENTRY_APPLICATION_ID}
RUN pnpm run build

FROM node:22-alpine AS runner

WORKDIR /app

ARG NEXT_PUBLIC_SENTRY_DSN=""
ARG SENTRY_DSN=""
ARG SENTRY_APPLICATION_ID=frontend-share

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
ENV NEXT_PUBLIC_SENTRY_DSN=${NEXT_PUBLIC_SENTRY_DSN}
ENV SENTRY_DSN=${SENTRY_DSN}
ENV SENTRY_APPLICATION_ID=${SENTRY_APPLICATION_ID}

RUN apk add --no-cache openssl

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/prisma ./prisma
# pnpm 将 @prisma/* 放在 .pnpm 中，需整体复制 node_modules（含 migrate 用的 prisma CLI）
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

CMD ["sh", "-c", "node node_modules/prisma/build/index.js migrate deploy && node server.js"]
