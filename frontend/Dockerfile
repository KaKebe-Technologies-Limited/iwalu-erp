FROM node:20-slim

# Install pnpm
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate

WORKDIR /app

# Copy lockfile and package.json to install dependencies first (caching)
COPY package.json pnpm-lock.yaml* ./

# Install dependencies before copying the rest of the code
# This avoids reinstalling unless package.json/pnpm-lock.yaml change.
RUN pnpm install

# Expose port
EXPOSE 3000

# Start the development server
CMD ["pnpm", "run", "dev"]
