FROM node:20-slim

# Install pnpm
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate

WORKDIR /app

# Expose port
EXPOSE 3000

# Start the development server
CMD ["pnpm", "run", "dev"]
