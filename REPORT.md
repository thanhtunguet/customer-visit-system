
# **Project Plan: Multi‑Tenant Face Recognition Platform for Retail**

## **1. System Architecture**

**Multi-Tenant SaaS Design:** Leverage a _shared database, shared schema_ model for multi-tenancy, using a single PostgreSQL instance with tenant-aware row isolation . Each table includes a tenant_id to scope data , and we enforce row-level security (RLS) policies so queries automatically filter by the requesting tenant . This approach is cost-efficient and simple for ~50 tenants, while still providing logical data isolation . Tenant context is passed in API calls (e.g. via JWT claims or headers) and validated on each request . This ensures one chain’s data is never exposed to another, preventing cross-tenant leaks by design . (If stricter isolation or >100 tenants were needed, we could consider separate schemas or databases per tenant , but that isn’t necessary at our scale.)

  

**Microservices Layout:** The system is split into loosely coupled services for scalability and clarity:

-   **API Backend (FastAPI):** A central RESTful API that handles all business logic, database operations, and aggregation of analytics. It serves as the hub for tenants’ admin operations and for receiving recognition events from camera workers.
    
-   **Camera Worker(s):** Lightweight Python processes (containerized) running on edge devices (Mac Mini M1/M2 at each site) that connect to cameras. Each worker handles one or more camera streams, performing face detection and encoding locally. Workers send results (face embeddings and metadata) to the API for matching and storage.
    
-   **Frontend Service:** A React/TypeScript single-page app served via a lightweight web server or CDN. In on-prem deployment, we can use an Nginx or Node.js server as a static file host and reverse proxy to the FastAPI backend. This “frontend” service ensures a unified origin for API calls (simplifying CORS) and could also handle real-time WebSocket connections for live updates.
    

  

These services communicate primarily over HTTPS REST calls (e.g. workers POST recognition events to the backend). Internally, we may use a message queue (like RabbitMQ or Kafka) to buffer high-frequency events if needed, but given moderate load (max ~11 events/sec across all sites), direct API calls are sufficient initially. Each tenant’s data is logically isolated in the backend – either by RLS or by scoping queries with tenant_id filters on every request .

  

**Data Flow:** The end-to-end flow of data is as follows:

1.  **Video Ingestion:** Live video streams (RTSP or USB webcam) feed into the on-site camera workers. For each video frame (or every Nth frame to reduce load), the worker runs face **detection**. Modern CNN detectors (see Section 2) identify any faces and their bounding boxes in the frame.
    
2.  **Face Embedding:** For each detected face, the worker crops/aligns the face and computes a vector embedding using a deep model (e.g. 512-D ArcFace embedding). The worker immediately compares the face against a small local **staff list** to see if it’s an employee (using pre-enrolled staff embeddings cached in memory). This prevents counting staff as customers.
    
3.  **Event Upload:** The worker then sends a secure API request to the central backend with the face data – including the embedding vector (or an ID reference to it), a timestamp, the camera/site ID, and a snapshot image (optional). If the face was identified as staff, that flag is included.
    
4.  **Recognition & Storage:** The FastAPI backend receives the event and invokes the face **recognition pipeline** on the server side. The embedding is inserted into Milvus (vector DB) and an approximate nearest neighbor search is performed against the tenant’s existing customer vectors . If a match above threshold is found, the system links the event to an existing customer profile ID; if not, it creates a new customer profile (optionally, marked “anonymous” until augmented with personal info). The backend stores a **Visit** record in PostgreSQL (with tenant/site, timestamp, and linked customer or “new customer” ID). The raw face snapshot is written to MinIO object storage (with a path reference in the DB).
    
5.  **Analytics & Output:** The stored data can then be aggregated for analytics. The frontend or scheduled jobs query the API for reports (e.g. daily visitor count, unique visitors, repeat vs new, gender distribution) which are computed from the Visit and Customer data. Real-time alerts (like “VIP customer Jane Doe just entered Store 7”) can be pushed via WebSocket to the dashboard if needed. A high-level architecture overview can be summarized as: **Camera → Edge Worker (Detect & Embed) → Backend API (Match & Store) → Database/Analytics → Frontend UI**.
    

  

Throughout this flow, **privacy and compliance** measures are applied. Raw images are only stored temporarily (MinIO is configured to auto-delete images older than 30 days). We retain long-term only the face embeddings and textual metadata for analytics and recognition. Embeddings are considered pseudonymous data (not directly reconstructing the face), which mitigates some privacy risk, though they are still sensitive biometric data. To comply with GDPR-like principles, we ensure data minimization (only storing necessary features), purpose limitation (data used solely for improving service and analytics), and the ability to purge data on request. Each tenant’s data is isolated, and **customer profiles can be shared across tenants only if intended**. (The system can be configured such that the same individual visiting different tenant chains is recognized as one profile, since the vector search can be global across tenants. However, by default we isolate tenant searches to avoid unintended data sharing. This is adjustable via Milvus partitions if a unified customer ID is required across all tenants – see Section 3.)

  

Finally, since the deployment is on-premises, all components run in a private network environment for security. A centralized Linux server at headquarters runs the core backend, DB, and storage services (possibly containerized on Kubernetes), and each store site runs its own Mac-Mini-based worker. This hybrid edge-cloud model reduces bandwidth usage (video processing occurs on-site) and keeps personal data largely within the company’s network.

  

## **2. Face Recognition Pipeline**

  

**Face Detection:** For robust face recognition, accurate detection is the critical first step (garbage-in, garbage-out). We adopt state-of-the-art deep learning detectors to locate faces in each camera frame. Two recommended options are:

-   **RetinaFace:** A highly accurate multi-task CNN that detects faces with pixel-level precision and even finds facial landmarks. RetinaFace is regarded as one of the most accurate open-source face detectors , excelling at finding even small or angled faces. It uses a ResNet backbone (~27 million parameters) and can detect faces at various scales with high recall. In our context, RetinaFace ensures we don’t miss customers (even if partially occluded or at a distance), reducing false negatives. The trade-off is that it’s computationally heavier – on CPU-only edge devices it may be slower (~5-10 FPS on an M1) and might introduce latency .
    
-   **YuNet (OpenCV):** A lightweight face detector optimized for edge performance. YuNet’s model has only ~75k parameters versus RetinaFace’s 27M , allowing it to run in real time on modest hardware. It’s available via OpenCV’s deep learning API as an ONNX model . YuNet sacrifices some accuracy (especially on very small or heavily occluded faces) but can achieve higher FPS. In testing, YuNet can miss some tiny or partial faces that RetinaFace would catch, but it still reliably detects frontal faces and moderate profiles . Given our use (store entrances where faces will be relatively close and frontal), YuNet could provide a good speed/accuracy balance. **Recommendation:** Use RetinaFace on sites that can support a GPU or for critical accuracy needs, and YuNet or a similarly efficient model on CPU-bound edge devices for real-time processing . Both can be integrated through Python (RetinaFace via insightface or retinaface libraries, YuNet via OpenCV). We will also set an appropriate confidence threshold and apply non-max suppression to avoid false positives (ensuring precision remains high ).
    

  

Additionally, we incorporate basic **tracking** to improve efficiency: if the same face is continuously seen in a video, the worker can skip re-running detection on every single frame. Lightweight trackers (like SORT or byte-track) can follow a detected face for a short duration, and we only re-run face recognition when a new face appears or a tracked face re-enters after leaving frame. This prevents duplicate counts and reduces compute load.

  

**Face Alignment:** Before embedding, detected face crops are aligned (rotated/scaled) based on eye or landmark positions. Alignment improves recognition accuracy by normalizing pose. Libraries like InsightFace provide alignment functions, or we can use dlib’s 5-point landmark model to align eyes horizontally. This step is lightweight and runs on CPU.

  

**Face Embedding Extraction:** For each aligned face, the system computes a fixed-length feature vector (“embedding”) that represents the face’s identity. We use modern deep networks trained on large face datasets for this. Recommended options:

-   **InsightFace (ArcFace model):** The InsightFace library provides state-of-the-art face recognition models (ArcFace, CosFace, etc.) with pre-trained weights. ArcFace, in particular, achieves very high accuracy by using an additive angular margin loss for training, producing highly discriminative embeddings . A popular model is a ResNet100 or ResNet50 backbone producing a 512-D embedding. Developers find InsightFace’s models both high-accuracy and easy to use; in one case, using an InsightFace ResNet50 model with face alignment yielded excellent results for re-identification . We favor an open-source model like ArcFace (ResNet100) trained on MS1M or Glint360K dataset, which can reach ~99.8% on LFW benchmark – providing reliable recognition of repeat customers. The embedding dimensionality is typically 512, which balances detail with manageable vector size .
    
-   **FaceNet (InceptionResNet):** An alternative is FaceNet, which uses an Inception-ResNet v1 model to produce 128-D embeddings. FaceNet (trained with triplet loss on 2015-era data) is slightly older but still performs well and has efficient implementations (e.g. the facenet-pytorch library). For example, a project used InceptionResnetV1 (VGGFace2 pretrained) to generate embeddings and found it effective . FaceNet’s 128-D vectors are smaller, meaning faster similarity searches, though potentially a bit less discriminative than ArcFace’s 512-D. In practice, both InsightFace (ArcFace) and FaceNet have been deployed successfully , and the difference in accuracy at our scale might be marginal. We lean towards ArcFace for slightly better accuracy on difficult cases (it introduced an angular margin that makes features more separable ).
    

  

Both options are available under permissive licenses and can run on CPU (with vectorized operations) or leverage Apple’s Neural Engine/GPU via ONNX Runtime or CoreML for acceleration. We prefer open-source to avoid per-request costs and to keep data on-prem, but we will also consider commercial APIs in our analysis.

  

**Commercial Face Recognition API (Optional):** Services like **AWS Rekognition**, **Azure Face API**, or **Face++** offer face detection and identification via cloud API. These can simplify implementation (pre-trained models, easy scaling) and sometimes provide additional attributes (age, emotion) out-of-the-box. However, they introduce latency (cloud round-trip) and raise privacy concerns (streaming customer faces to third-party cloud). Cost can also be significant: e.g. AWS Rekognition charges per image analyzed – which could become expensive at high volumes . One Reddit user noted AWS can “be pretty expensive if not careful” for face re-ID at scale . For instance, at 1 million images/month, costs could run into thousands of dollars monthly. Additionally, cloud APIs have usage limits and you’re dependent on internet connectivity. **Proposal:** Remain with open-source self-hosted models for real-time edge processing. We might use a commercial API in a **pilot or backup scenario** (for example, to double-check borderline cases or to get advanced attributes), but not as the primary pipeline. If we did, Azure Face or Rekognition could be evaluated for accuracy vs. our models, and a cost analysis would be done (likely proving on-prem is more economical given ~1M daily events).

  

**Vector Database (Milvus) for Embeddings:** Extracted face embeddings are sent to the central server and stored in Milvus, a specialized vector database ideal for similarity search on high-dimensional data. Milvus indexes these vectors and supports fast approximate nearest neighbor (ANN) queries, which is crucial for real-time identification . Each embedding vector (128-D or 512-D) is stored along with metadata: we include at least a unique ID, tenant_id, and person_id (if the face has been identified as a known customer) . We may also store attributes like gender or site in metadata for filtered searches (e.g. restrict search to the same city or tenant for performance and privacy). When a new embedding comes in, we perform a similarity search in Milvus to find the nearest stored vectors (using cosine similarity or Euclidean distance as the metric ). Milvus uses ANN algorithms (like HNSW or IVF) to handle large volumes quickly, trading a tiny bit of accuracy for significant speed gains . Given our scale (potentially millions of embeddings across all tenants), this is essential for sub-second response.

  

**Milvus Schema & Multi-Tenancy:** We have two design options for tenant isolation in Milvus:

-   Use a **separate collection per tenant**, each containing that tenant’s customer embeddings. This provides strong isolation and simplifies per-tenant indexing (Milvus can handle tens of thousands of collections ). A query for a given tenant simply goes to their collection. However, if we want to identify a customer across tenants, we’d have to search multiple collections.
    
-   Use a **single collection with a partition for each tenant**, leveraging Milvus’s partition-level multi-tenancy (up to 1024 partitions in one collection) . Each embedding gets a tenant_id tag and is inserted into that tenant’s partition. We then query within that partition for normal ops. This allows optional cross-tenant searches by querying multiple partitions if needed. Given we have at most ~50 tenants, partitioning is convenient and efficient. We’ll implement it such that by default each query is constrained to the relevant tenant partition (enforcing isolation), but the system admin could perform a global search if cross-tenant profile sharing is enabled. Milvus supports attaching scalar metadata to vectors and filtering in queries, so we can also enforce tenant_id in the search criteria (even without formal partitions) .
    

  

We will design the Milvus collection with dimension = 512 (for ArcFace) or 128 (for FaceNet) and use an index type suitable for our data size – likely IVF_FLAT or IVF_SQ8 (inverted file with optional quantization) for good balance of recall and memory. As data grows, we can adjust nlist (clusters) to keep search latency low (< 50 ms typically). Insertion of vectors is very fast (Milvus can handle high write rates), and we will periodically run index build/optimizations offline if needed (Milvus 2.x can handle dynamic data well with IVF).

  

**Identification Logic:** When a new face vector comes in, the backend searches Milvus and gets the top-N nearest neighbors and their similarity scores. We then apply a **confidence threshold** to decide match vs new. For example, using ArcFace embeddings (L2 normalized vectors), a cosine similarity above ~0.5 might indicate the same person . In fact, in one InsightFace model (Buffalo_L), experiments found that cosine > 0.52 virtually eliminated false positives . We will calibrate this threshold on validation data (perhaps using some collected faces of known individuals) to target <1% false accept rate while maintaining high true match rate. If the top match exceeds the threshold, we consider it a known customer: we retrieve that person’s profile (via person_id from the metadata or a quick DB lookup) and record the visit under that ID. If no match is confident, we create a new customer record and store this embedding as their reference.

  

To continuously improve accuracy, we’ll use **embedding update strategies**: Each time we encounter a returning person, we can enrich their stored representation. Rather than keeping only the first seen embedding, we store multiple embeddings per person over time (or maintain an updated centroid). For example, using multiple images of the same person and averaging their embedding vectors yields a more robust reference . We can implement this by storing a person’s last N embeddings in Milvus (tagged with person_id) and optionally averaging them when performing comparisons. The aforementioned approach of averaging 3+ images improved accuracy and removed noise in tests . We will also monitor for drift – if a person’s newer embeddings start diverging (due to hairstyle change, aging, etc.), our system could either update their profile vector or keep a diverse gallery of vectors for them to cover different appearances.

  

**Additional Model Considerations:** We will use pretrained models initially, but the architecture allows swapping in improved models as research advances (e.g. a transformer-based face recognition model or improved loss functions from 2024 papers). If needed, we could fine-tune models on our specific data (for instance, if the environment causes systematic errors like low light in some stores, fine-tuning could help, though this would require a labeled dataset which we may not readily have). We’ll also keep an eye on **face anti-spoofing (liveness)** if ever the system is used for secure access – not a current requirement, but worth noting as a potential addition.

  

In summary, the pipeline goes: **Detect → Align → Embed → Search (Milvus) → Identify/Enroll → Store Visit.** By using top-tier open-source models (RetinaFace + ArcFace/FaceNet) , we achieve high accuracy under full control. The vector database enables real-time matching at scale, and iterative improvements like multi-embedding averaging and threshold tuning will ensure we maximize accuracy (recognizing repeat customers even with slight appearance changes) while minimizing false matches.

  

## **3. Database & Storage Schema**

  

We design a relational **Entity-Relationship (ER) model** in PostgreSQL to capture tenants, locations, people, and visit events. Below are the core entities and their schema (with key fields):

-   **Tenant:** Represents a client company (a chain of stores). Fields: tenant_id (PK), name, industry, created_at, etc. (Since all tenants share the app instance, this table is small and mostly for internal management and licensing.)
    
-   **Site:** A physical location/store belonging to a tenant. Fields: site_id (PK), tenant_id (FK → Tenant), name (e.g. “Store #123, Hanoi”), address, timezone, etc. Also site_type or tags if needed. We index tenant_id here to quickly fetch all sites of a tenant.
    
-   **Camera:** Represents a camera device or stream at a site. Fields: camera_id (PK), site_id (FK → Site), name/description (e.g. “Front Entrance Cam”), rtsp_url or connection info (if needed by the UI), and status (online/offline). For privacy, we might also store a flag if this camera is enabled for face recognition or just counting. One site will have 1-5 cameras. We associate each incoming event with a camera_id to trace its source.
    
-   **Customer (Person) Profile:** Represents a unique individual (visitor) recognized by the system. Here we consider **shared profiles across tenants**: meaning if the same person visits different tenant chains, we may keep a single profile (with one ID) referenced by events in multiple tenants. Fields: person_id (PK), name, gender, birth_date, phone, email etc – personal attributes if known. Many of these might be null or empty for visitors who haven’t explicitly identified themselves (anonymous). If privacy dictates isolation, we can include tenant_id in this table to scope profiles per tenant, but since the requirement states customer profiles are shared, our design uses a global Customer table without tenant_id (i.e. person identity transcends tenants). In that case, we handle tenant-specific visibility at the application layer (tenant admins would only see those person profiles that have visited their stores, not the full global list, unless given permission).
    
-   **Staff:** Employees of the tenant, to be excluded from customer counts. Fields: staff_id (PK), tenant_id (FK), name, role, etc., and importantly a reference to their face data. We will enroll each staff member’s face by storing their embedding (either in Milvus tagged as staff or in a separate vector store) and possibly an ID photo in MinIO. Staff have their own table to manage their info. During recognition, if a face matches a staff embedding, we mark the event as staff (so it can be filtered out or logged separately). This prevents confusion of staff vs customers.
    
-   **Visit/Event:** Each time a face is detected entering a store, we log a Visit record. Fields: visit_id (PK), tenant_id, site_id, camera_id, timestamp (entry time), person_id (FK to Customer, nullable if unknown), is_staff (boolean), and embedding_id or vector reference. We also include an image_path or file ID for the snapshot stored in MinIO, and possibly a gender_estimate or age_estimate if we run on-the-fly demographic models. The Visit table will be the largest (up to ~1M rows per day in worst case globally). We partition this table by time (e.g. monthly) to keep it manageable – older partitions can be archived or dropped as needed. We also index on site_id and timestamp to efficiently query visits per store per day, etc. A composite index on (tenant_id, timestamp) helps for tenant-wide date queries. If using PG 15+, we might use logical partitioning by tenant as well, but monthly time partitioning is straightforward for roll-offs (since visits beyond retention – say 1 year – might be purged or anonymized).
    
-   **Face Embeddings (Vector Index):** We do not store raw embedding vectors in PostgreSQL (that’s Milvus’s job), but we maintain a reference mapping. For example, we can have a face_vector table with vector_id (Milvus PK), person_id, and maybe quality_score or notes. However, Milvus allows storing metadata, so we might skip a separate table and rely on Milvus as the system of record for face vectors. Each vector knows its person_id and tenant_id via metadata , and Milvus can generate its own internal IDs. For analysis or backup, we could periodically dump these or use Milvus’s persistence.
    

  

**Milvus Vector Schema:** A single collection (e.g. named “face_embeddings”) with fields: embedding (Float[512] vector), person_id (Int), tenant_id (Int), plus perhaps is_staff (Bool) or created_ts (for info). The collection dimension is 512. We enable an ANN index (like IVF) once data grows. On insertion of a new face, we add with metadata. When a person’s profile is merged (say we realize two person_ids were actually the same individual), we can update metadata or remove duplicates. Because Milvus doesn’t support in-place vector update (vectors are immutable after insert), updating a person’s “reference embedding” might mean inserting the new one and deleting the old if we choose to keep only one. However, as mentioned, we likely keep multiple vectors per person. Milvus can store millions of vectors easily; we’ll monitor index size and disk usage, but a few million 512-d vectors is on the order of a few GB, which is fine on our central server.

  

**Object Storage (MinIO) Schema:** We use MinIO (S3-compatible) to store images securely. Likely we organize buckets or prefixes by tenant and date. For example: bucket “faces-raw”, key path: {tenant_id}/{site_id}/{YYYY-MM}/{person_or_visit_id}.jpg. When a new snapshot is uploaded, it goes to the appropriate path. We enable a lifecycle policy on the bucket to automatically delete or archive objects older than 30 days (meeting the privacy requirement without manual intervention). This ensures raw images don’t persist beyond policy. For backup or audit purposes, we might also retain aggregated or blurred images, but by default deletion is permanent. The database Visit record will have the image key; after the image is purged, that reference can either be cleared or kept (pointing to nothing). We might implement a job that also nulls out image_path for visits > 30 days to avoid confusion.

  

**Indexing & Query Optimization:**

-   PostgreSQL: We add indexes on all foreign key fields (tenant_id, site_id, person_id in their respective tables). For the Visit table, an index on (tenant_id, site_id, timestamp) will help for queries like “visits per site in date range”. We also index person_id on Visit to quickly retrieve all visits of a given customer (for example, to list all times a VIP visited any store). The Customers table will have a unique index on phone or email if those are used as identifiers (to avoid duplicates if a person registers). If needed, we could use **partitioning**: e.g., partition Visit by tenant_id as well, which makes it easier to drop a tenant’s data if they leave the service, and improves query performance by eliminating partitions of other tenants. However, given only 50 tenants, we could rely on indexing + RLS for isolation and not complicate with 50 partitions. Time-based partitioning is more pressing due to volume.
    
-   Milvus: We use partitioning by tenant in the vector collection (each tenant partition can be indexed separately, which is efficient since each tenant may have far fewer vectors than the whole). We will likely use an **IVF index** with a moderate nlist (e.g. 1024) per partition and load it into memory for fast search. Milvus also allows **product quantization (PQ)** if we need to reduce memory, but at our vector size it may not be necessary initially. We will tune search parameters (nprobe for IVF, or ef for HNSW if we use that) to ensure >~95% recall of true match in top-k. Because each search is per event (which is at most a few per second per site), Milvus should handle this easily; it’s built for thousands of queries per second scale.
    

  

**ER Model Summary:** To illustrate relationships: Tenants have many Sites, Sites have many Cameras and Visits. Visits link to either a Customer or Staff (via person_id or a separate staff flag). Customers can have visits across multiple tenants (if shared global profiles), meaning a one-to-many relationship from Customer to Visit without tenant scoping. Staff are tenant-scoped and their visits (if any) are just used for filtering out. The below diagram outlines it:

```
Tenant (1) ── (∞) Site ── (∞) Camera
   │              │
   │              └─ (∞) Visit ── (∞) Customer 
   │                           └─ (∞) [Staff] 
   (Note: Staff separate, not linking to Visit directly but identified in Visit.is_staff)
```

We ensure **data retention policies** are enforced at the DB level as well. For example, we may have a scheduled job to delete Visit records (or at least the image references) older than X years if required by policy (the prompt says raw images 1 month, but embeddings can be stored long-term; we’ll keep Visit metadata indefinitely for analytics unless told to purge). Embeddings in Milvus are long-term, but if a customer opts out or requests deletion, we will remove their vectors and profile – implementing a deletion workflow that purges their data from both PG and Milvus.

  

Finally, **database tech choices**: PostgreSQL is our source of truth for structured data. It can easily handle our scale (millions of rows, moderate query load) on a single instance. We will use appropriate isolation (READ COMMITTED or REPEATABLE READ for transactions) and possibly use read replicas if analytic queries grow heavy (though initial scale doesn’t demand it). We will also utilize PostgreSQL’s JSONB columns for any semi-structured data (e.g. storing a blob of analysis results per visit like emotion scores) to keep the schema flexible without lots of join tables.

  

MinIO will run on the same server (or a storage server) with sufficient disk. Each image is a few tens of KB (if we store just the face crop at, say, 200x200 or 400x400 resolution JPEG). Even at 1 million images per month, that’s manageable in storage (with auto deletion after 30 days). We will monitor I/O and maybe separate MinIO to its own machine if needed in the future.

  

## **4. Scalability & Performance**

  

From the outset, the system is designed to scale horizontally and handle increasing load without degrading performance. Key strategies:

  

**Horizontal Scaling of Workers:** Each site deploys its own camera worker service on a Mac Mini M-series. This distributed edge computing means adding a new site (or more cameras) is as simple as provisioning another Mac Mini (or adding another worker process) – no added load on the central server for video processing. Within a site, the worker can be multi-threaded or multi-process: for example, one process per camera feed to utilize multiple CPU cores. The Mac Mini M1/M2 has 8+ CPU cores and a neural engine, so it can likely handle ~4-8 concurrent face detections per second (depending on model). If a single Mac needs to handle more cameras than it can support, we can scale horizontally by adding another Mac at that site and splitting the camera load. The design allows **multiple worker instances per tenant/site** – they register with the backend and the backend will know which worker is assigned to which camera stream. Load-balancing between workers is manual (assign cameras to specific machines), but we could automate it via a site-local orchestrator in the future.

  

Since workers operate independently, the failure or high load of one does not affect others (fault isolation). They connect to the backend statelessly – if a worker restarts, it simply resumes sending events. We may implement a simple heartbeat from workers so the server knows the camera status (and can alert if a camera or worker is down).

  

**Scaling the Backend API:** The FastAPI backend is stateless (all state in DB/Milvus), so we can run multiple instances/pods behind a load balancer. In a Kubernetes deployment, we’d use a Deployment for the API with, say, 2-4 replicas to start, and a ClusterIP Service + Ingress for load balancing. As traffic grows (e.g., many API requests from frontends or many worker event posts), the Horizontal Pod Autoscaler (HPA) can spin up more API pods. The main load on the API from workers is the vector search and DB insert per visit – both fairly quick. However, heavy analytics queries (e.g., generating a monthly report for all sites) could be offloaded to a separate reporting service or run on read replicas to keep the main API snappy. We will monitor CPU and DB connections and scale as needed. PostgreSQL itself can handle a lot of writes, but if needed, we can scale it vertically (more CPU/RAM) or use partitioning to parallelize some operations.

  

Milvus can be scaled by sharding or deploying in cluster mode (with multiple query nodes, index nodes, etc.). For our scale, a single Milvus instance (with maybe GPU acceleration if available for search) should suffice. But if vector search QPS increases, we can add additional query nodes or even partition by some key like site and run multiple Milvus instances. Milvus is designed to handle billions of vectors distributed, so we have headroom.

  

**Efficient Streaming & Frame Handling:** To maximize throughput on the edge, we optimize how camera frames are captured and processed:

-   Use hardware-accelerated decoding for RTSP streams where possible. On Mac, we can leverage the VideoToolbox API or FFmpeg’s hwaccel for H264 to offload decoding to the media engine. This frees CPU time for the face detection algorithm.
    
-   We will adjust frame rate processing: e.g., if a camera provides 30 FPS, we might only process 5 FPS for face detection. For counting entrants, we don’t need every frame – a lower sampling is often sufficient and dramatically cuts CPU usage. If someone is missed in one frame, they’ll likely be caught a fraction of a second later. We ensure the sampling interval is small enough not to miss quick walk-ins.
    
-   Implement a frame buffer with skip logic: if the face detection/recognition pipeline is still busy (e.g., the previous frame is being processed), we drop incoming frames to avoid queuing an ever-growing backlog. This keeps latency bounded. It’s better to skip frames than to lag minutes behind real time. OpenCV’s VideoCapture can sometimes buffer frames internally; we will configure it (or use an alternative like cv2.CAP_FFMPEG with proper flags) to drop older frames if reading is slow, ensuring we always get the latest frame.
    
-   Consider **motion detection** to trigger face recognition only when activity is present. A simple background subtraction or motion sensor can gate the face pipeline, reducing computations during idle times (e.g., store is open but no one is entering at 3pm, no need to run face detection on static empty frames).
    
-   For RTSP specifically, using GStreamer or FFmpeg pipelines might give more control. We could use GStreamer to split a stream – one branch for live display if needed, one for analytics. But in our simpler case, we might not need to duplicate the stream; the worker can do both (process for faces and also forward frames to UI if needed).
    

  

**Network and Throughput:** Each recognition event involves sending a small payload to the server – primarily the embedding vector (~512 floats, i.e. 2 KB) and maybe a JPEG snapshot (~10-50 KB). Even at peak (1,000 visits/day per site = ~0.7 visits/min average; burst maybe a few per minute), this is negligible bandwidth per site. 50 tenants * 20 sites = 1000 sites could in theory produce up to ~1M events/day (worst case), which is ~11.5 events/sec globally. The central server and network can handle this volume of small requests. We will ensure the API endpoint for events is efficient (e.g., use async FastAPI to handle concurrent posts, and batch DB operations if multiple events come in at once). We might also implement simple queueing on the worker: if network blips, the worker can batch a few events and send when reconnected to avoid data loss (with a max retry policy for reliability).

  

**Load Balancing & Caching:** For the frontend and API, we’ll employ load balancing via Nginx or cloud LB. The **frontend static content** can be served through a CDN or at least an Nginx reverse proxy on the server to offload that from the app. API calls will be balanced among the FastAPI instances. We also enable caching where appropriate: for instance, responses for analytics that don’t change often (like a report for last month) can be cached in memory or by a reverse proxy for subsequent requests. Within the app, using Redis to cache frequently used data (e.g., list of sites, tenant configs, or even recently seen customer names to avoid repeated DB hits) can reduce load. Example: cache the result of “get tenant settings” so that each worker heartbeat doesn’t hit the DB.

  

**Database Performance:** We anticipate high write rates to the Visit table. PostgreSQL can handle hundreds of inserts per second; to be safe, we’ll use connection pooling and possibly the COPY protocol or batch inserts if a worker sends multiple events at once. We’ll keep an eye on indexing overhead – heavy indexing on a high-write table can slow inserts, so we keep only necessary indexes and consider dropping indexes on very high-frequency logs, using aggregation tables instead. We can also periodically prune the Visit table (if we decide to not retain all raw events forever, or move older ones to a data warehouse).

  

**Milvus Performance:** Each recognition triggers a search in Milvus. With perhaps hundreds of thousands of vectors per tenant (over time), an IVF or HNSW search will take a few milliseconds in memory. Milvus can easily do >500 QPS per CPU core with appropriate indexes, so ~11 QPS aggregated is trivial. If we ever scale to tens of millions of vectors, we’ll use cluster mode with sharding, or use the fact that each tenant partition is smaller, making per-tenant search still fast. We will pre-load frequently used partitions (Milvus allows pinning certain partitions in RAM) for active tenants. If a certain tenant has very large data (millions of known customers), we allocate more memory or an isolated Milvus instance for them.

  

**Concurrency and Threading:** FastAPI with Uvicorn can handle many concurrent connections via async I/O. The main synchronous tasks might be the Milvus search (which has its own optimizations in C++) and the PostgreSQL insert. Both are quick, but if needed we can offload heavy work to background threads or Celery tasks. For example, we could immediately respond to the worker and then do the Milvus search asynchronously, but that complicates real-time identification. Instead, we keep it in-line but ensure the request cycle stays short (<100ms typically). We’ll set proper timeouts to avoid any stalled connections.

  

**Edge Caching of Profiles:** As an optimization, edge workers could maintain a cache of known frequent visitors’ embeddings for quicker local recognition. However, managing consistency of that (especially if global profiles update) is complex, and given the moderate scale, it’s fine for workers to always ask the server. One exception: staff embeddings are small in number, so the worker will load all staff faces for its site at startup and check those locally first (this is a simple dictionary of <100 faces typically, negligible memory). This saves a round trip for the common case of seeing staff multiple times a day.

  

**Testing for Performance:** We will simulate high traffic (e.g., using recorded video with many faces or generating loads of API events) to ensure the system meets the required throughput. We’ll tune buffer sizes (for video decode), batch sizes (maybe send embeddings in small batches if multiple faces detected at once), and verify that latency from face appearance to database log is within acceptable range (ideally <1 second end-to-end).

  

In summary, our architecture uses **distributed edge processing** to handle the heavy vision workload, and a scalable cloud-native backend to handle aggregated data. This separation ensures we can scale each part independently: add more edge nodes for more cameras, and scale backend instances or beef up the DB for more analytics users. Given the relatively modest scale (dozens of sites, low QPS), our solution is comfortably within capacity, but it also uses modern scalable components (Kubernetes, vector DB, stateless services) to accommodate future growth to many more tenants or higher foot-traffic with minimal refactoring.

  

## **5. Security & Privacy**

  

Security and privacy are paramount in a system handling biometric data (faces) and personal information. We implement multiple layers of controls to protect data and ensure compliance with regulations:

  

**Data Encryption:** All communications between edge workers, backend, and frontend occur over HTTPS. We’ll issue TLS certificates (via internal CA or Let’s Encrypt) for the API endpoint and ensure workers trust that cert. This prevents eavesdropping on face data in transit. Within the server, we enable encryption at rest where possible: e.g., enable PostgreSQL’s encryption (or use OS-level disk encryption) for the database files, and configure MinIO with server-side encryption for stored images. While embeddings alone are not directly identifiable, they are sensitive, so the Milvus storage directory can also reside on an encrypted volume. Access to encryption keys will be limited to the ops team.

  

**Authentication & Authorization (authN/Z):** The API will enforce authentication for all requests. Initially, access is only for internal staff (e.g., our company’s admins) and the edge workers. We’ll use a secure token-based system:

-   **Machine-to-Machine Auth:** Each camera worker will have an API key or JWT credential to authenticate when calling the backend. For instance, we might provision a JWT for each worker with a subject claiming its site ID and tenant ID, signed by our server. The backend will verify this token on each request (ensuring it’s from a valid worker and not tampered). This prevents unauthorized devices from sending fake data.
    
-   **User Auth:** For the admin frontend, we integrate an identity provider or a simple username/password login with role-based access. Internal admins might authenticate via our corporate SSO or via a secure OAuth2 flow. Each authenticated user account is tied to a tenant (or “super-admin” for our internal team). We will likely implement using FastAPI’s OAuth2PasswordBearer or JWT authentication with refresh tokens. Passwords (if any) are stored hashed with bcrypt. We also support 2FA for admin accounts if needed to add security.
    
-   **RBAC:** We define roles like **System Admin** (full access to all tenants, manage system settings), **Tenant Admin** (access to their chain’s data, manage their stores, staff, and view reports), and possibly **Site Manager** (restricted to a single site’s data). Permissions are enforced in the API endpoints, often by filtering by tenant_id as described in multi-tenancy. For example, even if a Tenant Admin tries to query a customer not in their tenant, the RLS/logic will yield no result . This prevents horizontal escalation. In code, we’ll have decorators or dependencies that verify the user’s role and scope for each request. All admin UI actions will be authorized accordingly. Since initially the only users are our internal staff (with system admin role), we might keep it simple, but the framework for RBAC will be in place when we introduce tenant-specific logins later.
    

  

**Secure API Design:** We follow REST best practices to avoid common vulnerabilities:

-   Input validation on all endpoints (using Pydantic models in FastAPI) to ensure no malicious data is processed. For instance, limit lengths on text fields (preventing buffer issues) and ensure numeric ranges make sense.
    
-   Use parameterized SQL queries (SQLAlchemy) to avoid injection. Also, because of multi-tenancy, ensure every query includes tenant scoping either via RLS or query filter – never rely on front-end to filter.
    
-   Implement rate limiting on sensitive endpoints (like login or any expensive report generation) to prevent brute force or denial of service. This can be done via a middleware using a Redis counter for example.
    
-   Return only necessary data to users – e.g., the worker API responses won’t contain any sensitive info, and tenant admins will not receive data that isn’t theirs.
    
-   We will log and monitor API access. Each request log includes the user/tenant context so we can audit who accessed what . Suspicious access patterns (like someone querying another tenant’s ID) can be flagged by analyzing these logs.
    

  

**Data Privacy & Compliance:** Our data retention and handling policies align with privacy laws:

-   **Limited Retention:** Raw face images are kept no longer than 30 days, as specified. We enforce this via MinIO lifecycle rules and an additional safety net: a daily cron job that deletes any image objects (and possibly Visit records) older than 30 days. This job will also remove any personal identifiers that are no longer needed. The face embeddings, being less personal but still biometric, are kept long-term to identify returning customers. We justify this under “legitimate interests” for customer service improvement, but we will purge embeddings too if an individual requests deletion.
    
-   **Consent and Notice:** Although this is handled outside the system operationally, the design supports compliance – e.g., if a customer opts out of face recognition, we can add their face embedding to a “do-not-track” list. That could either mean we deliberately do not store/identify their face (the worker could hash and compare to an opt-out list of embeddings and ignore them), or simply we delete their profile if they ask. The system has the capability to search by photo (embedding) to find if that person exists, so we can honor deletion requests. In practice, signage at stores will inform customers of CCTV and analytics, fulfilling notice requirements.
    
-   **Minimization & Anonymization:** We store minimal personally identifiable info (PII). By default, a customer profile is just an ID and embedding. Name, phone, etc., are only added if the business obtains them (e.g., loyalty program sign-up). For analytics reports, we typically don’t need names – counts by gender or repeat visits are aggregated and anonymized. We can generate these stats without exposing identities. If sharing any data externally (like demonstrating to a tenant), we ensure it’s aggregated (e.g., “100 females visited this week”) to avoid personal data leakage. If we ever use real images for any presentation, we would blur faces unless authorized.
    
-   **Anonymization/Pseudonymization:** Face embeddings act as pseudonymous identifiers. On their own, they are random vectors. Without our system, they can’t be easily linked to a person. We keep the mapping from embedding to identity secure in our DB. If needed, we could even encrypt embeddings (some research suggests homomorphic approaches, but that’s heavy; instead we focus on securing the environment). For additional anonymization, we might hash phone numbers and such in the DB so that if a dump occurs, raw PII isn’t plainly readable.
    

  

**Secure Storage & Access Controls:** Access to databases and servers is restricted. The Postgres and Milvus instances will require strong passwords (or certificates) and only accept connections from the application (localhost or within the Kubernetes cluster). MinIO access keys are kept secret and not exposed; the app generates pre-signed URLs for the frontend if it needs to load an image, so that we never embed raw credentials client-side. Each component’s credentials (DB password, MinIO keys, etc.) will be stored securely (like Kubernetes Secrets or an .env file on the server with proper permissions) – never hard-coded. Internally, we’ll rotate these keys periodically.

  

**Audit & Monitoring:** We will implement auditing such as:

-   Logging admin user actions (who viewed or exported customer lists, etc.), to have a trail in case of misuse.
    
-   Monitoring for unusual behavior, e.g., a sudden bulk of face data being accessed or exported. We can set up alerts if an admin account queries data outside their scope or if there are many  login failures (could indicate an attack attempt).
    
-   If using Kubernetes, enable network policies so that, for instance, the frontend pod can only talk to the API, and only the API can talk to the DB – minimizing lateral movement risk if one component is compromised.
    

  

**Physical Security:** Since deployment is on-prem, the server location and Mac Minis should be in secure premises. The Mac Minis at stores should be in a locked back office, and network communication to central likely over VPN or private lines, to avoid exposure on the open internet. We’ll likely have an IPsec or WireGuard VPN between each site and the central server, adding an extra encryption layer and also allowing using internal IPs for communication.

  

**Staff Access and Training:** Only authorized internal staff (system administrators) can access the infrastructure and databases directly. Tenant admins (future) will only see their slice via the app. We will enforce the principle of least privilege: for example, if using Kubernetes, developer accounts can’t see secret values in production; DB accounts are separated for app vs reporting (the app uses a role that can only do needed DML, not drop tables, etc., to limit impact of SQL injection).

  

**Compliance Considerations:** Our design allows compliance with GDPR-like regimes:

-   We maintain records of processing (we can document what data we collect and for what purpose).
    
-   For any individual’s data, we can fulfill access or deletion requests by querying their person profile and visits and erasing them (with a verified identity procedure out-of-band).
    
-   We avoid collecting sensitive attributes that aren’t needed. (We do collect gender as requested, which under some laws can be sensitive personal data. We either rely on self-reported gender if provided or use a crude model to guess; either way, we treat it carefully. It’s used only for aggregate analytics.)
    
-   If in the future we integrate something like emotion detection, we would do so only if there’s a clear business need, and we’d treat that data as transient (not stored long-term per individual).
    
-   We ensure third-party tools (if any) also comply – but since on-prem, we minimize third-party data processors. (If using a cloud SMS API to send an alert, make sure not to send any face data etc.)
    

  

In essence, **privacy by design** is followed: we keep data minimal (embeddings, not full images beyond 30 days), secure it heavily, and give control to the data controller (our clients) to remove data when required. Customers (the individuals) are mostly tracked anonymously unless they choose to share info. And as a final protective measure, if a particular country’s law is strict, we could even run the whole system on-prem for that client (no data leaves their premises). Our architecture is flexible to deploy in a private server environment as needed.

  

## **6. DevOps & Deployment**

  

We aim for a robust yet flexible deployment process, supporting local development (Docker Compose) and production (Kubernetes on a Linux server for central components, plus on-site installations for edge).

  

**Dockerization Strategy:** All components will be containerized for consistency across environments:

-   We will create a Dockerfile for the FastAPI backend (Python). This will use a lightweight Python base image (e.g. python:3.11-slim) and employ multi-stage build: one stage to pip install dependencies (including scientific libraries like NumPy, OpenCV, etc.), and a final stage copying in only the needed artifacts to minimize image size. We need to ensure the image includes system libs for OpenCV (ffmpeg, etc.) and perhaps libomp for some models. We’ll produce images for both amd64 (for Linux server) and arm64 (for Mac M1 workers). Using Docker Buildx, we can build multi-arch images in CI . This way, the same Docker image (just different architecture) can run on the Mac minis. Alternatively, we might choose to run the worker directly on MacOS without Docker (since Docker on Mac actually runs a Linux VM and may not have direct access to hardware acceleration). But using Docker ensures consistency; we’ll test performance to confirm it’s acceptable on Mac.
    
-   Dockerfile for the worker service: It will be similar (Python with OpenCV, InsightFace, etc.). Possibly, we combine backend and worker into one image with different start commands for simplicity, but better to separate concerns. The worker image might be larger if it includes heavy ML libraries, but since it’s built for ARM Mac, it should include appropriate wheels (TensorFlow is heavy, but we might use ONNX or PyTorch with MPS support).
    
-   Dockerfile for the frontend: We will build the React app (with Vite) into static files. Then use a simple Nginx or caddy image to serve them. The Dockerfile can use node:18-alpine to run npm build, then copy the dist/ into an nginx:alpine image. This yields a small image serving index.html and assets. We’ll configure Nginx with a fallback to index.html for client-side routing, and proxy /api/ calls to the backend (if Nginx is fronting both). In production though, we might not use Nginx for proxy if we have Kubernetes Ingress or a separate load balancer doing that.
    
-   We also containerize dependencies like Milvus and PostgreSQL for local dev in docker-compose. In production, we might run PG and Milvus as containers under Kubernetes or directly on the host (depending on what we trust for performance and persistence). Since it’s a single server for central, running DB inside K8s is possible but sometimes it’s simpler to run it as a service on the host or a VM. We’ll likely use Helm charts or manifests for Milvus (Zilliz provides a Helm chart to deploy Milvus cluster or standalone). For PG, we can use a stable chart or just use a managed approach if available on-prem (perhaps not, so likely a StatefulSet with a persistent volume).
    

  

**Local Development (Docker-Compose):** We will provide a docker-compose YAML that brings up:

-   Postgres
    
-   MinIO
    
-   Milvus (perhaps using milvus standalone docker image)
    
-   the FastAPI backend (with appropriate env vars to connect to the above)
    
-   the frontend (maybe served by the backend for simplicity in dev, or separate container)
    
-   optionally a dummy worker container that can simulate camera input (for testing end-to-end).
    

  

This lets developers run the entire stack on Mac/Linux easily for testing.

  

**Kubernetes Deployment:** For production on the central server, we use Kubernetes (likely a single-node cluster or small cluster if multiple servers are available):

-   We define a **Deployment** for the FastAPI API, with environment variables for DB connection, Milvus, etc. We attach a persistent volume (PersistentVolumeClaim) if the API service needs to write anything (though ideally it’s stateless; sessions or files should go to external storage like MinIO or DB).
    
-   A **Service** for the API (ClusterIP) and an **Ingress** (or just NodePort since on-prem) to expose it at e.g. api.mycompany.local. If we use Ingress, we can also serve the frontend through it under / and API under /api/.
    
-   Deployments (or StatefulSets) for **PostgreSQL** and **Milvus**: we’ll use a PVC for each to store data. For PG, something like 100GB volume, with scheduled backups (perhaps a cronjob that dumps SQL to MinIO daily). For Milvus, ensure a volume with sufficient IOPS (NVMe if possible, for fast vector search). Both can run as single-instance stateful services. We secure them by network policy (only API can talk to them). Alternatively, since it’s on one server, we might choose not to containerize PG/Milvus, but using K8s for them gives easier manageability and alignment with the rest of stack. There’s a slight complexity with Milvus needing etcd and perhaps pulsar/rocksmq – but the Milvus standalone docker (Milvus Lite) can simplify that (embedded metadata store). For production-grade, using the official cluster chart with etcd included is fine.
    
-   **MinIO**: either run as a container in K8s with a PV, or use an existing NAS. We’ll likely run MinIO in a StatefulSet, with a PV (say 1TB, depending on retention needs). MinIO can be accessed via a Service internally and via Ingress for UI if needed (though usage is internal only, the API will fetch images and send to UI via presigned URL).
    
-   **Frontend**: We can serve static files via an Nginx Deployment or use a Kubernetes ConfigMap volume to hold the built files served by an Nginx container. Another approach: skip container and use GitHub Pages or an internal static server. But since on-prem, simplest is to include it in cluster – e.g., an Nginx deployment serving on port 80, and Ingress routes frontend domain to it. We’ll also make sure it’s behind TLS.
    

  

For **Edge Workers**: we do not plan to run a full Kubernetes cluster on each Mac mini (especially since Macs aren’t directly supported as K8s nodes). Instead, we’ll run the worker via Docker or as a simple systemd service. Deployment to edge could be manual (SSH and run Docker container) or automated with a config management tool. We’ll supply a Docker image for the worker and a startup script that pulls the latest image from our registry and runs it with appropriate environment (pointing to central server URL, with site/camera config). Because each site has unique config (camera RTSP URLs, site_id, etc.), we might use a config file or environment variables on that site’s worker. We can manage those via Ansible or even a small central agent. For now, deployment is likely manual per site due to relatively low number of sites (20 max per tenant). We’ll create a **zsh/bash script** to setup a Mac: install Docker, pull the worker image, set it to auto-start (perhaps using launchd or a login script), so that when a Mac reboots it resumes processing.

  

**CI/CD Pipeline:** We will set up continuous integration and deployment processes:

-   **CI (Continuous Integration):** Using a platform like GitHub Actions or GitLab CI, we will automate building and testing on every commit. The pipeline will run unit tests for the FastAPI backend (using pytest), run linting (flake8, mypy for type checking), and build the Docker images for backend and worker. We’ll incorporate tests for critical components: e.g., a test that spins up a fake Milvus and ensures adding/searching an embedding works, tests for API endpoints (auth, RLS enforcement, etc.), and maybe a simulation test for the face pipeline with a known image to verify integration of detection and embedding.
    
-   We will also run frontend build and its tests (if any, like unit tests for React components) in CI.
    
-   **CD (Continuous Deployment):** On merging to main branch, CI will push Docker images to a private container registry (hosted on our server or a cloud registry if allowed). We’ll tag images version-wise (and possibly latest for development). Deployment to Kubernetes can then be done via automated means: e.g., using Argo CD (a GitOps approach) where a git repo of manifests is updated to the new image tag and Argo applies it. Or a simpler approach: use kubectl in CI to set the Deployment image tag to the new version, triggering a rolling update. Since it’s on-prem, we might schedule these updates during off-peak hours.
    
-   For edge, CD is trickier since they are not on Kubernetes. We might implement a lightweight updater: e.g., the worker could periodically check (at startup or daily) for a new Docker image tag from the registry (maybe we tag images by version and have a small API to check latest). Or simpler, we can push updates via SSH or Apple Remote Desktop when needed. Given not too many edge devices, manual or semi-automatic update is acceptable. We’ll script it to avoid human error: a script that SSHes to each Mac in an inventory list and runs docker pull new_worker_image && docker stop old && docker run new.
    
-   We’ll integrate **automated testing** into the pipeline. Beyond unit tests, we want integration tests: e.g., spin up the docker-compose in CI and run a test where a simulated worker posts an event and see if the backend records it. This ensures our whole stack works together. This can be done with GitHub Actions service containers or a kind cluster.
    

  

**Infrastructure as Code:** We’ll maintain Kubernetes manifests (or Helm charts) in version control. This includes Deployment yamls, Service, Ingress, ConfigMaps for config, Secrets (not the actual secrets but templates pulling from a secure store). That way, the environment is reproducible. For the DB and storage outside K8s, we’ll maintain setup scripts (SQL migrations for DB schema, MinIO bucket setup scripts).

  

**Auto-scaling & Resource Management:** In Kubernetes, we’ll set resource requests/limits for each pod. E.g., API pod might request 0.5 CPU and 512MB, and can scale out if needed. We can configure an HPA to add pods if CPU > 70% for 5 minutes, for instance. Similarly, if expecting variable frontend load, though likely the main load is internal usage which is predictable.

For Milvus, we’ll allocate sufficient memory for the indexes. If running cluster mode, we can scale query nodes if QPS grows.

  

**Logging & Monitoring in Deployment:** We’ll deploy a monitoring stack in K8s (like Prometheus + Grafana) to collect metrics from the API (we can use the OpenTelemetry or Prometheus client in FastAPI to export metrics like request rate, latency, etc.). We also monitor DB metrics and resource usage. Grafana dashboards will be set up for system health. Centralized logging (ELK or Loki) can aggregate logs from all pods and even from edge workers (maybe they send logs to central or we retrieve via a lightweight agent). This helps in troubleshooting issues across distributed components.

  

**Backup and Recovery:** We will schedule regular backups for Postgres (nightly dumps or WAL archiving for point-in-time recovery) and offload those backups securely (perhaps to a different storage or cloud storage if allowed, encrypted). Milvus vector data can be reconstructed from the combination of DB and backup images theoretically, but we should also consider backing up Milvus periodically (Milvus has an export function or we could save the person vectors in a backup table). MinIO images are transient (30 days), but we might still back up last 30 days images for redundancy if storage allows, or at least ensure high availability (e.g., RAID storage).

For the K8s cluster, we document deployment steps so that if the server dies, we can recreate environment on a new machine and restore DB from backup.

  

**DevOps on Edge:** We standardize the Mac Mini setup with scripts (zsh as mentioned, since Mac default shell). A script will install Homebrew, Docker, any needed libraries (if we choose to run without Docker, then Python, dlib models, etc., would be installed – but with Docker we avoid polluting host). We treat these edge devices as cattle, not pets: meaning if one fails, we can quickly commission a new one with the script, configure site ID, and be up. We do, however, monitor them – maybe via a simple Prometheus node exporter or just by the heartbeats to central.

  

In summary, our deployment pipeline emphasizes **automation and reliability**: code changes are tested and built into versioned containers, infrastructure is defined in code, and rollout can be done in a controlled manner (with the ability to roll back images if an issue is detected). This reduces downtime and ensures consistency between environments (dev, staging, prod). By containerizing all parts, we eliminate the “works on my machine” issues and ensure that whether on a developer’s laptop or on the production server, the software behaves the same.

  

## **7. Frontend UX Recommendations**

  

The frontend will be a responsive, intuitive web application (React + TypeScript) designed for internal admins initially, with the possibility of extending to tenant managers later. We prioritize clear visualization of data and ease of management for the various entities (tenants, sites, cameras, staff, customers). Here’s an outline of key UI components and UX best practices:

  

**Admin Dashboard:** Upon login, the admin lands on a dashboard providing an overview. For a system admin, this might include high-level stats across all tenants (total visits today, number of active sites, any alerts like offline cameras). For a tenant admin, the dashboard focuses on their chain: e.g., total visitors today across all their sites, current peak hour, and perhaps a leaderboard of sites by footfall. We’ll use cards and charts for quick insights. For example, show “Today: 500 visits (50 repeat, 450 new)” with an icon, or “Active Cameras: 95% online”. The design should follow Ant Design’s principles for consistency and use its grid system for responsive layout.

  

**Entity Management Pages:**

-   **Tenants:** (System admin only) A page to list all tenant organizations with key info (name, #sites, status). Admin can add a new tenant (form to input name, maybe logo), edit or disable tenants. This is mostly for our internal use; tenant admins wouldn’t see this.
    
-   **Sites:** A page per tenant listing their sites. Tenant admin or system admin can create new site (specify name, address, timezone). On each site’s detail page, show its cameras and recent stats (like visitor count today, trend vs yesterday). Allow editing site info or deleting a site (with confirmation, and perhaps requiring removal of associated cameras first to avoid orphan data).
    
-   **Cameras:** Under each site, list cameras with fields like name, type (IP camera or USB), stream URL, status (online/offline, maybe last heartbeat time). We provide controls to edit camera settings. Possibly a button “View Live Feed” that opens the stream (more on that below). For adding a camera, we input the RTSP URL and a name; we might also allow a snapshot test (attempt to fetch a frame to verify the URL).
    
-   **Staff Management:** Tenant admins can manage staff profiles. We list all staff with their photo (if available) or a silhouette icon, name, and maybe role. Options to add staff: possibly uploading a photo or taking a snapshot from a camera to enroll their face embedding. (If a camera at site can be used to capture staff face, we could integrate a “capture face” function – or simply let them upload an image file which the backend will process to extract embedding). We also allow editing staff info, and removing staff (which should also remove their embeddings from recognition so they might start being counted as customers unless re-enrolled).
    
-   **Customer (Visitor) Profiles:** This page is a bit sensitive since customers are tracked without perhaps explicit sign-up in many cases. But it could be useful for tenant marketing teams. We provide a list of known customers that have been seen, with columns: perhaps a small face thumbnail (from their last visit snapshot), an assigned ID or name if known, number of visits, first seen date, last seen date. Tenant admins could select a profile to view more details: e.g., a timeline of all their visits (which stores, when) and any profile info on file (like name/phone if linked). This helps identify VIPs or patterns (e.g., this person visits weekly on Fridays). **Important:** If profiles are global, we need to ensure one tenant admin doesn’t see another tenant’s notes on the same person. Likely, we’ll implement that tenant admins only see profiles of people who have visited their stores, and they only see visit data for their tenant. They might see that the person also visited X times elsewhere if we allow cross-tenant info, but likely we will not show that to maintain each tenant’s privacy. For now, since it’s internal-only, our staff can see global profiles.
    
-   In the customer profile view, we can allow admin to merge profiles if duplicates were created (e.g., if recognition failed to link and later they realize two IDs are same person, an admin could merge them). Also, if the customer provides consent info (like filling a form), admin can edit their details here.
    

  

**Real-Time Monitoring Dashboard:** We’ll create a section for “Live Monitoring” which can be per site (or per camera). This will be especially useful for internal staff or maybe store managers to see what’s happening right now.

-   For each camera, if feasible, display a **live video feed** or at least a refresh snapshot. We can implement live feed by using the RTSP stream converted to an HTML5-friendly format. One approach: have the edge worker or another service transcode RTSP to HLS or WebRTC. Given it’s internal, an easier method is to use an MJPEG stream or periodic JPEG refresh. For instance, the worker could push a latest frame to the server (perhaps every second) and we update an <img> tag in the UI. Or we integrate a lightweight streaming server (like running an RTSP->WebRTC gateway on the Mac and embedding a WebRTC player in the UI). If complexity/time is an issue, we start with the simpler approach: show a snapshot that updates, and highlight detections on it.
    
-   Overlay information on the video: When a face is detected in real time, we can draw a bounding box and label (e.g., “John D. – VIP” or “Returning (5th visit)”). Doing this in the UI means sending coordinates and identity data quickly. Possibly the worker can send events via WebSocket to the frontend containing detection info. The UI, which has the snapshot, can draw boxes. Alternatively, the worker could draw on the frame before sending (but that could obscure the raw image).
    
-   A list of recent events: On the monitoring page, show a scrollable list of the last N visitors detected (with time, maybe name if known or “New Customer”, and snapshot). This acts as a real-time log. We can highlight if someone is repeat (“Repeat visitor, 3rd time this week”) or VIP (if flagged).
    
-   This page could be filterable by site or camera. If a tenant admin oversees many stores, they might select one store to monitor live.
    
-   Technical implementation: We’ll likely use a WebSocket (via FastAPI’s WebSocket support) that the browser connects to. The backend (or a push service) broadcasts new visit events to clients subscribed to that tenant or site. The event carries minimal data: site, camera, maybe person_id or name, and a URL for the snapshot (we could have the worker upload the snapshot and include the URL). The frontend, upon receiving, adds it to the list and maybe updates counters.
    

  

**Reports & Analytics UI:** Using charts (Ant Design Charts or Recharts):

-   **Visitor Count Trends:** Line chart or bar chart showing number of visitors over time. We will have toggles for daily/weekly/monthly aggregation. For example, a line chart for last 30 days, or a bar chart with each day’s count. Another could be an hourly distribution (average visitors by hour of day, maybe comparing weekdays vs weekends).
    
-   **Repeat vs New:** A donut or pie chart showing the proportion of new vs returning visitors in a selected time range.
    
-   **Gender Distribution:** Since gender is tracked, a pie chart for male/female (and unknown) breakdown in a given period. This helps tenants see their customer demographics.
    
-   **Day of Week heatmap:** Perhaps a matrix 7x24 heatmap where one axis is day of week, the other hour of day, and color intensity is average footfall. This helps identify peak periods (e.g., Friday evenings are busiest).
    
-   **Site comparisons:** If tenant has multiple sites, a bar chart comparing total visits per site (with ability to filter to a date range). This can highlight top-performing stores.
    
-   We’ll include interactive filters: a date picker to select range, a dropdown to filter by site (or “All Sites”), and possibly filter by customer segment (like just staff vs customers, though staff ideally filtered out always for these).
    
-   All charts should be exportable. We can add an “Export CSV” button which downloads the raw data underlying a chart (for further analysis in Excel). For printing or presentations, an “Export PDF” or “Print” option will format the charts into a PDF report. We might use a library like jspdf or simply instruct users to use browser print to PDF, ensuring the page is print-optimized.
    

  

Using Ant Design and Tailwind CSS:

-   AntD provides ready-made components: tables, forms, modals, notifications, etc., which we’ll use for consistency and productivity.
    
-   Tailwind will help with custom styling and layout fine-tuning. For instance, spacing, colors can be adjusted via Tailwind utility classes to match branding.
    
-   We should define a clear style for status indicators (e.g., a green dot for camera online, red for offline), using AntD’s Badge or icons.
    

  

**Responsiveness and Layout:** The frontend should be usable on various screen sizes. While primary use might be on desktop, perhaps a store manager might open it on a tablet. AntD is responsive by default with its grid, but we may need to adjust some components. We ensure tables and charts resize nicely. Possibly implement different views if on a small screen (like less detail, more summary).

  

**User Experience & Flow:**

-   Provide easy navigation: a sidebar menu (AntD Menu) for sections: Dashboard, Live Monitor, Reports, Management (with sub-items for Sites, Cameras, Staff, Customers), Settings.
    
-   Use clear labels and tooltips: e.g., on charts, use tooltips to show exact numbers on hover. On forms, provide field descriptions (like what format phone number).
    
-   Validation and feedback: when adding/editing items, validate inputs (no empty required fields, proper formats) and show success messages or error feedback using AntD’s notification or message components.
    
-   Ensure that heavy actions ask for confirmation: e.g., deleting a site or camera should prompt “Are you sure? This will remove all data for that site’s visits” to avoid accidents.
    
-   Leverage AntD tables for listing entities and allow sorting/filtering within tables (like sort by last seen in customer list, or filter staff by role).
    
-   Real-time aspects: The Live Monitor page updates in real-time. Others like reports likely refresh on demand or auto-refresh every X minutes if left open. We can implement a small refresh button for user to trigger the latest data load.
    

  

**Future Multi-Tenant UI:** If/when we create a separate web app for tenant admins, we will likely reuse much of this UI but simply restrict scope (each tenant admin’s view is effectively the pieces of this interface filtered to their data). We might have a separate login page or domain for tenants. The design should consider that – maybe include tenant branding (like showing their logo when they log in) to give a personalized feel.

  

**Accessibility:** We should ensure the UI is accessible (WCAG standards) – using proper semantic HTML with our components and ensuring sufficient color contrast in charts and text. Ant Design components are generally accessible, but custom graphics we include (like on canvas for charts) should have alternative text or labels.

  

**Internationalization:** Since the project context is Vietnam (Ba Đình, Hanoi), we might eventually need multi-language (English, Vietnamese) support. We can set up the app to allow i18n from the start (using a library like react-i18next). Initially content might be English for development, but we should allow easy translation by externalizing strings.

  

**Example Scenario in UI:** A tenant admin logs in. On the dashboard, they see “Today so far: 200 visitors (20% repeat)” and a chart of the week’s trend. They click “Live Monitor”, select “Store A” and see the entrance cam feed. The feed shows 2 people in view, with a box around one labeled “Welcome back, Alice N.” because she’s recognized (maybe internally they added her name). The other face shows “New Visitor” as a label. The admin then goes to “Reports”, selects last 7 days and sees that weekends have more visitors, etc., and downloads a CSV of daily counts to share. Next, they go to “Staff” to add a new staff who joined – they upload his photo, name, and save, so he won’t be counted as customer. The UI shows a success message “Staff added, face profile registered.”

  

Overall, the UX will aim to be **enterprise-friendly**: meaning clear data presentation, not overly flashy but clean and reliable, with the power to drill down into data if needed. We’ll test the UI with sample data to ensure performance (large lists should paginate, heavy reports should load asynchronously with a spinner, etc.). Real-time aspects will be designed carefully to not overload the browser (if hundreds of events, we might auto-truncate the live list to latest 100, etc.).

  

## **8. Future Enhancements**

  

Looking beyond the initial scope, several enhancements and integrations can increase the value of the platform:

  

**Advanced ML Features:**

-   **Emotion Detection:** We could integrate an emotion recognition model on the face images to gauge customer sentiment. For example, a lightweight CNN that classifies expressions (happy, neutral, angry, etc.). This could be done at the edge or on snapshots sent to the server. The result per visit (e.g., “customer looked happy”) could feed into analytics — e.g., what percentage of customers appear satisfied. However, accuracy for emotion can be variable and there are privacy implications (inferring mood might be sensitive). Still, it could help measure customer experience (like are morning customers happier than evening ones?). We would use a pre-trained model (like one of the fer2013 models or mediaPipe face mesh combined with an emotion classifier).
    
-   **Age & Gender Estimation:** We already plan to capture gender (either via profile or model). We can add an age estimation model to approximate each visitor’s age range. Many modern face models (including some in InsightFace) can output age/gender. We could run this on each detection and store an age bracket (child, teen, adult, senior, or a number estimate). This enables reports like age distribution of visitors, or even store personalization (e.g., mostly young adults in evenings). The model could be something like SSR-Net or DEX for age, which are reasonably fast. Accuracy is ±5 years typically, so we treat it as an estimate. Gender detection from face is easier; if we don’t collect it as profile info, an automated guess can still let us group “approx male vs female count” in reports (with some error margin).
    
-   **Person Grouping / Loyalty Scoring:** We can develop a **loyalty scoring** mechanism using visit frequency. For instance, the system can assign each customer a score or tier: e.g., Gold, Silver, Bronze, based on how often they visit. A simple metric could be visits in last 30 days + visits in last 6 months, weighted. Or recency-weighted: someone who visited 10 times in last month gets high score. We can display this on their profile (like “Loyalty Level: Gold (25 visits in last 3 months)”). This could translate into actionable insights – tenants might want to target high-score visitors with rewards. We might even integrate this with their POS: e.g., if they have a loyalty program, our score might complement it for those not enrolled formally.
    
-   **Face Recognition Model Updates:** As new research comes (2024–2025 likely to see more transformer-based models or improved loss functions), we should keep our pipeline updated. For example, if a new model “AdaFace v2” comes with better handling of age progression, we could incorporate it. We might run two models in parallel (the new one for testing) and measure improved accuracy on a validation set. Also, as masks were an issue in 2020–2021, if that returns or if some customers wear masks, we could incorporate masked-face recognition models or multi-modal (face + body) recognition to maintain accuracy.
    
-   **Continuous Learning:** Possibly, fine-tune our recognition model on confirmed matches from our data (especially if we get labeled data at some point). This would adapt the model to our environment/camera specifics. This is a more distant idea since it requires a training pipeline and careful evaluation to not overfit.
    

  

**Integrations with Other Systems:**

-   **POS (Point of Sale) Integration:** By linking with the POS system of the stores, we can correlate footfall with purchases. For example, when a purchase is made and the customer uses a loyalty ID or phone number, the system could attempt to match that with a face seen entering. If matched, we can confirm that face’s identity with a profile (tying anonymous face to a known customer account). This closes the loop, allowing revenue attribution to visits and better understanding of conversion rates (how many visitors actually buy something). Technically, integration might mean our system exposes an API endpoint or a webhook for the POS. The POS could send us events like “Customer with phone X just made a purchase of $Y at store Z at time T”. We then look if at store Z around time T we saw a face that is likely that person (matching the profile we might have if they enrolled or if we have their phone from a previous link). If so, we could tag that visit as a purchase event as well. This can enrich analytics (e.g., “30% of visitors made purchases, average spend $15”).
    
-   **CRM/Marketing Integration:** For tenants with a CRM, we can feed data into it – such as visit frequency for known customers. For instance, if a customer is identified by face as a loyalty member, we can increment a field in CRM like “store visits”. Conversely, if CRM has customer segmentation, our system can import that to display VIP status on the UI. Integration could be via API or data export (e.g., nightly batch exporting list of recognized customers and their visit counts, which the CRM ingests).
    
-   **Notification Systems:** We can integrate with messaging or notification services. For example, if a VIP customer (flagged in the database) walks in, the system could send a push notification to the store manager’s phone or a message on a Slack/Telegram channel that “VIP John Doe has arrived at Store #3”. This could prompt staff to provide personalized service. Similarly, unusual events (like an excessively low customer count one day) could trigger alerts for operational awareness.
    
-   **Multi-factor Identification:** Combine face recognition with other signals. For example, if the chain has membership cards, scanning a card and matching face can double-confirm ID for high accuracy. Or integrating with entry gates (for instance, at a club or gym) to automatically open for recognized members.
    

  

**Scalability & Cost Optimizations:**

-   **Edge Device Options:** Currently using Mac Minis which are relatively high-end. In future, if scaling to hundreds of sites, cost could be optimized by using devices like NVIDIA Jetson or Intel NUCs with OpenVINO for inference. We can containerize our worker to run on ARM64 Jetsons for example (the code largely would work with minor tweaks). Jetson’s GPU could accelerate face detection. Alternatively, using an IP camera with built-in AI that can do face detection on-camera and send crops might reduce the needed compute at edge. Our platform could adapt to these input sources as well.
    
-   **Cloud vs On-Prem Hybrid:** If at some point we consider a cloud deployment (for broader SaaS offering beyond one private server), we could push heavy vector search to a managed Milvus service or use cloud GPU for recognition to scale up dynamically. Cost-wise, we’d analyze whether edge processing (cost of hardware) vs cloud processing (cost of compute on demand) is more efficient. Likely for constant video streams, owning the edge hardware is cheaper in long run, but cloud could be considered if scaling globally.
    
-   **Batch Processing for Analytics:** As data grows, on-demand calculations might strain the DB (e.g., computing a year’s worth of data ad-hoc). We might introduce a nightly batch job that computes summary tables (materialized views) for things like daily visitor count per site, etc. This is more of an optimization to ensure snappy reports for long time spans.
    
-   **Storage Pruning:** We keep embeddings indefinitely, which means growth in Milvus. If a customer hasn’t returned in, say, 5 years, that vector might not be needed. We could implement policies to archive or remove embeddings of inactive customers (perhaps after notifying or if they haven’t returned by a certain time). This frees space and keeps search faster by reducing clutter. Another approach is clustering visitors – if someone was seen once and never again, and we only care about “unique count”, maybe after some time, instead of a full vector we just keep a count. But likely, storage is not an issue at our modest scale.
    
-   **Parallelism and GPU usage:** To speed up processing at edge if needed, we could utilize GPUs. Future Mac versions or alternative hardware with discrete GPUs could allow us to run heavier models (like ArcFace ResNet100) in real-time. Also, if we ever need to reprocess historical images (for example, if we switch to a new recognition model and want to re-embed all past snapshots), we could spin up a batch pipeline on a beefy server or in cloud to do so, rather than on the small edge devices.
    

  

**New Use Cases:**

-   **Attendance/Access Control:** The core tech could be repurposed for staff attendance logging or secure access (like unlock door if face recognized). We could extend the system to handle such events, though that might be separate from customer analytics. It’s a possible product extension we keep in mind since we have the face rec pipeline ready.
    
-   **Customer Engagement:** Perhaps integrate with digital signage. Example: if a returning customer is recognized, a nearby info screen could show personalized welcome or suggestions (without naming them explicitly, unless privacy allows). This would involve quick communication from our system to that signage system.
    
-   **Shared Blacklist/Security:** Multi-tenant face recognition could be used not just for positive customer experiences but also for security (e.g., known shoplifters or banned individuals). In future, tenants might want to maintain a watchlist of certain faces. The system could then alert if a blacklisted person enters. We can incorporate a flag on profiles for “watchlist” and provide instant notifications. This must be handled carefully to avoid misidentification issues.
    

  

**Continuous Improvement with Feedback:** We will gather feedback from users and refine UI and features. For example, if tenant admins want a mobile app for quick stats, we might create a simplified mobile view or a separate mobile app that uses the same API. If they need integration with their BI tools, we might add an API to fetch raw visit data or connect directly to their data warehouse.

  

**Cost Monitoring:** Over time, we’ll track which components drive costs:

-   If the vector DB or storage grows, we might compress older data or move it to cheaper storage. For instance, older embeddings could be moved to a disk-based index rather than RAM.
    
-   Optimize cloud vs edge: maybe some sites could use a centralized processing if bandwidth is cheap and central compute is strong (though that goes against our current design, it’s a trade-off if in some scenario central GPU could process many streams and the network can carry them).
    
-   The platform can also adopt serverless ideas for certain tasks (e.g., report generation could run as an AWS Lambda function if we go cloud, scaling to demand).
    

In conclusion, the platform is built with a foundation that allows many future enhancements. We focused first on reliable face recognition and analytics, but the same infrastructure can drive richer insights (age, emotion) and deeper customer engagement (loyalty integration, personalized service). We will prioritize these enhancements based on client needs and ensure any new feature maintains our standards for privacy, accuracy, and scalability.
