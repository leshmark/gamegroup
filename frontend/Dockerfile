FROM nginx:alpine

# Copy frontend files
COPY . /usr/share/nginx/html

# Copy nginx configuration template
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80

# nginx:alpine automatically processes templates in /etc/nginx/templates/
# and substitutes environment variables before starting nginx
CMD ["nginx", "-g", "daemon off;"]
