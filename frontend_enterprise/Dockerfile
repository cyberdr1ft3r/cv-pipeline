# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Baked into the client bundle at build time (override per environment on VPS).
ARG NEXT_PUBLIC_API_URL=/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build Next.js app
RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

# Install only production dependencies
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps --only=production

# Copy built app from builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

# Expose port
EXPOSE 3000

# Start the app
CMD ["npm", "start"]

