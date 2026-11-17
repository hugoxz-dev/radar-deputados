FROM node:24-alpine

WORKDIR /app

# Instala as dependências primeiro (camada em cache enquanto o package.json não mudar)
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
