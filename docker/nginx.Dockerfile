FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf

RUN printf '\
upstream supporty {\n\
    server app:8000;\n\
    keepalive 32;\n\
}\n\
\n\
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;\n\
\n\
server {\n\
    listen 80;\n\
    server_name _;\n\
\n\
    location /api/ {\n\
        limit_req zone=api burst=10 nodelay;\n\
        proxy_pass         http://supporty;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header   Host              $host;\n\
        proxy_set_header   X-Real-IP         $remote_addr;\n\
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;\n\
        proxy_set_header   X-Forwarded-Proto $scheme;\n\
        proxy_set_header   Connection        "";\n\
        proxy_read_timeout  120s;\n\
        proxy_send_timeout  120s;\n\
        add_header X-Content-Type-Options  "nosniff"       always;\n\
        add_header X-Frame-Options         "DENY"          always;\n\
        add_header X-XSS-Protection        "1; mode=block" always;\n\
        add_header Referrer-Policy         "no-referrer"   always;\n\
    }\n\
\n\
    location /health {\n\
        proxy_pass http://supporty/api/v1/health;\n\
        access_log off;\n\
    }\n\
\n\
    location /dashboard/ {\n\
        proxy_pass         http://dashboard:8501/dashboard/;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header   Upgrade    $http_upgrade;\n\
        proxy_set_header   Connection "upgrade";\n\
        proxy_set_header   Host       $host;\n\
        proxy_read_timeout 86400;\n\
    }\n\
\n\
    location / {\n\
        default_type application/json;\n\
        return 200 '"'"'{"service":"Autonomous Support Architect","status":"ok","endpoints":{"webhook":"POST /api/v1/webhook/ticket","health":"GET /api/v1/health","dashboard":"GET /dashboard/"}}'"'"';\n\
    }\n\
}\n\
' > /etc/nginx/conf.d/default.conf
