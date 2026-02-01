# Dự án nhận diện khuôn mặt khách hàng

## Đối tượng khách hàng

- Các chuỗi cửa hàng FnB có nhu cầu theo dõi và đánh giá hiệu quả kinh doanh thông qua các chỉ số về số lượng khách ghé thăm, khách cũ quay lại và tăng trải nghiệm phục vụ khách hàng

## Giải pháp

- Sử dụng công nghệ nhận diện khuôn mặt đặt tại cửa ra vào của cửa hàng để nhận diện và đếm số lượng khách hàng ra / vào cửa hàng.
- Lưu trữ khuôn mặt khách hàng trong thời gian ngắn (1 tháng) để phục vụ hậu kiểm, sau đó sẽ xóa để đảm bảo quyền riêng tư cho khách hàng
- Lưu trữ các vector embedding của khuôn mặt khách hàng lâu dài để phục vụ nhận diện khách hàng quay lại trong tương lai
- Ghi nhận các lượt ghé thăm của khách hàng (Visit) để phục vụ đánh giá hiệu quả kinh doanh và lập báo cáo
- Tạo profile dành cho nhân viên (Staff) với dữ liệu khuôn mặt để tránh nhầm lẫn với khách hàng.

## Danh sách báo cáo

- Số lượng khách hàng ghé thăm
- Số lượng khách hàng ghé thăm theo các chỉ số:
  + Theo giới tính (nam, nữ, không rõ)
  + Theo khung giờ
- Số lượng khách hàng ghé thăm theo các ngày trong tuần

Các báo cáo trên cho phép xem theo các khoảng thời gian:

- Trong ngày
- Theo tuần
- Theo tháng
- Theo khung giờ

## Ý tưởng đề xuất

- Thiết kế hệ thống multi-tenants, mỗi tenant là dành cho một chuỗi cửa hàng
- Mỗi cửa hàng có nhiều cơ sở / chi nhánh (sites)
- Giao diện cho phép tạo và quản lý tenant và site.
- Mỗi cửa hàng có nhiều nhân sự (staff), nhân sự có các thông tin: tên, năm sinh, số điện thoại, email, giới tính và dữ liệu khuôn mặt (tối thiểu 2 ảnh)
- Giao diện cho phép tạo và quản lý nhân sự
- Thông tin khách hàng được chia sẻ chung trên toàn hệ thống: tên, giới tính, năm sinh, số điện thoại
- Giao diện cho phép tạo và quản lý thông tin khách hàng
- Camera stream: là các camera gắn tại các site, cần hỗ trợ cả local webcams và RTSP stream, bao gồm stream type (webcam, rtsp), name, webcamIndex (for webcam) and rtsp url (for rtsp stream)
- Giao diện quản lý camera stream: tạo mới, sửa thông tin, xóa, start, stop, toggle face recognition (with bounding boxes), connect stream on frontend
- Mỗi lượt ghé thăm của khách hàng: ID khách hàng, ID của Site, thời gian ghi nhận được, khuôn mặt ghi nhận (dạng ảnh và vector embedding)
- Giao diện cho phép xem lượt ghé thăm của khách hàng theo Site và khoảng thời gian

## Yêu cầu kĩ thuật

1. Tech stack:

    1.1. Backend
      - Python
      - FastAPI
      - PostgreSQL (to save relational data)
      - Milvus (to save embedding vectors)
      - MinIO (to save files: face images, captured customer photos, etc.)
    1.2. Frontend
      - React + Typescript with Vite bundler
      - Ant.design UI with Tailwind CSS

2. Microservices
  
  - 1 microservice backend: cung cấp các API quản trị và tương tác với frontend
  - multi camera processing services: các worker phục vụ xử lý dữ liệu hình ảnh từ camera: nhận diện và tìm kiếm khuôn mặt, embedding bằng vector và lưu trữ khuôn mặt thông qua API do backend cung cấp, có thể scale horizontally
  - 1 frontend service: sử dụng vite proxy trong chế độ development và nginx trong production, proxy và expose các API từ backend

3. Orchestration

  3.1. Development
  - cần hỗ trợ cả MacOS và Linux
  
  3.2. Production
  - Đóng gói thành docker images
  - Có file docker-compose để chạy với docker
  - Có file deployment+service.yaml để chạy với kubernetes
  - Có zsh script để chạy với MacOS

---

Refined prompt
==============

You are an AI consultant and systems architect specializing in computer vision, distributed systems, and enterprise SaaS platforms.

Your task is to create a comprehensive, step-by-step plan for building the following project:

⸻

Project: Dự án nhận diện khuôn mặt khách hàng

Business Context
	•	Customers: FnB chains that want to track customer visits, repeat customers, and enhance service experience.
	•	Goal: Deploy face recognition at store entrances to count visitors, recognize returning customers, and generate business analytics reports.
	•	Privacy: Store raw face images for 1 month, delete afterward; store face embeddings long-term.

Core Requirements
	•	Multi-tenant SaaS: Each tenant = 1 chain of stores; each chain has multiple sites.
	•	Staff profiles with face data (to avoid confusion with customers).
	•	Customer profiles: shared across tenants (name, gender, birthday, phone).
	•	Camera stream support (local webcams, RTSP).
	•	Visit tracking with embeddings and snapshots.
	•	Reports: visitor counts by time, gender, day of week (daily, weekly, monthly).

Tech Stack
	•	Backend: Python, FastAPI, PostgreSQL, Milvus, MinIO.
	•	Frontend: React + Typescript + Vite, Ant Design + Tailwind CSS.
	•	Microservices:
	•	API backend
	•	Scalable camera workers for face detection/embedding
	•	Frontend service with proxy
	•	Orchestration: Docker images, docker-compose for local, Kubernetes for production, zsh scripts for MacOS/Linux.

⸻

Deliverables Required in Your Response
	1.	System Architecture
	•	Latest recommended design patterns for multi-tenant SaaS.
	•	Microservices layout (backend, workers, frontend).
	•	Data flow (camera → face detection → embedding → database/report).
	•	Privacy & compliance considerations (GDPR-like).
	2.	Face Recognition Pipeline
	•	Recommended libraries/frameworks for face detection, embedding, and recognition (with pros/cons).
	•	Best practices for embedding storage and Milvus schema design.
	•	Accuracy optimization techniques (latest models, embeddings update strategies).
	3.	Database & Storage Schema
	•	Entity-relationship model (customers, staff, visits, tenants, sites, cameras).
	•	Indexing and partitioning strategies for PostgreSQL + Milvus.
	4.	Scalability & Performance
	•	How to horizontally scale camera workers.
	•	Streaming optimization (RTSP/Webcam handling).
	•	Load balancing and caching recommendations.
	5.	Security & Privacy
	•	Data retention policy enforcement (auto-purge raw images after 1 month).
	•	Customer consent & anonymization best practices.
	•	Secure API design (authN/authZ, RBAC).
	6.	DevOps & Deployment
	•	Dockerization strategy.
	•	Suggested Kubernetes manifests (deployment, service, autoscaling).
	•	CI/CD pipeline with testing strategy.
	7.	Frontend UX Recommendations
	•	Admin portal for managing tenants, sites, cameras, staff, and customers.
	•	Real-time monitoring dashboard for visits & camera streams.
	•	Report visualization (charts, filters, exports).
	8.	Future Enhancements
	•	Potential ML improvements (emotion detection, age estimation, loyalty scoring).
	•	Possible integration with POS/CRM systems.
	•	Cost optimization for scaling.

⸻

Important Instructions
	•	Always provide latest research-backed techniques and tools (2024–2025).
	•	Structure your response with clear sections, subheadings, and diagrams (if possible in text).
	•	Include concrete implementation recommendations (specific frameworks, Python libraries, database schema suggestions).
	•	Explain trade-offs where applicable.
	•	Focus on enterprise-readiness (scalability, security, compliance).

⸻

🔑 Final Goal: Produce a detailed project plan and technical blueprint that a development team can use as a foundation for implementation.
