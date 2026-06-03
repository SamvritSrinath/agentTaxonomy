FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY dist/ .
EXPOSE 3000
CMD ["node", "auth-service.js"]
