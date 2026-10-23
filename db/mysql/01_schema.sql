-- Base source des clients (MySQL 8) : alimentée en données fictives, lue par Airflow.
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS clients (
  id               INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  code_client      CHAR(10)      NOT NULL COMMENT 'Identifiant métier CLI-000000',
  nom              VARCHAR(80)   NOT NULL,
  prenom           VARCHAR(80)   NOT NULL,
  email            VARCHAR(190)  NOT NULL,
  telephone        VARCHAR(20)   NULL,
  ville            VARCHAR(80)   NULL,
  pays             VARCHAR(60)   NOT NULL DEFAULT 'Burkina Faso',
  statut           ENUM('actif','inactif','suspendu') NOT NULL DEFAULT 'actif',
  date_inscription DATE          NOT NULL,
  created_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_clients_code  (code_client),
  UNIQUE KEY uq_clients_email (email),
  KEY idx_clients_updated_at (updated_at),
  KEY idx_clients_ville (ville)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
