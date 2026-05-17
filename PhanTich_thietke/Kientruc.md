# EDUAI HUB – PHÂN TÍCH & THIẾT KẾ HỆ THỐNG

> Tài liệu kỹ thuật dùng thống nhất cho đội phát triển (Backend – Frontend – AI – Data)

---

## 1. MỤC TIÊU TÀI LIỆU

* Chuẩn hóa **thiết kế tổng thể hệ thống EduAI Hub**
* Làm căn cứ triển khai code cho đội nhóm
* Đảm bảo đúng: **MVC – AI có kiểm soát – RAG hai miền dữ liệu**

---

## 2. TỔNG QUAN HỆ THỐNG

EduAI Hub là nền tảng AI tích hợp phục vụ **3 nhóm nghiệp vụ chính**:

1. **Quản lý nhà trường** (Hiệu trưởng, BGH)
2. **Dạy học** (Giáo viên)
3. **Học tập cá nhân hóa** (Học sinh – kế thừa DeepTutor)

Hệ thống tuân thủ nguyên tắc:

> **AI gợi ý → Con người kiểm tra → Con người quyết định → Hệ thống thực thi**

---

## 3. KIẾN TRÚC TỔNG THỂ

### 3.1. Mô hình kiến trúc

```
Frontend (AdminLTE 4 – Web)
        ↓
Controller / API (Backend)
        ↓
Model (CSDL nghiệp vụ + Vector DB RAG)
        ↓
AI Services (LLM + RAG + Agent + Memory)
```

### 3.2. Công nghệ đề xuất

| Thành phần     | Công nghệ           | Lý do chọn               |
| -------------- | ------------------- | ------------------------ |
| Backend        | FastAPI (Python)    | Nhẹ, nhanh, hợp AI       |
| Frontend       | AdminLTE 4          | Quen thuộc, dễ mở rộng   |
| CSDL nghiệp vụ | **MySQL / MariaDB** | Dễ cài, dễ đóng gói      |
| Vector DB      | **Qdrant**          | Dễ triển khai, mạnh, nhẹ |
| AI             | LLM API / Local LLM | Linh hoạt                |

---

## 4. MÔ HÌNH MVC CHI TIẾT

### 4.1. View (Frontend – AdminLTE 4)

```
views/
├── dashboard/
├── management/
│   ├── documents
│   ├── ai-assistant
├── teaching/
│   ├── materials
│   ├── lesson-plans
├── learning/
│   ├── tutor
│   ├── progress
├── rag/
├── system/
```

---

### 4.2. Controller (Business Logic)

```
controllers/
├── AuthController
├── UserController
├── SchoolController
├── ManagementController
├── TeachingController
├── LearningController
├── RagController
├── AIController
├── IOfficeController
```

**Vai trò Controller:**

* Nhận request
* Kiểm tra quyền
* Gọi RAG / AI
* Yêu cầu người dùng duyệt
* Lưu log quyết định

---

### 4.3. Model – CSDL nghiệp vụ (MySQL / MariaDB)

> Chọn **MariaDB** nếu cần nhẹ, dễ đóng gói

#### 4.3.1. Người dùng & phân quyền

```sql
users(id, name, email, role, school_id, created_at)
roles(id, name)
permissions(id, name)
```

---

#### 4.3.2. Quản lý nhà trường

```sql
schools(id, name, level, address)

official_documents(
  id, source, title, issue_date,
  category, file_path, synced_at
)

management_decisions(
  id, user_id,
  ai_suggestion,
  final_decision,
  created_at
)
```

---

#### 4.3.3. Dạy học & học liệu

```sql
subjects(id, name, level)

teaching_materials(
  id, subject_id, grade,
  title, file_path, uploaded_by
)

lesson_plans(
  id, teacher_id, subject_id,
  content, created_at
)
```

---

#### 4.3.4. Học tập (DeepTutor mở rộng)

```sql
learning_sessions(
  id, student_id, topic, ai_feedback
)

learning_progress(
  id, student_id, subject_id, progress_data
)
```

---

## 5. VECTOR DATABASE (RAG)

### 5.1. Vector DB được chọn: **Qdrant**

**Lý do:**

* Chạy bằng Docker 1 lệnh
* Không phụ thuộc cloud
* Quản lý collection rõ ràng
* Hỗ trợ metadata filtering tốt

👉 Phù hợp **dự án giáo dục + đóng gói offline**

---

### 5.2. Thiết kế RAG hai miền dữ liệu

```
RAG_MANAGEMENT (Quản lý)
- Văn bản iOffice
- Văn bản nội bộ

RAG_TEACHING (Dạy học)
- Học liệu giáo viên
- SGK số

RAG_LEARNING (Học tập)
- Kiến thức học sinh
```

---

### 5.3. Metadata chuẩn cho vector

```json
{
  "source": "ioffice",
  "type": "official_document",
  "level": "THPT",
  "subject": null,
  "role_allowed": ["principal"],
  "effective_date": "2025-01-01"
}
```

---

## 6. AI SERVICE LAYER

```
ai_services/
├── PromptManager
├── RagRetriever
├── AgentManager
├── MemoryService
├── AuditService
```

### Nguyên tắc bắt buộc:

* Không auto quyết định
* Có log & audit
* Có phân quyền truy vấn RAG

---

## 7. TÍCH HỢP IOFFICE (RAG QUẢN LÝ)

### 7.1. Chức năng

* Đồng bộ văn bản từ iOffice
* Lọc theo quyền Hiệu trưởng
* Chuẩn hóa & embedding

### 7.2. Quy trình

```
iOffice → Sync → Normalize → Embed → Qdrant
```

---

## 8. BẢO MẬT & ĐẠO ĐỨC AI

* Không lưu dữ liệu nhạy cảm
* Không học lại từ dữ liệu người dùng
* Log mọi tương tác AI
* Con người luôn quyết định cuối cùng

---

## 9. ĐỀ XUẤT TRIỂN KHAI

### Giai đoạn 1

* Xây CSDL nghiệp vụ
* RAG quản lý (iOffice)

### Giai đoạn 2

* RAG dạy học
* AI cho giáo viên

### Giai đoạn 3

* AI Tutor học sinh
* Dashboard phân tích

---

## 10. KẾT LUẬN

Tài liệu này là **chuẩn kỹ thuật thống nhất** cho toàn bộ đội phát triển EduAI Hub. Mọi module mới phải tuân thủ kiến trúc MVC, nguyên tắc AI có kiểm soát và thiết kế RAG hai miền dữ liệu.
---------------------
I. PHÂN TÍCH TỔNG THỂ HỆ THỐNG
1. Các vai trò người dùng (Actor)
Vai trò	Chức năng chính
Hiệu trưởng	Quản lý – điều hành – ra quyết định
Phó Hiệu trưởng	Hỗ trợ quản lý
Giáo viên	Dạy học – học liệu – đánh giá
Học sinh	Học tập cá nhân hóa
Quản trị hệ thống	Cấu hình – phân quyền
2. Các phân hệ lớn
EduAI Hub
├── Phân hệ Quản lý nhà trường
├── Phân hệ Dạy học (Giáo viên)
├── Phân hệ Học tập (DeepTutor mở rộng)
├── Phân hệ RAG & AI Services
├── Phân hệ Quản trị hệ thống

II. THIẾT KẾ KIẾN TRÚC MVC
1. Tổng thể MVC
[ View (AdminLTE 4) ]
          │
          ▼
[ Controller (FastAPI / Laravel / Node) ]
          │
          ▼
[ Model (CSDL nghiệp vụ + Vector DB) ]


👉 MVC tách bạch rõ:

View: giao diện

Controller: nghiệp vụ + AI orchestration

Model: dữ liệu + RAG

2. CONTROLLER (Logic & Điều phối AI)
2.1. Nhóm Controller chính
controllers/
├── AuthController
├── UserController
├── ManagementController
├── TeachingController
├── LearningController
├── RagController
├── AIController
├── IOOfficeController

2.2. Vai trò Controller AI (rất quan trọng)

Chuẩn hóa prompt

Phân quyền truy vấn RAG

Điều phối multi-agent (kế thừa DeepTutor)

Áp dụng Human-in-the-loop

Luồng chuẩn:

Request → Controller → RAG → LLM → Human Review → Save

3. MODEL (CSDL nghiệp vụ + RAG)
3.1. CSDL nghiệp vụ (Relational DB – MySQL/PostgreSQL)
🔹 Nhóm người dùng & phân quyền
users (
  id, name, email, role, school_id, created_at
)

roles (
  id, name
)

permissions (
  id, name
)

🔹 Quản lý nhà trường
schools (
  id, name, level, address
)

official_documents (
  id, source, title, issue_date, category, file_path
)

management_decisions (
  id, user_id, ai_suggestion, final_decision, created_at
)

🔹 Dạy học & học liệu
subjects (
  id, name, level
)

teaching_materials (
  id, subject_id, grade, title, file_path, uploaded_by
)

lesson_plans (
  id, teacher_id, subject_id, content
)

🔹 Học tập (DeepTutor mở rộng)
learning_sessions (
  id, student_id, topic, ai_feedback
)

learning_progress (
  id, student_id, subject_id, progress_data
)

3.2. CSDL RAG – Vector Database

👉 Tách biệt khỏi CSDL nghiệp vụ

🔹 Vector DB (FAISS / Milvus / Qdrant)
rag_management_vectors
rag_teaching_vectors
rag_learning_vectors

🔹 Metadata đi kèm vector
{
  "source": "ioffice",
  "document_type": "official",
  "level": "THPT",
  "effective_date": "2025-01-01",
  "permission": ["principal"]
}


👉 Điều này giúp:

Truy vấn đúng vai trò

Không trộn quản lý & dạy học

4. VIEW – GIAO DIỆN ADMINLTE 4
4.1. Cấu trúc giao diện
AdminLTE 4
├── Dashboard
├── Quản lý nhà trường
│   ├── Văn bản iOffice
│   ├── Trợ lý AI Hiệu trưởng
│   ├── Báo cáo – Thống kê
├── Dạy học
│   ├── Quản lý học liệu
│   ├── Trợ lý AI Giáo viên
├── Học tập
│   ├── AI Tutor (DeepTutor)
│   ├── Tiến trình học tập
├── RAG & AI
│   ├── Dữ liệu RAG
│   ├── Lịch sử AI
├── Hệ thống
│   ├── Người dùng
│   ├── Phân quyền

4.2. Dashboard (ăn điểm trình diễn)

Dashboard Hiệu trưởng:

Thống kê quyết định

Văn bản mới từ iOffice

Gợi ý AI nổi bật

Dashboard Giáo viên:

Bài dạy

Học liệu

Tiến độ lớp học

III. KIẾN TRÚC RAG & AI SERVICES (KẾ THỪA DEEPTUTOR)
1. AI Service Layer
ai_services/
├── PromptManager
├── RagRetriever
├── AgentManager
├── MemoryService
├── AuditService

2. Luồng RAG chuẩn
User Request
→ Controller
→ PromptManager
→ RagRetriever
→ LLM
→ Human Review
→ Save Decision

3. Kế thừa DeepTutor (điểm sáng tạo)
DeepTutor	EduAI Hub
Learning RAG	Dual-RAG (Quản lý + Dạy học)
Tutor Agent	Manager Agent + Teacher Agent
Memory học tập	Memory quản lý + audit
Knowledge Graph	Văn bản iOffice + học liệu
IV. BẢO MẬT – KIỂM SOÁT – ĐẠO ĐỨC AI

Phân quyền truy cập RAG

Không truy vấn vượt vai trò

Log mọi tương tác AI

Không tự động ban hành quyết định

V. TÓM TẮT GIÁ TRỊ KHOA HỌC

Thiết kế này:

✅ Chuẩn MVC – kiến trúc hiện đại

✅ Tách bạch nghiệp vụ – AI – dữ liệu

✅ Dùng được ngay trong thực tế

✅ Rất dễ bảo vệ trước BGK

✅ Dễ mở rộng cấp tỉnh