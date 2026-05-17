USE eduai_hub;

INSERT INTO roles(code, name) VALUES
('principal', 'Hiệu trưởng'),
('vice_principal', 'Phó hiệu trưởng'),
('teacher', 'Giáo viên'),
('student', 'Học sinh'),
('admin', 'Quản trị hệ thống')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO permissions(code, name) VALUES
('ioffice.sync', 'Đồng bộ iOffice'),
('rag.management.query', 'Truy vấn RAG Quản lý'),
('rag.teaching.query', 'Truy vấn RAG Dạy học'),
('rag.learning.query', 'Truy vấn RAG Học tập'),
('system.users.manage', 'Quản trị người dùng')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO subjects(name, level) VALUES
('Toán', 'THPT'),
('Vật lý', 'THPT'),
('Ngữ văn', 'THPT'),
('Tiếng Anh', 'THPT')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO schools(name, level, address)
SELECT 'Trường Demo EduAI', 'THPT', 'Dữ liệu mẫu cho hệ thống mới cài đặt'
WHERE NOT EXISTS (
  SELECT 1 FROM schools WHERE name = 'Trường Demo EduAI'
);

INSERT INTO users(school_id, name, email, password_hash, status)
SELECT s.id, 'Quản trị Demo', 'admin@eduai.local', SHA2('Demo@123456', 256), 'ACTIVE'
FROM schools s
WHERE s.name = 'Trường Demo EduAI'
  AND NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'admin@eduai.local'
  );

INSERT INTO user_roles(user_id, role_id)
SELECT u.id, r.id
FROM users u
JOIN roles r ON r.code = 'admin'
WHERE u.email = 'admin@eduai.local'
  AND NOT EXISTS (
    SELECT 1
    FROM user_roles ur
    WHERE ur.user_id = u.id AND ur.role_id = r.id
  );
