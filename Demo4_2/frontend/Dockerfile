FROM node:20-alpine

WORKDIR /app

# Copy dependency configs
COPY package*.json ./
RUN npm install

# Copy application files
COPY . .

# Build Next.js application
RUN npm run build

EXPOSE 3000

ENV PORT=3000
ENV HOST=0.0.0.0

CMD ["npm", "run", "start"]
