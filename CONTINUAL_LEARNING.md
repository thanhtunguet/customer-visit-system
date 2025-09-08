# Continual Learning for Face Recognition System (Centralized)

## Overview

This document outlines a comprehensive continual learning strategy to improve the accuracy and robustness of the face recognition system over time. Continual learning runs centrally in the API/backend cluster; workers never train or fine‑tune models. Workers only perform on‑device inference and periodically fetch approved model artifacts from the centralized model registry.

## Current System Architecture

### Face Recognition Pipeline (Runtime on Worker)
1. **YuNet Detection** → 5-point landmarks → Face alignment (112x112)
2. **InsightFace ArcFace** → 512D embeddings → L2 normalization
3. **Milvus Vector Search (central API)** → Cosine similarity → Threshold matching (0.8 staff)

### Key Components
- **Models**: YuNet (detection) + InsightFace ArcFace (embedding)
- **Storage**: Milvus (embeddings), PostgreSQL (metadata), MinIO (images + model artifacts)
- **Thresholds**: 0.7 detection confidence, 0.8 staff matching
- **Fallback**: Mock embedder with DCT/histogram features (for tests)
- **Model Registry**: Central registry manages versions, assignments, rollout; workers fetch signed artifacts.

## Continual Learning Strategy

### 1. Data Collection & Feedback Loop (Centralized)

#### 1.1 Verification Feedback System
```
Database Schema Additions:
- recognition_feedback (id, visit_id, staff_id, feedback_type, confidence, created_at)
- staff_face_verifications (id, staff_id, image_path, verified_by, quality_score, created_at)
- model_performance_metrics (date, accuracy, precision, recall, f1_score, model_version)
```

#### 1.2 Feedback Collection Methods
- **Admin Verification Interface**: Manual confirmation/correction of identifications
- **Staff Self-Verification**: Mobile/web app for staff to confirm/deny identifications
- **Automatic Quality Assessment**: Confidence scores, alignment quality, image clarity
- **Time-based Validation**: Correlate identifications with staff schedules/location

#### 1.3 Data Quality Metrics
```python
Quality Indicators:
- Face alignment score (landmark quality)
- Image sharpness (Laplacian variance)
- Illumination consistency (histogram analysis)
- Pose angle (facial landmark geometry)
- Resolution adequacy (face pixel count)
```

### 2. Model Improvement Strategies (Centralized Jobs)

#### 2.1 Embedding Enhancement
```python
Approaches:
1. Fine-tuning ArcFace on collected staff faces
2. Domain adaptation for specific lighting/camera conditions  
3. Multi-scale embedding fusion
4. Temporal consistency modeling (same person across visits)
```

#### 2.2 Dynamic Threshold Optimization
```python
Threshold Adaptation:
- Per-staff adaptive thresholds based on historical accuracy
- Time-of-day/lighting condition adjustments
- Camera-specific threshold calibration
- Confidence distribution analysis for optimal cutoffs
```

#### 2.3 Hard Negative Mining
```python
Hard Negative Collection:
- False positive identifications (wrong person matched)
- Near-miss cases (high similarity, different person)
- Challenging lighting/pose scenarios
- Cross-camera appearance variations
```

### 3. Implementation Architecture (Centralized Learning + Model Distribution)

#### 3.1 Learning Pipeline Components

```python
# Core Learning Service (runs in API/backoffice service or CronJobs)
class ContinualLearningService:
    def __init__(self):
        self.feedback_collector = FeedbackCollector()
        self.quality_assessor = QualityAssessor()
        self.threshold_manager = AdaptiveThresholdManager()
        self.trainer = OfflineTrainer()  # offline fine-tuning job
        self.registry = ModelRegistry()
        self.performance_monitor = PerformanceMonitor()

    async def process_feedback(self, feedback: RecognitionFeedback):
        # Collect and validate feedback centrally
        # Update quality metrics and hard negative queues
        # Feed threshold manager for per-staff/camera updates

    async def retrain_offline(self, tenant_id: UUID):
        # Prepare curated, verified datasets per tenant
        # Launch offline training job (K8s CronJob/Job)
        # Validate against holdout; register new version on success
        # Publish model manifest to MinIO and Registry

    async def rollout(self, assignment: ModelAssignment):
        # Update registry targets (tenant/site/camera)
        # Workers pick up new version on next heartbeat or poll
```

#### 3.2 Database Extensions (RLS + Registry)
```sql
-- Recognition feedback tracking
CREATE TABLE recognition_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    visit_id UUID REFERENCES visits(id),
    staff_id UUID REFERENCES staff(id),
    predicted_staff_id UUID REFERENCES staff(id),
    feedback_type VARCHAR(20) CHECK (feedback_type IN ('correct', 'incorrect', 'uncertain')),
    confidence_score FLOAT,
    image_quality_score FLOAT,
    feedback_source VARCHAR(20) CHECK (feedback_source IN ('admin', 'staff', 'system')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID
);

ALTER TABLE recognition_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY recognition_feedback_isolation ON recognition_feedback
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Model performance tracking
CREATE TABLE model_performance_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    model_version VARCHAR(50),
    evaluation_date DATE,
    accuracy FLOAT,
    precision FLOAT,
    recall FLOAT,
    f1_score FLOAT,
    total_samples INTEGER,
    evaluation_type VARCHAR(20) CHECK (evaluation_type IN ('daily', 'weekly', 'deployment')),
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE model_performance_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY model_performance_logs_isolation ON model_performance_logs
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Staff face training data
-- Unify with Enhanced DB: staff_face_images
-- Extend staff_face_images with verification/quality without duplicating embeddings
ALTER TABLE staff_face_images
    ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20) DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS quality_score FLOAT,
    ADD COLUMN IF NOT EXISTS alignment_score FLOAT,
    ADD COLUMN IF NOT EXISTS training_weight FLOAT DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS verified_by UUID,
    ADD COLUMN IF NOT EXISTS milvus_vector_id TEXT,
    ADD COLUMN IF NOT EXISTS milvus_partition TEXT;

ALTER TABLE staff_face_images ENABLE ROW LEVEL SECURITY;
CREATE POLICY staff_face_images_isolation ON staff_face_images
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

-- Model registry and assignments (centralized distribution)
CREATE TABLE model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,            -- e.g., arcface-yunet
    version TEXT NOT NULL,         -- semver
    artifact_path TEXT NOT NULL,   -- MinIO path
    checksum TEXT NOT NULL,        -- SHA256
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    notes TEXT
);

ALTER TABLE model_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY model_versions_isolation ON model_versions
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

CREATE TABLE model_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    site_id UUID REFERENCES sites(id),
    camera_id UUID REFERENCES cameras(id),
    model_version_id UUID NOT NULL REFERENCES model_versions(id),
    rollout_strategy TEXT DEFAULT 'immediate',  -- immediate|canary|percent
    percent INTEGER DEFAULT 100 CHECK (percent BETWEEN 1 AND 100),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID
);

ALTER TABLE model_assignments ENABLE ROW LEVEL SECURITY;
CREATE POLICY model_assignments_isolation ON model_assignments
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

#### 3.3 API Endpoints (Centralized Learning + Distribution)
```python
# Feedback collection endpoints
POST /v1/learning/feedback
GET  /v1/learning/feedback/{visit_id}
POST /v1/learning/verify-staff/{staff_id}

# Model management endpoints
GET  /v1/learning/performance
POST /v1/learning/retrain
GET  /v1/learning/model-versions
POST /v1/learning/deploy-model/{version}

# Model distribution to workers (read-only for workers)
GET  /v1/learning/model/assignment?site_id=&camera_id=    # returns manifest
GET  /v1/learning/model/artifact/{version}                # presigned URL
POST /v1/learning/worker/heartbeat                        # reports current model + capabilities

# Analytics endpoints
GET  /v1/learning/accuracy-trends
GET  /v1/learning/challenging-cases
GET  /v1/learning/improvement-opportunities
```

### 4. Learning Algorithms (Run Centrally)

#### 4.1 Incremental Fine-tuning
```python
class OfflineTrainer:
    def __init__(self, base_model: InsightFaceEmbedder):
        self.base_model = base_model
        self.learning_rate = 0.0001
        self.batch_size = 32

    async def fine_tune(self, training_data: List[FaceTrainingData]):
        # Prepare curated, verified faces (central store)
        # Train in a centralized job (optionally GPU)
        # Validate on hold-out set per tenant
        # Emit model artifact + manifest
        return ModelArtifact(...)

    async def update_prototypes(self, staff_id: UUID, new_embeddings: np.ndarray):
        # Compute per-staff centroid/medoid centrally
        # Upsert prototype vectors to Milvus (by staff_face_image_id)
        return True
```

#### 4.2 Adaptive Threshold Learning
```python
class AdaptiveThresholdManager:
    def __init__(self):
        self.staff_thresholds = {}
        self.camera_adjustments = {}
        self.time_adjustments = {}
    
    def compute_optimal_threshold(self, staff_id: UUID, historical_data: List[MatchResult]):
        # Analyze false positive/negative rates
        # Compute ROC curve and optimal threshold
        # Consider temporal patterns and camera variations
        return optimal_threshold
    
    def get_dynamic_threshold(self, staff_id: UUID, camera_id: UUID, timestamp: datetime):
        base_threshold = self.staff_thresholds.get(staff_id, 0.8)
        camera_adj = self.camera_adjustments.get(camera_id, 0.0)
        time_adj = self.get_time_adjustment(timestamp)
        return base_threshold + camera_adj + time_adj
```

#### 4.3 Quality Assessment
```python
class QualityAssessor:
    def assess_face_quality(self, image: np.ndarray, landmarks: np.ndarray) -> float:
        scores = []
        
        # Sharpness (Laplacian variance)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        scores.append(min(sharpness / 100.0, 1.0))
        
        # Alignment quality (landmark stability)
        if landmarks is not None:
            alignment_score = self.compute_alignment_score(landmarks)
            scores.append(alignment_score)
        
        # Face resolution
        face_area = image.shape[0] * image.shape[1]
        resolution_score = min(face_area / (112 * 112), 1.0)
        scores.append(resolution_score)
        
        # Illumination consistency
        illumination_score = self.assess_illumination(image)
        scores.append(illumination_score)
        
        return np.mean(scores)
```

### 5. Deployment Strategy (Central Registry → Workers)

#### 5.1 Model Versioning
```python
Model Management:
- Semantic versioning (v1.0.0, v1.1.0, v2.0.0)
- Central Model Registry (Postgres) with immutable MinIO artifacts
- A/B and canary rollouts via model_assignments (tenant/site/camera)
- Rollback via pointer switch; workers poll and fetch signed URLs
- Worker caches model locally; verifies checksum before activation
```

#### 5.2 Performance Monitoring
```python
Metrics Collection:
- Real-time accuracy tracking per camera/site
- Daily/weekly performance reports
- Alerting for accuracy degradation
- Comparative analysis across model versions
- Prometheus: face_recog_accuracy, fp_rate, fn_rate, threshold_value, model_version_active
```

#### 5.3 Update Frequency
```
Schedule:
- Daily: Threshold adjustments, feedback collection
- Weekly: Incremental embedding updates
- Monthly: Major model retraining
- On-demand: Critical accuracy issues
```

### 6. Privacy & Security Considerations

#### 6.1 Data Privacy
- **Consent Management**: Clear consent for using face data in learning
- **Data Retention**: Configurable retention periods for training data
- **Anonymization**: Remove identifying metadata from training samples
- **Access Controls**: Restrict learning data access to authorized personnel

#### 6.2 Model Security
- **Model Encryption**: Encrypt model artifacts at rest and in transit
- **Version Control**: Cryptographic signatures for model integrity
- **Audit Logging**: Track all model updates and deployments
- **Rollback Security**: Secure rollback mechanisms with validation
- **RLS Enforcement**: All new tables include tenant-scoped RLS policies

### 7. Implementation Phases (Reordered for Centralized CL)

#### Phase 1: Feedback & Quality (Week 1-2)
- [ ] Implement recognition_feedback endpoints (central)
- [ ] Extend staff_face_images with verification/quality fields
- [ ] Admin verification UI in web
- [ ] Worker sends quality metrics; API stores centrally

#### Phase 2: Quality Assessment (Week 3-4)
- [ ] Implement QualityAssessor centrally
- [ ] Curate verified training sets per tenant
- [ ] Performance monitoring dashboard

#### Phase 3: Adaptive Thresholds (Week 5-6)
- [ ] Implement AdaptiveThresholdManager (central)
- [ ] Historical analysis; per-staff/camera thresholds
- [ ] Deploy dynamic thresholds via API (workers unaffected)

#### Phase 4: Offline Model Updates (Week 7-8)
- [ ] Implement OfflineTrainer jobs (CronJob)
- [ ] Model registry + artifact management in MinIO
- [ ] A/B + canary rollout via assignments
- [ ] Automated retraining pipeline

#### Phase 5: Production Optimization (Week 9-10)
- [ ] Performance optimization and monitoring
- [ ] Advanced centralized learning (ensembles)
- [ ] Comprehensive testing and validation
- [ ] Documentation and operational runbooks

### 8. Success Metrics

#### 8.1 Accuracy Improvements
- **Target**: 5% improvement in recognition accuracy within 3 months
- **Measurement**: Daily accuracy tracking with statistical significance testing
- **Baseline**: Current system performance across all tenants

#### 8.2 False Positive/Negative Reduction
- **Target**: 50% reduction in false positives, 30% in false negatives
- **Measurement**: Weekly FP/FN rate analysis per camera and site
- **Thresholds**: Adaptive optimization targeting 1% FPR, 5% FNR

#### 8.3 User Satisfaction
- **Target**: 90% staff satisfaction with recognition accuracy
- **Measurement**: Monthly surveys and feedback collection
- **Quality**: Response time <500ms, availability >99.9%

### 9. Risk Mitigation

#### 9.1 Model Degradation
- **Risk**: New model versions performing worse than baseline
- **Mitigation**: Comprehensive testing, gradual rollouts, automatic rollback
- **Monitoring**: Real-time performance tracking with alerts

#### 9.2 Data Quality Issues
- **Risk**: Poor quality training data degrading model performance
- **Mitigation**: Multi-layer quality assessment, human verification loop
- **Validation**: Quality score thresholds and manual review process

#### 9.3 Privacy Concerns
- **Risk**: Unauthorized use of biometric data for learning
- **Mitigation**: Explicit consent, data minimization, audit trails
- **Compliance**: GDPR/CCPA compliance with data subject rights

### 10. Future Enhancements

#### 10.1 Advanced Learning Techniques
- **Federated Learning**: Multi-tenant learning without data sharing
- **Meta-Learning**: Few-shot learning for new staff members
- **Adversarial Training**: Robustness against adversarial attacks
- **Multi-modal Fusion**: Combining face, gait, and other biometrics

#### 10.2 Operational Intelligence
- **Predictive Analytics**: Predict recognition accuracy degradation
- **Anomaly Detection**: Identify unusual patterns in recognition data
- **Capacity Planning**: Optimize computing resources for learning workloads
- **Cost Optimization**: Balance accuracy improvements with computational costs

## Conclusion

This continual learning strategy provides a comprehensive framework for improving face recognition accuracy through systematic feedback collection, quality assessment, and adaptive model updates. The phased implementation approach ensures gradual rollout with risk mitigation, while the focus on privacy and security maintains compliance with biometric data regulations.

The success of this system depends on consistent feedback collection, robust quality assessment, and careful monitoring of model performance. By implementing these strategies, the face recognition system will continuously improve its accuracy and adapt to changing conditions in real-world deployment scenarios.
