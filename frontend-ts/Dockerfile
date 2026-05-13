# 使用 Node.js 22 作为基础镜像，满足 Vite 的运行要求
FROM node:22-alpine

# 设置工作目录
WORKDIR /app

# 安装 pnpm
RUN npm install -g pnpm

# 复制 package.json 和 pnpm-lock.yaml
COPY package*.json pnpm-lock.yaml* ./

# 安装依赖（使用 pnpm）
RUN pnpm install --frozen-lockfile

# 复制项目代码
COPY . .

# 构建项目
RUN pnpm run build

# 使用 nginx 作为生产服务器
FROM nginx:alpine

# 复制 Vite 构建产物到 nginx 静态目录
COPY --from=0 /app/dist /usr/share/nginx/html

# 复制 nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]