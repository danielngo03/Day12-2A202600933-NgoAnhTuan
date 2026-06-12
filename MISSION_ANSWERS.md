# Day 12 Lab - Mission Answers

**Sinh viên:** Ngô Anh Tuấn - 2A202600933  
**Ngày:** 12/06/2026

---

## Phần 1: Localhost vs Production

Thư mục sử dụng: `01-localhost-vs-production/`

### Bài 1.1: Các anti-pattern trong `develop/app.py`

Trong `01-localhost-vs-production/develop/app.py`, tìm thấy các vấn đề production sau:

1. Hardcode `OPENAI_API_KEY` trong source code.
2. Hardcode `DATABASE_URL` có username/password trong source code.
3. Bật `DEBUG = True` trực tiếp trong code.
4. Cố định `MAX_TOKENS = 500` thay vì đọc từ config/env.
5. Log bằng `print()` thay vì structured logging.
6. In API key ra log: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.
7. Không có endpoint `/health`, nên platform không biết app còn sống hay không.
8. Không có endpoint `/ready`, nên load balancer không biết app đã sẵn sàng nhận traffic chưa.
9. Cố định host là `localhost`, không phù hợp container/cloud.
10. Cố định port `8000`, không đọc từ biến môi trường `PORT`.
11. Chạy `reload=True`, phù hợp development nhưng không phù hợp production.
12. Không có graceful shutdown/SIGTERM handling.

### Bài 1.2: Chạy basic version

Lệnh chạy basic version:

```bash
cd 01-localhost-vs-production/develop
python3 -m pip install -r requirements.txt
python3 app.py
```

Lệnh test:

```bash
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

Kết luận: App có thể chạy local, nhưng chưa production-ready vì phụ thuộc môi trường máy cá nhân, hardcode secrets/config và thiếu health check/graceful shutdown.

### Bài 1.3: So sánh basic và advanced version

So sánh `01-localhost-vs-production/develop/app.py` với `01-localhost-vs-production/production/app.py` và `config.py`:

| Tiêu chí | Develop/basic | Production/advanced | Vì sao quan trọng? |
|---|---|---|---|
| Config | Hardcode trong code | Tập trung ở `config.py`, đọc từ env vars | Dễ thay đổi giữa local/staging/production mà không sửa code. |
| Secrets | API key và DB URL nằm trong code | `OPENAI_API_KEY`, `AGENT_API_KEY` đọc từ env | Tránh lộ secrets khi push GitHub hoặc build image. |
| Host | `localhost` | `0.0.0.0` | Container/cloud cần nhận traffic từ bên ngoài process. |
| Port | Cố định `8000` | `settings.port`, đọc từ `PORT` | Railway/Render inject port động. |
| Debug/reload | `reload=True` | Chỉ reload khi `DEBUG=true` | Tránh chạy dev reloader trong production. |
| Health check | Không có | Có `GET /health` | Platform có thể restart app khi unhealthy. |
| Readiness | Không có | Có `GET /ready` | Load balancer biết khi nào nên route traffic. |
| Logging | `print()` và log cả secret | Structured JSON logging, không log secret | Dễ quan sát trên cloud và an toàn hơn. |
| Shutdown | Tắt đột ngột | Lifespan + SIGTERM handler | Giảm mất request khi deploy/restart. |
| CORS | Không cấu hình rõ | `allowed_origins` từ config | Kiểm soát client nào được gọi API. |

---

## Phần 2: Docker

Thư mục sử dụng: `02-docker/`

### Bài 2.1: Câu hỏi Dockerfile cơ bản

Dựa trên `02-docker/develop/Dockerfile`:

1. Base image là `python:3.11`.
2. Working directory là `/app`.
3. `COPY 02-docker/develop/requirements.txt .` được đặt trước khi copy app code để tận dụng Docker layer cache. Nếu chỉ đổi source code, layer cài dependencies không cần chạy lại.
4. `CMD` là command mặc định khi container start và có thể override bằng lệnh `docker run`. `ENTRYPOINT` thường là executable cố định của container; tham số runtime thường được truyền sau entrypoint.

### Bài 2.2: Build và run basic container

Lệnh build/run theo lab:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
```

Lệnh test:

```bash
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
```

Quan sát: Basic image dùng full `python:3.11`, nên dễ hiểu nhưng image lớn hơn production image.

### Bài 2.3: Multi-stage build

Dựa trên `02-docker/production/Dockerfile`:

- Stage 1 `builder`:
  - Dùng `python:3.11-slim AS builder`.
  - Cài build dependencies như `gcc`, `libpq-dev`.
  - Cài Python dependencies bằng `pip install --user`.
- Stage 2 `runtime`:
  - Dùng `python:3.11-slim AS runtime`.
  - Tạo non-root user `appuser`.
  - Copy `/root/.local` từ builder sang runtime.
  - Copy `main.py` và `utils/mock_llm.py`.
  - Chạy bằng `uvicorn`.
  - Có `HEALTHCHECK`.

Vì sao image nhỏ hơn:

- Final image không giữ toàn bộ build context hoặc dev files.
- Runtime stage chỉ giữ packages và source cần chạy.
- Dùng `python:3.11-slim`, nhỏ hơn full `python:3.11`.
- Chạy non-root giúp an toàn hơn.

Lệnh build/so sánh:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images | grep my-agent
```

So sánh kích thước image:

| Image | Kiểu build | Kích thước kỳ vọng theo lab | Lý do |
|---|---|---:|---|
| `my-agent:develop` | Single-stage, `python:3.11` | khoảng 800 MB | Full Python image, giữ nhiều runtime/tooling hơn. |
| `my-agent:advanced` | Multi-stage, `python:3.11-slim` | khoảng 160 MB | Runtime stage chỉ copy phần cần chạy. |

Mức giảm ước tính:

```text
(800 - 160) / 800 = 80%
```

Kết luận: multi-stage build giúp image nhỏ hơn đáng kể, deploy nhanh hơn và giảm attack surface.

### Bài 2.4: Docker Compose stack

Dựa trên `02-docker/production/docker-compose.yml`, các service được start:

- `agent`: FastAPI AI agent.
- `redis`: cache/session/rate limit backend.
- `qdrant`: vector database cho RAG.
- `nginx`: reverse proxy/load balancer.

Architecture diagram:

```text
Client
  |
  v
Nginx :80/:443
  |
  v
Agent :8000
  |        \
  v         v
Redis     Qdrant
:6379     :6333
```

Lệnh chạy/test:

```bash
docker compose -f 02-docker/production/docker-compose.yml up
curl http://localhost/health
curl http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain microservices"}'
```

Giải thích giao tiếp:

- Client chỉ gọi Nginx qua port public.
- Nginx proxy request tới `agent:8000` qua Docker network.
- Agent gọi Redis bằng hostname service `redis`.
- Agent có thể gọi Qdrant bằng hostname service `qdrant`.

---

## Phần 3: Cloud Deployment

Thư mục sử dụng: `03-cloud-deployment/`

### Bài 3.1: Railway deployment

Dựa trên `03-cloud-deployment/railway/`:

- `app.py` đã đọc `PORT` bằng `os.getenv("PORT", 8000)`.
- `/health` trả về `{"status": "ok", ...}` để Railway healthcheck.
- `railway.toml` dùng Nixpacks và start command:

```toml
startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
restartPolicyType = "ON_FAILURE"
```

Các bước deploy:

```bash
cd 03-cloud-deployment/railway
npm i -g @railway/cli
railway login
railway init
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key
railway up
railway domain
```

Lệnh test public URL sau khi deploy:

```bash
curl https://<railway-domain>/health
curl https://<railway-domain>/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Am I on the cloud?"}'
```

Public URL:

```text
TODO: điền URL Railway thật sau khi deploy bằng tài khoản Railway.
```

Screenshot:

```text
TODO: thêm screenshots/railway-dashboard.png và screenshots/curl-tests.png sau khi deploy thật.
```

### Bài 3.2: So sánh `render.yaml` và `railway.toml`

| Tiêu chí | Railway `railway.toml` | Render `render.yaml` |
|---|---|---|
| Mục đích | Cấu hình deploy service trên Railway | Blueprint mô tả hạ tầng trên Render |
| Runtime | Nixpacks auto-detect Python | `runtime: python` |
| Start command | `uvicorn app:app --host 0.0.0.0 --port $PORT` | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Env vars | Set qua Railway CLI/dashboard | Khai báo trong YAML, secret dùng `sync: false` hoặc `generateValue` |
| Redis | Không khai báo trực tiếp trong file này | Có service Redis `agent-cache` |
| IaC level | Nhẹ, tập trung vào app service | Rõ hơn về infrastructure vì khai báo cả web service và Redis |

### Bài 3.3: GCP Cloud Run CI/CD

Dựa trên `03-cloud-deployment/production-cloud-run/cloudbuild.yaml`:

1. Step `test`: cài dependencies và chạy pytest.
2. Step `build`: build Docker image với tag `$COMMIT_SHA` và `latest`.
3. Step `push`: push image lên `gcr.io/$PROJECT_ID/ai-agent`.
4. Step `deploy`: deploy image lên Cloud Run ở region `asia-southeast1`.

Dựa trên `service.yaml`:

- `minScale: "1"` giúp giảm cold start.
- `maxScale: "10"` giới hạn số instance để kiểm soát chi phí.
- `containerConcurrency: 80` cho phép mỗi instance xử lý nhiều request.
- Secrets lấy từ Secret Manager, không hardcode trong YAML.
- Có liveness/startup probes tới `/health` và `/ready`.

---

## Phần 4: API Security

Thư mục sử dụng: `04-api-gateway/`

### Bài 4.1: API key authentication

Dựa trên `04-api-gateway/develop/app.py`:

- API key được đọc từ env var:

```python
API_KEY = os.getenv("AGENT_API_KEY", "demo-key-change-in-production")
```

- Header được kiểm tra qua:

```python
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
```

- Logic check nằm trong hàm `verify_api_key`.
- Nếu thiếu key: trả `401`.
- Nếu sai key: trả `403`.
- Nếu đúng key: request được xử lý.

Lệnh test:

```bash
cd 04-api-gateway/develop
AGENT_API_KEY=secret-key-123 python3 app.py

curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

Cách rotate key: đổi `AGENT_API_KEY` trong environment/platform secrets rồi restart/redeploy service. Không cần sửa source code.

### Bài 4.2: JWT authentication

Dựa trên `04-api-gateway/production/auth.py` và `app.py`:

- Endpoint lấy token thực tế trong code là `POST /auth/token`.
- User demo:
  - `student / demo123`, role `user`.
  - `teacher / teach456`, role `admin`.
- Token chứa `sub`, `role`, `iat`, `exp`.
- Token hết hạn sau 60 phút.
- Endpoint `/ask` dùng dependency `verify_token`, yêu cầu header `Authorization: Bearer <token>`.

Lệnh lấy token:

```bash
cd 04-api-gateway/production
python3 app.py

curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'
```

Lệnh gọi API bằng token:

```bash
TOKEN="<access_token>"
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
```

### Bài 4.3: Rate limiting

Dựa trên `04-api-gateway/production/rate_limiter.py`:

- Algorithm: sliding window counter bằng `deque` trong memory.
- Window: 60 giây.
- User thường: 10 requests/phút.
- Admin: 100 requests/phút.
- Admin bypass limit bằng cách dùng limiter khác rộng hơn:

```python
limiter = rate_limiter_admin if role == "admin" else rate_limiter_user
```

Khi vượt limit, app trả `429 Too Many Requests`, kèm headers như:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
- `Retry-After`

Lệnh test:

```bash
for i in {1..20}; do
  curl http://localhost:8000/ask -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "Test '$i'"}'
  echo ""
done
```

Kết quả kỳ vọng: request thứ 11 trở đi của user thường bị chặn với status `429`.

### Bài 4.4: Cost guard

Dựa trên `04-api-gateway/production/cost_guard.py`:

- Cost guard hiện tại là demo in-memory, phù hợp để học concept.
- Mỗi user có daily budget `$1/ngày`.
- Global daily budget là `$10/ngày`.
- `check_budget(username)` kiểm tra trước khi gọi LLM.
- `record_usage(username, input_tokens, output_tokens)` ghi nhận usage sau khi gọi LLM.
- Khi vượt per-user budget, app trả `402 Payment Required`.
- Khi vượt global budget, app trả `503 Service Unavailable`.

Logic Redis-based theo yêu cầu bài lab có thể triển khai như sau:

```python
import redis
from datetime import datetime

r = redis.Redis()

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"

    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:
        return False

    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)
    return True
```

Giải thích:

- Key theo tháng giúp reset budget tự nhiên.
- Redis giúp nhiều instance cùng đọc/ghi budget, không bị lệch khi scale.
- `expire` tránh giữ dữ liệu cũ mãi mãi.

---

## Phần 5: Scaling & Reliability

Thư mục sử dụng: `05-scaling-reliability/`

### Bài 5.1: Health checks

Dựa trên `05-scaling-reliability/develop/app.py`:

- `GET /health` là liveness probe.
- `GET /ready` là readiness probe.
- `/health` trả status, uptime, version, environment, timestamp và checks.
- `/ready` trả `ready: true` khi app đã load xong; trả `503` nếu chưa ready hoặc đang shutdown.

Lệnh test:

```bash
cd 05-scaling-reliability/develop
python3 app.py
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Bài 5.2: Graceful shutdown

Trong `05-scaling-reliability/develop/app.py`:

- App dùng FastAPI lifespan để quản lý startup/shutdown.
- `_is_ready = False` khi shutdown để ngừng nhận traffic mới.
- `_in_flight_requests` đếm request đang xử lý.
- Middleware `track_requests` tăng/giảm counter cho từng request.
- Shutdown chờ tối đa 30 giây cho request đang chạy hoàn thành.
- Có signal handler cho SIGTERM/SIGINT.
- `uvicorn.run(..., timeout_graceful_shutdown=30)` cho phép shutdown mềm.

Lệnh test theo lab:

```bash
python3 app.py &
PID=$!

curl -X POST "http://localhost:8000/ask?question=Long task" &
sleep 0.5
kill -TERM $PID
wait
```

Kết quả kỳ vọng: request đang xử lý hoàn thành, log xuất hiện thông điệp graceful shutdown.

### Bài 5.3: Stateless design

Dựa trên `05-scaling-reliability/production/app.py`:

- App không nên lưu conversation/session trong memory của từng instance.
- Session được lưu bằng key Redis `session:{session_id}`.
- Hàm `save_session` dùng `setex` để lưu session có TTL.
- Hàm `load_session` đọc session từ Redis.
- Hàm `append_to_history` append message vào history và giữ tối đa 20 messages.

Điểm cần chú ý: code có fallback in-memory nếu Redis không available. Fallback này chỉ để demo local; khi production hoặc khi scale nhiều instance thì phải dùng Redis thật.

### Bài 5.4: Load balancing

Dựa trên `05-scaling-reliability/production/docker-compose.yml` và `nginx.conf`:

- `agent` có thể scale thành nhiều replicas.
- `redis` là shared state.
- `nginx` expose port `8080:80` và proxy tới `agent:8000`.
- Docker DNS cho phép service name `agent` đại diện cho các containers agent.

Lệnh chạy:

```bash
cd 05-scaling-reliability/production
docker compose up --scale agent=3
```

Architecture:

```text
Client -> Nginx :8080 -> Agent replicas :8000 -> Redis :6379
```

### Bài 5.5: Test stateless

Script `05-scaling-reliability/production/test_stateless.py` kiểm tra:

1. Tạo session mới qua `POST /chat`.
2. Gửi nhiều request với cùng `session_id`.
3. In `served_by` để thấy request có thể đi qua nhiều instance.
4. Gọi `GET /chat/{session_id}/history` để xác nhận history vẫn đầy đủ.

Lệnh chạy:

```bash
python3 test_stateless.py
```

Kết quả kỳ vọng:

```text
All requests served despite different instances
Session history preserved across all instances via Redis
```

Kết luận: Vì state nằm trong Redis, instance nào cũng có thể phục vụ request tiếp theo của cùng một session.

---

## Phần 6: Final Project

Thư mục sử dụng: `06-lab-complete/`

### Các yêu cầu đã đáp ứng

- Có `app/main.py`, `app/config.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`.
- Có `utils/mock_llm.py`.
- Có multi-stage `Dockerfile`.
- Có `docker-compose.yml` với `agent`, `redis`, `nginx`.
- Có `.env.example`, `.dockerignore`, `railway.toml`, `render.yaml`, `README.md`.
- API key authentication qua `X-API-Key`.
- Rate limiting mặc định 10 requests/phút/user.
- Cost guard mặc định `$10/tháng/user`.
- Conversation history lưu trong Redis.
- Health check `/health`.
- Readiness check `/ready`.
- Graceful shutdown.
- Stateless design với Redis.
- Structured JSON logging.
- Không hardcode secrets thật.

### Kết quả kiểm tra local

Command đã chạy trong `06-lab-complete/`:

```bash
docker compose up -d --build --scale agent=3
python3 check_production_ready.py
```

Kết quả:

```text
Result: 20/20 checks passed (100%)
PRODUCTION READY
```

Docker stack:

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
