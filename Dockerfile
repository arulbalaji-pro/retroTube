FROM node:20-alpine

# Install ffmpeg for thumbnail generation and stream transcoding
RUN apk add --no-cache ffmpeg

WORKDIR /app

# Copy dependency manifests and install production dependencies
COPY package*.json ./
RUN npm install --omit=dev

# Copy application source code
COPY server.js ./
COPY public ./public

# Ensure the thumbnails directory exists
RUN mkdir -p public/thumbnails

EXPOSE 3000

ENV NODE_ENV=production
ENV VIDEO_DIR=/media

CMD ["node", "server.js"]
