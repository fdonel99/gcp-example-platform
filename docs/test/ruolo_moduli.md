# Ruolo dei Moduli Terraform

*Ultimo aggiornamento automatico: 18/08/2026 alle 12:39:07 (UTC) (Deploy in ambiente: **test**)*

---

# Operational Guide: Terraform Module Analysis

This document provides an overview of the Terraform modules used in our project. Each module has been described in terms of its business role, the resources it creates, and the key variables that facilitate its configuration.

## Module Overview

- **data_storage**: Manages Google BigQuery datasets and Google Cloud Storage buckets.
- **orchestration**: Manages the scheduling of Cloud Functions using Google Cloud Scheduler.
- **compute_functions**: Manages Google Cloud Functions for various data processing tasks.
- **setup**: Configures project-wide settings including APIs, IAM roles, and secrets.

---

## Module: data_storage

### Business Role
The **data_storage** module is responsible for the setup of datasets in BigQuery and storage buckets in Google Cloud Storage. This is critical for data storage, archival, and staging in our data processing pipelines.

### Resources Created
- **BigQuery Datasets**: 
  - `dataset_principale`, `dataset_dati_storico`, `dataset_dati_staging` - Used for storing primary data, historical data, and staging data respectively.
- **Google Storage Buckets**:
  - Buckets like `import_ns_zip`, `spese_trasporto`, `infografica_input`, etc., for storing various types of files necessary for different business functions.

### Key Variables
- `project_id`: GCP Project ID.
- `environment`: Deployment environment (e.g., prod, test).

---

## Module: orchestration

### Business Role
The **orchestration** module schedules the execution of Cloud Functions, enabling automated workflows crucial for the periodic data import and processing tasks.

### Resources Created
- **Cloud Scheduler Jobs**:
  - `schedulazione_drive_to_gcp`: For importing data from Google Drive to BigQuery.
  - `schedulazione_tables_loading`: For loading tables into BigQuery.
  - Additional jobs for exporting product and vendor reports.

### Key Variables
- `project_id`: GCP Project ID.
- `environment`: Deployment environment.
- `region`: The region where the job is executed.
- `function_*_uri`: URIs for various Cloud Functions.

---

## Module: compute_functions

### Business Role
The **compute_functions** module encompasses serverless functions used for data processing, including importing data, running analytics, and generating exports. Fundamental for the data integration operations.

### Resources Created
- **Cloud Functions**:
  - For tasks such as translating infographics, calculating transportation expenses, and loading historical data into BigQuery.

### Key Variables
- `project_id`: GCP Project ID.
- `environment`: Deployment environment.
- `bucket_*_name`: Various buckets used for deploying function code and managing function runtime triggers.
- `cloud_worker_sa_email`: Service account used by the functions.

---

## Module: setup

### Business Role
The **setup** module sets up foundational GCP resources such as enabling necessary APIs and creating service accounts, ensuring proper IAM configurations and secret management essential for application security and operation.

### Resources Created
- **Service Accounts**:
  - Includes `cloud_worker`, `cloud_deployer`, `bq_scheduler`, and `cf_scheduler` with specific roles and permissions.
- **Secret Manager Entries**:
  - Secrets for sensitive information like Telegram tokens.

### Key Variables
- `project_id`: GCP Project ID.
- `environment`: Deployment environment.
- `telegram_token_value`, `telegram_chat_id_value`: Sensitive tokens used for notifications.

---

## Important Considerations

- **Environment Specifics**: Each module uses an `environment` variable to cater configurations to different deployment environments (e.g., prod, test).
- **Security**: The `setup` module establishes critical security infrastructure, ensuring all actions taken by resources operate with the principle of least privilege.
- **Data Lifecycle Management**: The `data_storage` module implements lifecycle rules for bucket contents, controlling data expiration based on use-case.
- **Cross-Module Dependencies**: Variables passed among modules (e.g., URIs for Cloud Functions or service account emails) underscore the interdependencies for achieving end-to-end workflows.

This document is intended to offer clarity for cloud engineers and system administrators managing infrastructure components in the defined GCP environment using Terraform. This enables efficient troubleshooting, scaling, and modification to accommodate business evolution.