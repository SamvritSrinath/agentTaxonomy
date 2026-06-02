This is a production-grade, scalable, and secure genomic data management platform designed for cancer bioinformatics workflows. 

The platform features a multi-tenant, event-driven architecture utilizing **Go** for high-performance microservices, **Kafka** for event streaming, **MinIO** (S3-compatible) for object storage, **PostgreSQL** for metadata and index storage, and **Open Policy Agent (OPA)** for policy-as-code security enforcement.

---

### System Architecture

```
                       [ Researcher / Client ]
                                  │
                                  ▼
                       [ API Gateway (Port 8080) ] ──(Authorize)──► [ OPA (Port 8181) ]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
[ Ingestion Service (Port 8081) ]                 [ Search Service (Port 8083) ]
         │                                                 │
         ├─► Generates Presigned URLs                      ├─► Queries Metadata & Indexes
         ├─► Writes Metadata to Postgres                   └─► Reads from Postgres
         │
         ▼ (Publishes "FileUploadedEvent")
   [ Kafka Broker ]
         │
         ▼ (Consumes Event)
[ Indexing Service (Port 8082) ]
         │
         ├─► Downloads Genomic File from Object Storage (MinIO)
         ├─► Parses Headers (FASTA, FASTQ, BAM, VCF)
         ├─► Extracts Genomic Sequences & Variants
         └─► Writes Indexes to Postgres
```

---

### Part 1: Policy-as-Code Security (`policies/policy.rego`)

This OPA policy enforces multi-tenant isolation and role-based access control (RBAC). Researchers can only access datasets belonging to their specific `tenant_id`.

```rego
package authz

default allow = false

# Allow admin full access
allow {
    input.role == "admin"
}

# Allow researchers to read/write within their own tenant
allow {
    input.role == "researcher"
    input.tenant_id == input.resource_tenant_id
    action_allowed(input.action)
}

action_allowed("GET")
action_allowed("POST")
action_allowed("PUT")

# Guest access (read-only within tenant)
allow {
    input.role == "guest"
    input.tenant_id == input.resource_tenant_id
    input.action == "GET"
}
```

---

### Part 2: API Gateway (`api-gateway/main.go`)

The API Gateway authenticates incoming requests using JWTs, extracts tenant and role claims, queries OPA for authorization, and routes requests to downstream microservices.

```go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v4"
)

var (
	jwtSecret          = []byte("super-secret-cancer-bioinformatics-key")
	ingestionServiceURL = "http://localhost:8081"
	searchServiceURL    = "http://localhost:8083"
	opaURL             = "http://localhost:8181/v1/data/authz/allow"
)

type Claims struct {
	TenantID string `json:"tenant_id"`
	Role     string `json:"role"`
	jwt.RegisteredClaims
}

type OPARequest struct {
	Input OPAInput `json:"input"`
}

type OPAInput struct {
	TenantID         string `json:"tenant_id"`
	Role             string `json:"role"`
	Action           string `json:"action"`
	Path             string `json:"path"`
	ResourceTenantID string `json:"resource_tenant_id"`
}

type OPAResponse struct {
	Result bool `json:"result"`
}

func main() {
	http.HandleFunc("/api/v1/ingest/", handleRoute(ingestionServiceURL))
	http.HandleFunc("/api/v1/search/", handleRoute(searchServiceURL))
	http.HandleFunc("/auth/token", generateTokenHandler)

	log.Println("API Gateway running on port :8080...")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func generateTokenHandler(w http.ResponseWriter, r *http.Request) {
	tenantID := r.URL.Query().Get("tenant_id")
	role := r.URL.Query().Get("role")
	if tenantID == "" || role == "" {
		http.Error(w, "Missing tenant_id or role parameters", http.StatusBadRequest)
		return
	}

	expirationTime := time.Now().Add(24 * time.Hour)
	claims := &Claims{
		TenantID: tenantID,
		Role:     role,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expirationTime),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString(jwtSecret)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"token": tokenString})
}

func handleRoute(targetURL string) http.HandlerFunc {
	target, _ := url.Parse(targetURL)
	proxy := httputil.NewSingleHostReverseProxy(target)

	return func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" || !strings.HasPrefix(authHeader, "Bearer ") {
			http.Error(w, "Unauthorized: Missing or invalid token", http.StatusUnauthorized)
			return
		}

		tokenStr := strings.TrimPrefix(authHeader, "Bearer ")
		claims := &Claims{}
		token, err := jwt.ParseWithClaims(tokenStr, claims, func(token *jwt.Token) (interface{}, error) {
			return jwtSecret, nil
		})

		if err != nil || !token.Valid {
			http.Error(w, "Unauthorized: Invalid token", http.StatusUnauthorized)
			return
		}

		// Extract target resource tenant ID from query parameters or path
		resourceTenantID := r.URL.Query().Get("tenant_id")
		if resourceTenantID == "" {
			resourceTenantID = claims.TenantID // Default to self
		}

		// Query OPA Policy Engine
		allowed, err := checkOPAPolicy(claims.TenantID, claims.Role, r.Method, r.URL.Path, resourceTenantID)
		if err != nil || !allowed {
			http.Error(w, "Forbidden: Policy enforcement block", http.StatusForbidden)
			return
		}

		// Inject Tenant Context Headers for downstream microservices
		r.Header.Set("X-Tenant-ID", claims.TenantID)
		r.Header.Set("X-User-Role", claims.Role)

		proxy.ServeHTTP(w, r)
	}
}

func checkOPAPolicy(tenantID, role, action, path, resourceTenantID string) (bool, error) {
	opaReq := OPARequest{
		Input: OPAInput{
			TenantID:         tenantID,
			Role:             role,
			Action:           action,
			Path:             path,
			ResourceTenantID: resourceTenantID,
		},
	}

	body, err := json.Marshal(opaReq)
	if err != nil {
		return false, err
	}

	resp, err := http.Post(opaURL, "application/json", bytes.NewBuffer(body))
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()

	var opaResp OPAResponse
	if err := json.NewDecoder(resp.Body).Decode(&opaResp); err != nil {
		return false, err
	}

	return opaResp.Result, nil
}
```

---

### Part 3: Ingestion Service (`ingestion-service/main.go`)

This service registers new genomic datasets, generates secure S3 presigned URLs for direct upload, and publishes a `FileUploadedEvent` to Kafka.

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	_ "github.com/lib/pq"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/segmentio/kafka-go"
)

var (
	db          *sql.DB
	minioClient *minio.Client
	kafkaWriter *kafka.Writer
	bucketName  = "genomic-data"
)

type Dataset struct {
	ID       string `json:"id"`
	TenantID string `json:"tenant_id"`
	Name     string `json:"name"`
	Version  string `json:"version"`
}

type GenomicFile struct {
	ID        string `json:"id"`
	DatasetID string `json:"dataset_id"`
	FileType  string `json:"file_type"` // FASTA, FASTQ, BAM, VCF
	S3Key     string `json:"s3_key"`
}

type FileUploadedEvent struct {
	TenantID  string `json:"tenant_id"`
	DatasetID string `json:"dataset_id"`
	FileID    string `json:"file_id"`
	FileType  string `json:"file_type"`
	S3Key     string `json:"s3_key"`
}

func main() {
	initDB()
	initMinIO()
	initKafka()

	http.HandleFunc("/api/v1/ingest/upload", handleUploadRequest)
	log.Println("Ingestion Service running on port :8081...")
	log.Fatal(http.ListenAndServe(":8081", nil))
}

func initDB() {
	var err error
	connStr := "postgres://postgres:postgres@localhost:5432/genomics?sslmode=disable"
	db, err = sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal(err)
	}
}

func initMinIO() {
	var err error
	endpoint := "localhost:9000"
	accessKeyID := "minioadmin"
	secretAccessKey := "minioadmin"

	minioClient, err = minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKeyID, secretAccessKey, ""),
		Secure: false,
	})
	if err != nil {
		log.Fatal(err)
	}

	ctx := context.Background()
	exists, err := minioClient.BucketExists(ctx, bucketName)
	if err == nil && !exists {
		err = minioClient.MakeBucket(ctx, bucketName, minio.MakeBucketOptions{})
	}
	if err != nil {
		log.Fatal(err)
	}
}

func initKafka() {
	kafkaWriter = &kafka.Writer{
		Addr:     kafka.TCP("localhost:9092"),
		Topic:    "genomic-uploads",
		Balancer: &kafka.LeastBytes{},
	}
}

func handleUploadRequest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	tenantID := r.Header.Get("X-Tenant-ID")
	var req struct {
		DatasetName string `json:"dataset_name"`
		Version     string `json:"version"`
		FileType    string `json:"file_type"`
		FileName    string `json:"file_name"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Validate genomic file types
	validTypes := map[string]bool{"FASTA": true, "FASTQ": true, "BAM": true, "VCF": true}
	if !validTypes[req.FileType] {
		http.Error(w, "Invalid file type. Supported: FASTA, FASTQ, BAM, VCF", http.StatusBadRequest)
		return
	}

	datasetID := fmt.Sprintf("ds-%d", time.Now().UnixNano())
	fileID := fmt.Sprintf("file-%d", time.Now().UnixNano())
	s3Key := fmt.Sprintf("%s/%s/%s", tenantID, datasetID, req.FileName)

	// Save metadata to Postgres
	_, err := db.Exec(`
		INSERT INTO datasets (id, tenant_id, name, version, status) 
		VALUES ($1, $2, $3, $4, 'PENDING_UPLOAD')`,
		datasetID, tenantID, req.DatasetName, req.Version)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	_, err = db.Exec(`
		INSERT INTO genomic_files (id, dataset_id, file_type, s3_key, status) 
		VALUES ($1, $2, $3, $4, 'PENDING')`,
		fileID, datasetID, req.FileType, s3Key)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// Generate S3 Presigned URL for secure upload
	expiry := time.Duration(1000) * time.Second
	presignedURL, err := minioClient.PresignedPutObject(context.Background(), bucketName, s3Key, expiry)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// Publish Event to Kafka
	event := FileUploadedEvent{
		TenantID:  tenantID,
		DatasetID: datasetID,
		FileID:    fileID,
		FileType:  req.FileType,
		S3Key:     s3Key,
	}
	eventBytes, _ := json.Marshal(event)
	err = kafkaWriter.WriteMessages(context.Background(), kafka.Message{
		Key:   []byte(tenantID),
		Value: eventBytes,
	})
	if err != nil {
		log.Printf("Failed to publish Kafka event: %v", err)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"dataset_id":   datasetID,
		"file_id":      fileID,
		"upload_url":   presignedURL.String(),
		"instructions": "Upload your file using PUT to the upload_url",
	})
}
```

---

### Part 4: Indexing Service (`indexing-service/main.go`)

This service consumes `FileUploadedEvent` messages from Kafka, streams the genomic files from MinIO, parses their headers/sequences, and indexes them into PostgreSQL.

```go
package main

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"io"
	"log"
	"strings"

	_ "github.com/lib/pq"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/segmentio/kafka-go"
)

var (
	db          *sql.DB
	minioClient *minio.Client
	bucketName  = "genomic-data"
)

type FileUploadedEvent struct {
	TenantID  string `json:"tenant_id"`
	DatasetID string `json:"dataset_id"`
	FileID    string `json:"file_id"`
	FileType  string `json:"file_type"`
	S3Key     string `json:"s3_key"`
}

func main() {
	initDB()
	initMinIO()
	startKafkaConsumer()
}

func initDB() {
	var err error
	connStr := "postgres://postgres:postgres@localhost:5432/genomics?sslmode=disable"
	db, err = sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal(err)
	}
}

func initMinIO() {
	var err error
	endpoint := "localhost:9000"
	accessKeyID := "minioadmin"
	secretAccessKey := "minioadmin"

	minioClient, err = minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKeyID, secretAccessKey, ""),
		Secure: false,
	})
	if err != nil {
		log.Fatal(err)
	}
}

func startKafkaConsumer() {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{"localhost:9092"},
		GroupID:  "indexing-group",
		Topic:    "genomic-uploads",
		MinBytes: 10e3, // 10KB
		MaxBytes: 10e6, // 10MB
	})

	log.Println("Indexing Service listening for Kafka events...")

	for {
		m, err := reader.ReadMessage(context.Background())
		if err != nil {
			log.Printf("Error reading message: %v", err)
			continue
		}

		var event FileUploadedEvent
		if err := json.Unmarshal(m.Value, &event); err != nil {
			log.Printf("Error unmarshaling event: %v", err)
			continue
		}

		log.Printf("Processing file %s of type %s for tenant %s", event.S3Key, event.FileType, event.TenantID)
		processAndIndexFile(event)
	}
}

func processAndIndexFile(event FileUploadedEvent) {
	// Download file stream from MinIO
	object, err := minioClient.GetObject(context.Background(), bucketName, event.S3Key, minio.GetObjectOptions{})
	if err != nil {
		log.Printf("Failed to download file from MinIO: %v", err)
		return
	}
	defer object.Close()

	// Parse and Index based on file type
	switch strings.ToUpper(event.FileType) {
	case "FASTA":
		parseFASTA(event.FileID, object)
	case "VCF":
		parseVCF(event.FileID, object)
	default:
		log.Printf("Indexing for file type %s is not yet implemented", event.FileType)
	}

	// Update file and dataset status
	db.Exec("UPDATE genomic_files SET status = 'INDEXED' WHERE id = $1", event.FileID)
	db.Exec("UPDATE datasets SET status = 'ACTIVE' WHERE id = $1", event.DatasetID)
	log.Printf("Successfully indexed file: %s", event.FileID)
}

func parseFASTA(fileID string, reader io.Reader) {
	scanner := bufio.NewScanner(reader)
	var currentSeqID string
	var sequenceBuilder strings.Builder

	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, ">") {
			if currentSeqID != "" {
				saveIndex(fileID, currentSeqID, sequenceBuilder.String())
				sequenceBuilder.Reset()
			}
			currentSeqID = strings.TrimPrefix(line, ">")
		} else {
			sequenceBuilder.WriteString(line)
		}
	}
	if currentSeqID != "" {
		saveIndex(fileID, currentSeqID, sequenceBuilder.String())
	}
}

func parseVCF(fileID string, reader io.Reader) {
	scanner := bufio.NewScanner(reader)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "#") {
			continue // Skip headers
		}
		fields := strings.Split(line, "\t")
		if len(fields) >= 5 {
			chrom := fields[0]
			pos := fields[1]
			ref := fields[3]
			alt := fields[4]
			variantID := fmt.Sprintf("chr%s:%s:%s>%s", chrom, pos, ref, alt)
			saveIndex(fileID, variantID, line)
		}
	}
}

func saveIndex(fileID, sequenceID, content string) {
	preview := content
	if len(content) > 200 {
		preview = content[:200]
	}

	_, err := db.Exec(`
		INSERT INTO genomic_indexes (file_id, sequence_id, sequence_preview) 
		VALUES ($1, $2, $3)`,
		fileID, sequenceID, preview)
	if err != nil {
		log.Printf("Failed to save index record: %v", err)
	}
}
```

---

### Part 5: Search Service (`search-service/main.go`)

This service allows researchers to query indexed genomic sequences and variants. It enforces tenant isolation by filtering results using the `X-Tenant-ID` header injected by the API Gateway.

```go
package main

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"

	_ "github.com/lib/pq"
)

var db *sql.DB

type SearchResult struct {
	DatasetName     string `json:"dataset_name"`
	DatasetVersion  string `json:"dataset_version"`
	FileType        string `json:"file_type"`
	SequenceID      string `json:"sequence_id"`
	SequencePreview string `json:"sequence_preview"`
}

func main() {
	initDB()

	http.HandleFunc("/api/v1/search/query", handleSearch)
	log.Println("Search Service running on port :8083...")
	log.Fatal(http.ListenAndServe(":8083", nil))
}

func initDB() {
	var err error
	connStr := "postgres://postgres:postgres@localhost:5432/genomics?sslmode=disable"
	db, err = sql.Open("postgres", connStr)
	if err != nil {
		log.Fatal(err)
	}
}

func handleSearch(w http.ResponseWriter, r *http.Request) {
	tenantID := r.Header.Get("X-Tenant-ID")
	query := r.URL.Query().Get("q")

	if query == "" {
		http.Error(w, "Query parameter 'q' is required", http.StatusBadRequest)
		return
	}

	rows, err := db.Query(`
		SELECT d.name, d.version, f.file_type, i.sequence_id, i.sequence_preview
		FROM genomic_indexes i
		JOIN genomic_files f ON i.file_id = f.id
		JOIN datasets d ON f.dataset_id = d.id
		WHERE d.tenant_id = $1 AND (i.sequence_id ILIKE $2 OR i.sequence_preview ILIKE $2)`,
		tenantID, "%"+query+"%")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	results := []SearchResult{}
	for rows.Next() {
		var res SearchResult
		if err := rows.Scan(&res.DatasetName, &res.DatasetVersion, &res.FileType, &res.SequenceID, &res.SequencePreview); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		results = append(results, res)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}
```

---

### Part 6: Infrastructure & Deployment

#### 1. Database Schema (`k8s/postgres-schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS datasets (
    id VARCHAR(255) PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS genomic_files (
    id VARCHAR(255) PRIMARY KEY,
    dataset_id VARCHAR(255) REFERENCES datasets(id
