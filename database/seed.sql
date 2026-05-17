USE eduai_hub;

INSERT INTO roles(code, name) VALUES
('principal', 'Hiệu trưởng'),
('vice_principal', 'Phó hiệu trưởng'),
('teacher', 'Giáo viên'),
('student', 'Học sinh'),
('admin', 'Quản trị hệ thống');

INSERT INTO permissions(code, name) VALUES
('ioffice.sync', 'Đồng bộ iOffice'),
('rag.management.query', 'Truy vấn RAG Quản lý'),
('rag.teaching.query', 'Truy vấn RAG Dạy học'),
('rag.learning.query', 'Truy vấn RAG Học tập'),
('system.users.manage', 'Quản trị người dùng');

INSERT INTO subjects(name, level) VALUES
('Toán', 'THPT'),
('Vật lý', 'THPT'),
('Ngữ văn', 'THPT'),
('Tiếng Anh', 'THPT');
