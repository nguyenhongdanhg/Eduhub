CREATE DATABASE IF NOT EXISTS eduai_hub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE eduai_hub;

CREATE TABLE schools (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  level ENUM('MN','TH','THCS','THPT','OTHER') NOT NULL DEFAULT 'OTHER',
  address VARCHAR(512) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_schools_name (name)
) ENGINE=InnoDB;

CREATE TABLE subjects (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  level ENUM('MN','TH','THCS','THPT','OTHER') NOT NULL DEFAULT 'OTHER',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_subjects_name_level (name, level)
) ENGINE=InnoDB;

CREATE TABLE roles (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_roles_code (code)
) ENGINE=InnoDB;

CREATE TABLE permissions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code VARCHAR(128) NOT NULL,
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_permissions_code (code)
) ENGINE=InnoDB;

CREATE TABLE role_permissions (
  role_id BIGINT UNSIGNED NOT NULL,
  permission_id BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (role_id, permission_id),
  CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
  CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id BIGINT UNSIGNED NULL,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  status ENUM('ACTIVE','DISABLED') NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_school_id (school_id),
  CONSTRAINT fk_users_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE user_roles (
  user_id BIGINT UNSIGNED NOT NULL,
  role_id BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, role_id),
  CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE school_classes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(255) NOT NULL,
  grade TINYINT UNSIGNED NOT NULL,
  homeroom_teacher_id BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_school_classes_school_name (school_id, name),
  KEY idx_school_classes_school_id (school_id),
  KEY idx_school_classes_teacher_id (homeroom_teacher_id),
  CONSTRAINT fk_school_classes_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
  CONSTRAINT fk_school_classes_teacher FOREIGN KEY (homeroom_teacher_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE class_enrollments (
  class_id BIGINT UNSIGNED NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (class_id, student_id),
  KEY idx_class_enrollments_student (student_id),
  CONSTRAINT fk_class_enrollments_class FOREIGN KEY (class_id) REFERENCES school_classes(id) ON DELETE CASCADE,
  CONSTRAINT fk_class_enrollments_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE official_documents (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id BIGINT UNSIGNED NULL,
  source ENUM('IOFFICE','INTERNAL','OTHER') NOT NULL DEFAULT 'OTHER',
  title VARCHAR(512) NOT NULL,
  issue_date DATE NULL,
  category VARCHAR(255) NULL,
  file_path VARCHAR(1024) NULL,
  external_ref VARCHAR(255) NULL,
  synced_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_official_documents_school_id (school_id),
  KEY idx_official_documents_issue_date (issue_date),
  CONSTRAINT fk_official_documents_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE teaching_materials (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id BIGINT UNSIGNED NULL,
  subject_id BIGINT UNSIGNED NOT NULL,
  grade TINYINT UNSIGNED NULL,
  title VARCHAR(512) NOT NULL,
  file_path VARCHAR(1024) NULL,
  uploaded_by BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_teaching_materials_school_id (school_id),
  KEY idx_teaching_materials_subject_id (subject_id),
  KEY idx_teaching_materials_uploaded_by (uploaded_by),
  CONSTRAINT fk_teaching_materials_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL,
  CONSTRAINT fk_teaching_materials_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE RESTRICT,
  CONSTRAINT fk_teaching_materials_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE lesson_plans (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id BIGINT UNSIGNED NULL,
  teacher_id BIGINT UNSIGNED NOT NULL,
  subject_id BIGINT UNSIGNED NOT NULL,
  grade TINYINT UNSIGNED NULL,
  title VARCHAR(512) NOT NULL,
  content LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_lesson_plans_teacher_id (teacher_id),
  KEY idx_lesson_plans_school_id (school_id),
  KEY idx_lesson_plans_subject_id (subject_id),
  CONSTRAINT fk_lesson_plans_teacher FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_lesson_plans_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE RESTRICT,
  CONSTRAINT fk_lesson_plans_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE learning_sessions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id BIGINT UNSIGNED NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  topic VARCHAR(512) NOT NULL,
  ai_feedback LONGTEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_learning_sessions_student_id (student_id),
  KEY idx_learning_sessions_school_id (school_id),
  CONSTRAINT fk_learning_sessions_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_learning_sessions_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE learning_progress (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id BIGINT UNSIGNED NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  subject_id BIGINT UNSIGNED NOT NULL,
  progress_data JSON NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_learning_progress_student_subject (student_id, subject_id),
  KEY idx_learning_progress_school_id (school_id),
  KEY idx_learning_progress_subject_id (subject_id),
  CONSTRAINT fk_learning_progress_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_learning_progress_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE RESTRICT,
  CONSTRAINT fk_learning_progress_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE rag_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  rag_document_id BIGINT UNSIGNED NULL,
  domain ENUM('MANAGEMENT','TEACHING','LEARNING') NOT NULL,
  source VARCHAR(64) NOT NULL,
  type VARCHAR(64) NOT NULL,
  title VARCHAR(512) NULL,
  original_id VARCHAR(255) NULL,
  chunk_index INT UNSIGNED NULL,
  qdrant_collection VARCHAR(128) NOT NULL,
  qdrant_point_id VARCHAR(128) NOT NULL,
  metadata JSON NOT NULL,
  status ENUM('PENDING','EMBEDDING','READY','FAILED','DELETED') NOT NULL DEFAULT 'PENDING',
  embedded_at TIMESTAMP NULL,
  chunk_tokens INT UNSIGNED NULL,
  content_hash CHAR(64) NULL,
  last_error TEXT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_rag_items_document (rag_document_id),
  KEY idx_rag_items_status (status),
  KEY idx_rag_items_original (domain, source, type, original_id),
  KEY idx_rag_items_domain (domain),
  UNIQUE KEY uq_rag_items_collection_point (qdrant_collection, qdrant_point_id),
  UNIQUE KEY uq_rag_items_doc_chunk (rag_document_id, chunk_index),
  KEY idx_rag_items_collection (qdrant_collection)
) ENGINE=InnoDB;

CREATE TABLE rag_documents (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  domain ENUM('MANAGEMENT','TEACHING','LEARNING') NOT NULL,
  source VARCHAR(64) NOT NULL,
  type VARCHAR(64) NOT NULL,
  original_id VARCHAR(255) NOT NULL,
  title VARCHAR(512) NULL,
  school_id BIGINT UNSIGNED NULL,
  subject_id BIGINT UNSIGNED NULL,
  grade TINYINT UNSIGNED NULL,
  qdrant_collection VARCHAR(128) NOT NULL,
  status ENUM('PENDING','PROCESSING','READY','FAILED','DELETED') NOT NULL DEFAULT 'PENDING',
  file_hash CHAR(64) NULL,
  file_size BIGINT UNSIGNED NULL,
  file_mtime TIMESTAMP NULL,
  file_exists TINYINT(1) NULL,
  file_checked_at TIMESTAMP NULL,
  content_hash CHAR(64) NULL,
  chunk_count INT UNSIGNED NULL,
  last_indexed_at TIMESTAMP NULL,
  last_error TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_rag_documents_origin (domain, source, type, original_id),
  KEY idx_rag_documents_file_hash (file_hash),
  KEY idx_rag_documents_school (school_id),
  KEY idx_rag_documents_subject (subject_id),
  KEY idx_rag_documents_status (status),
  CONSTRAINT fk_rag_documents_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL,
  CONSTRAINT fk_rag_documents_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL
) ENGINE=InnoDB;

ALTER TABLE rag_items
  ADD CONSTRAINT fk_rag_items_document FOREIGN KEY (rag_document_id) REFERENCES rag_documents(id) ON DELETE SET NULL;

CREATE TABLE ai_requests (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  role_effective VARCHAR(64) NULL,
  domain ENUM('MANAGEMENT','TEACHING','LEARNING') NOT NULL,
  prompt LONGTEXT NOT NULL,
  rag_query JSON NULL,
  model VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_ai_requests_user_id (user_id),
  KEY idx_ai_requests_domain (domain),
  CONSTRAINT fk_ai_requests_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE ai_decisions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ai_request_id BIGINT UNSIGNED NOT NULL,
  ai_suggestion LONGTEXT NULL,
  human_decision LONGTEXT NULL,
  decision_status ENUM('DRAFT','APPROVED','REJECTED') NOT NULL DEFAULT 'DRAFT',
  decided_by BIGINT UNSIGNED NULL,
  decided_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_ai_decisions_request (ai_request_id),
  KEY idx_ai_decisions_decided_by (decided_by),
  CONSTRAINT fk_ai_decisions_request FOREIGN KEY (ai_request_id) REFERENCES ai_requests(id) ON DELETE CASCADE,
  CONSTRAINT fk_ai_decisions_decider FOREIGN KEY (decided_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

DELIMITER //
DROP TRIGGER IF EXISTS trg_ai_decisions_bi//
DROP TRIGGER IF EXISTS trg_ai_decisions_bu//
CREATE TRIGGER trg_ai_decisions_bi
BEFORE INSERT ON ai_decisions
FOR EACH ROW
BEGIN
  IF NEW.decision_status <> 'DRAFT' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ai_decisions must start as DRAFT';
  END IF;
  SET NEW.decided_by = NULL;
  SET NEW.decided_at = NULL;
END//
CREATE TRIGGER trg_ai_decisions_bu
BEFORE UPDATE ON ai_decisions
FOR EACH ROW
BEGIN
  IF NEW.decision_status = 'DRAFT' THEN
    SET NEW.decided_by = NULL;
    SET NEW.decided_at = NULL;
  END IF;

  IF NEW.decision_status IN ('APPROVED','REJECTED') THEN
    IF NEW.decided_by IS NULL OR NEW.decided_at IS NULL OR NEW.human_decision IS NULL THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Human approval/rejection requires decided_by, decided_at, human_decision';
    END IF;
  END IF;
END//
DELIMITER ;

CREATE TABLE audit_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NULL,
  action VARCHAR(128) NOT NULL,
  entity_type VARCHAR(128) NULL,
  entity_id VARCHAR(128) NULL,
  payload JSON NULL,
  ip VARCHAR(64) NULL,
  user_agent VARCHAR(512) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_audit_logs_user_id (user_id),
  KEY idx_audit_logs_action (action),
  CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE ioffice_accounts (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  school_id BIGINT UNSIGNED NULL,
  username VARCHAR(255) NOT NULL,
  password_enc VARCHAR(2048) NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_ioffice_accounts_user (user_id),
  KEY idx_ioffice_accounts_school (school_id),
  CONSTRAINT fk_ioffice_accounts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_ioffice_accounts_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE ioffice_documents (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id BIGINT UNSIGNED NULL,
  ioffice_doc_id VARCHAR(128) NOT NULL,
  so_ky_hieu VARCHAR(255) NULL,
  trich_yeu VARCHAR(1024) NULL,
  hinh_thuc VARCHAR(255) NULL,
  ngay_van_ban VARCHAR(64) NULL,
  ngay_den VARCHAR(64) NULL,
  don_vi_ban_hanh VARCHAR(512) NULL,
  vai_tro VARCHAR(255) NULL,
  han_xu_ly VARCHAR(64) NULL,
  trang_thai_xu_ly VARCHAR(255) NULL,
  chi_dao_xl LONGTEXT NULL,
  nhiem_vu LONGTEXT NULL,
  link_goc VARCHAR(1024) NULL,
  file_path VARCHAR(1024) NULL,
  file_name VARCHAR(512) NULL,
  vb_status ENUM('CHO_XU_LY','XEM_DE_BIET','DA_XU_LY') NULL,
  fetch_status ENUM('PENDING','OK','FAILED') NOT NULL DEFAULT 'PENDING',
  fetch_error TEXT NULL,
  summary_text LONGTEXT NULL,
  summary_status ENUM('PENDING','PROCESSING','READY','FAILED') NOT NULL DEFAULT 'PENDING',
  summary_model VARCHAR(255) NULL,
  summary_error TEXT NULL,
  summary_updated_at TIMESTAMP NULL,
  content_hash CHAR(64) NULL,
  synced_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_ioffice_documents_doc (ioffice_doc_id),
  KEY idx_ioffice_documents_school (school_id),
  KEY idx_ioffice_documents_vb_status (vb_status),
  KEY idx_ioffice_documents_fetch_status (fetch_status),
  KEY idx_ioffice_documents_summary_status (summary_status),
  CONSTRAINT fk_ioffice_documents_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE document_categories (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  school_id BIGINT UNSIGNED NULL,
  name VARCHAR(255) NOT NULL,
  parent_id BIGINT UNSIGNED NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_document_categories_user_parent_name (user_id, parent_id, name),
  KEY idx_document_categories_user (user_id),
  KEY idx_document_categories_school (school_id),
  CONSTRAINT fk_document_categories_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_document_categories_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL,
  CONSTRAINT fk_document_categories_parent FOREIGN KEY (parent_id) REFERENCES document_categories(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE document_category_items (
  category_id BIGINT UNSIGNED NOT NULL,
  ioffice_document_id BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (category_id, ioffice_document_id),
  KEY idx_document_category_items_doc (ioffice_document_id),
  CONSTRAINT fk_document_category_items_category FOREIGN KEY (category_id) REFERENCES document_categories(id) ON DELETE CASCADE,
  CONSTRAINT fk_document_category_items_doc FOREIGN KEY (ioffice_document_id) REFERENCES ioffice_documents(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE system_configs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  conf_key VARCHAR(128) NOT NULL,
  conf_value LONGTEXT NULL,
  description VARCHAR(512) NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_system_configs_key (conf_key)
) ENGINE=InnoDB;

CREATE TABLE token_usage_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NULL,
  provider VARCHAR(64) NOT NULL,
  model VARCHAR(128) NOT NULL,
  prompt_tokens INT UNSIGNED NOT NULL DEFAULT 0,
  completion_tokens INT UNSIGNED NOT NULL DEFAULT 0,
  content_type VARCHAR(128) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_token_usage_logs_user (user_id),
  KEY idx_token_usage_logs_created (created_at),
  KEY idx_token_usage_logs_type (content_type)
) ENGINE=InnoDB;
