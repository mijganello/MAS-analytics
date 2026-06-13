FROM node:20-alpine AS dependencies
WORKDIR /app
COPY package.json ./
RUN npm install -g pnpm && pnpm install --no-frozen-lockfile

FROM dependencies AS development
COPY . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

FROM dependencies AS builder
COPY . .
RUN pnpm build

FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
