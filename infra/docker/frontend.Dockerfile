FROM node:24.13.0-bookworm-slim AS build
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /workspace
RUN npm install --global pnpm@11.25.0
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
COPY apps/admin/package.json ./apps/admin/package.json
RUN pnpm install --frozen-lockfile
ARG APP_NAME=web
COPY apps/${APP_NAME} ./apps/${APP_NAME}
ARG PUBLIC_URL
ARG ADMIN_BASE_PATH=/admin
ENV PUBLIC_URL=$PUBLIC_URL ADMIN_BASE_PATH=$ADMIN_BASE_PATH API_INTERNAL_URL=http://api:8000
RUN pnpm --filter @lab/${APP_NAME} build

FROM node:24.13.0-bookworm-slim AS runtime
ARG APP_NAME=web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 APP_NAME=$APP_NAME
WORKDIR /app
COPY --from=build --chown=node:node /workspace/apps/${APP_NAME}/.next/standalone ./
COPY --from=build --chown=node:node /workspace/apps/${APP_NAME}/.next/static ./apps/${APP_NAME}/.next/static
COPY --from=build --chown=node:node /workspace/apps/${APP_NAME}/public ./apps/${APP_NAME}/public
USER node
EXPOSE 3000
CMD ["sh", "-c", "exec node apps/$APP_NAME/server.js"]
