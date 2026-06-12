# Deployment Information

File này dành cho service cuối cùng trong `06-lab-complete/`.

## Public URL

```text
TODO: điền URL Railway thật sau khi deploy
```

Ví dụ format:

```text
https://your-agent.up.railway.app
```

Lưu ý: `http://localhost` chỉ là URL kiểm tra local bằng Docker, không phải public URL để nộp.

## Platform

Platform chọn để deploy: Railway

Lý do chọn Railway:

- Phù hợp demo/lab, deploy nhanh.
- Có thể dùng Dockerfile có sẵn trong `06-lab-complete/`.
- Hỗ trợ environment variables và healthcheck.
- Có thể gắn Redis service để đáp ứng yêu cầu stateless/rate limit/cost guard.

## Source Code Deploy

Thư mục deploy:

```text
06-lab-complete/
```

Các file deployment chính:

- `Dockerfile`
- `docker-compose.yml`
- `railway.toml`
- `render.yaml`
- `.env.example`
- `README.md`

## Environment Variables Set

Cần set trên Railway:

```text
PORT=<Railway tự inject>
ENVIRONMENT=production
AGENT_API_KEY=<strong-secret-api-key>
REDIS_URL=<railway-redis-private-url>
RATE_LIMIT_PER_MINUTE=10
MONTHLY_BUDGET_USD=10.0
ESTIMATED_REQUEST_COST_USD=0.001
LOG_LEVEL=INFO
```

Tuỳ chọn:

```text
OPENAI_API_KEY=
LLM_MODEL=gpt-4o-mini
ALLOWED_ORIGINS=*
HISTORY_TTL_SECONDS=2592000
MAX_HISTORY_MESSAGES=20
```

## Railway Deploy Commands

```bash
cd 06-lab-complete
npm i -g @railway/cli
railway login
railway init
railway add redis
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=<strong-secret-api-key>
railway variables set REDIS_URL=<railway-redis-private-url>
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set MONTHLY_BUDGET_USD=10.0
railway variables set ESTIMATED_REQUEST_COST_USD=0.001
railway variables set LOG_LEVEL=INFO
railway up
railway domain
```

Sau khi có domain, thay `TODO` ở mục Public URL bằng URL thật.

## Test Commands

Trước khi test, set biến:

```bash
export URL="https://your-agent.up.railway.app"
export API_KEY="<AGENT_API_KEY đã set trên Railway>"
```

### 1. Health Check

```bash
curl "$URL/health"
```

Kết quả mong đợi:

```json
{"status":"ok"}
```

### 2. Readiness Check

```bash
curl "$URL/ready"
```

Kết quả mong đợi:

```json
{"ready":true}
```

### 3. Authentication Required

```bash
curl -i -X POST "$URL/ask" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

Kết quả mong đợi:

```text
401 Unauthorized
```

### 4. API Test With Authentication

```bash
curl -X POST "$URL/ask" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"What is Docker?"}'
```

Kết quả mong đợi:

```text
200 OK
```

Response cần có các field chính:

- `answer`
- `rate_limit`
- `budget`
- `served_by`

### 5. Conversation History Test

```bash
curl -X POST "$URL/ask" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","question":"My name is Alice"}'

curl -X POST "$URL/ask" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","question":"What is my name?"}'
```

Kết quả mong đợi ở request thứ hai:

```text
Your name is Alice.
```

### 6. Rate Limiting Test

```bash
for i in $(seq 1 12); do
  curl -s -o /tmp/rate-$i.json -w "%{http_code} " \
    -X POST "$URL/ask" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"rate-test\",\"question\":\"test $i\"}"
done

cat /tmp/rate-12.json
```

Kết quả mong đợi:

```text
200 200 200 200 200 200 200 200 200 200 429 429
```

### 7. Error Handling Test

```bash
curl -i -X POST "$URL/ask" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"invalid":"data"}'
```

Kết quả mong đợi:

```text
422 Unprocessable Entity
```

## Screenshots

Cần thêm vào repo sau khi deploy thật:

```text
screenshots/railway-dashboard.png
screenshots/service-running.png
screenshots/curl-tests.png
```

Nội dung screenshots nên thể hiện:

- Railway deployment đang active/running.
- Environment variables đã set.
- Public URL trả `/health` thành công.
- API `/ask` chạy thành công với `X-API-Key`.

## Local Verification

Phần này chỉ là bằng chứng app chạy đúng ở local trước khi deploy public.

Ngày kiểm tra local: 12/06/2026

Command đã chạy:

```bash
cd 06-lab-complete
docker compose up -d --build --scale agent=3
python3 check_production_ready.py
```

Kết quả readiness checker:

```text
Result: 20/20 checks passed (100%)
PRODUCTION READY
```

Docker stack local:

```text
06-lab-complete-agent-1   healthy
06-lab-complete-agent-2   healthy
06-lab-complete-agent-3   healthy
06-lab-complete-nginx-1   0.0.0.0:80->80/tcp
06-lab-complete-redis-1   healthy
```

Image size:

```text
06-lab-complete-agent latest 332MB
```

Các test đã verify local:

```text
GET /health -> 200 OK
GET /ready -> 200 OK
POST /ask không có key -> 401 Unauthorized
POST /ask có key hợp lệ -> 200 OK
Rate limit -> 429 sau 10 requests/phút
Cost guard -> 402 khi request làm vượt monthly budget
Conversation history -> giữ được qua nhiều agent instances
```

## Submission Checklist

- [ ] Thay Public URL bằng URL Railway thật.
- [ ] Set đầy đủ environment variables trên Railway.
- [ ] Test URL public từ terminal/browser khác.
- [ ] Thêm screenshots vào thư mục `screenshots/`.
- [ ] Đảm bảo không commit file `.env` thật.
- [ ] Đảm bảo `MISSION_ANSWERS.md` và `DEPLOYMENT.md` được commit.
