# Stage 1: Build
FROM node:24-alpine AS builder
WORKDIR /app

# Install dependencies (use cache)
COPY package*.json ./
RUN npm install

# Build application
COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

# Add sophisticated config
COPY nginx.conf /etc/nginx/nginx.conf

# Add static assets
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
