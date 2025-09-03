# Visit Gallery Improvements - Detailed TODO List

## Issue 1: Face Images Not Displayed ✅ COMPLETED
**Problem**: Visits are not showing face images in the gallery
**Root Cause Found**: Worker was sending `snapshot_url=None` in face detection events

**Implementation Tasks**:
- [x] Debug image_path population in face_service.py - Found worker sends null URLs
- [x] Added image upload API endpoints (/v1/files/upload-url, /v1/files/download-url)
- [x] Enhanced worker with face image capture and upload functionality
- [x] Modified process_frame() to upload face crops to MinIO
- [x] Updated FaceDetectedEvent to include actual snapshot URLs
- [x] Test MinIO presigned URL generation - Working properly

## Issue 2: Visit Deduplication/Merging Logic ✅ COMPLETED
**Problem**: Each face detection event creates a separate visit record, need to merge continuous appearances
**Business Rule**: If same person appears within 30 minutes, treat as one visit

**Database Changes**:
- [x] Added visit_session_id, first_seen, last_seen, visit_duration_seconds, detection_count, highest_confidence fields
- [x] Created database migration (009_add_visit_session_fields.py)
- [x] Added indexes for efficient session queries

**Backend Logic Changes**:
- [x] Modified face_service.py _create_visit_record() method with visit merging logic:
  - [x] Check for existing visits within 30-minute window
  - [x] If found, update existing visit's last_seen timestamp, duration, detection count
  - [x] If not found, create new visit record with session ID
  - [x] Track confidence scores (use highest confidence in session)
  - [x] Update image paths to use best quality detection

**API Changes**:
- [x] Updated VisitResponse schema to include session information
- [x] Modified visits endpoint to return merged visit data with session fields
- [x] Added visit duration and detection count to response

**Frontend Changes**:
- [x] Updated Visit interface with new session fields
- [x] Enhanced visit cards to show detection count and duration
- [x] Updated modal to display session statistics and peak confidence

## Issue 3: Infinite Pagination Scroll ✅ COMPLETED
**Problem**: Currently loads all visits at once, need efficient pagination
**Goal**: Implement infinite scroll with proper performance

**Backend Pagination**:
- [x] Implemented cursor-based pagination using `last_seen` timestamp
- [x] Added VisitsPaginatedResponse schema with has_more and next_cursor
- [x] Updated visits endpoint to support cursor parameter
- [x] Reduced default limit to 50 visits per page for better performance
- [x] Optimized queries with existing database indexes

**Frontend Implementation**:
- [x] Implemented native infinite scroll with scroll event listener
- [x] Added loading states for initial load and pagination
- [x] Added proper error handling for failed page loads
- [x] Implemented cursor-based pagination state management
- [x] Added scroll detection within 200px of bottom

**UX Improvements**:
- [x] Added loading spinner for "loading more" state
- [x] Added "Load More" button as fallback option
- [x] Show progress indicator ("Scroll for more..." / "All visits loaded")
- [x] Handle empty states gracefully
- [x] Updated stats to show loaded visits count

## Testing & Quality Assurance
- [ ] Unit tests for visit merging logic
- [ ] Integration tests for pagination endpoints
- [ ] Frontend component tests for infinite scroll
- [ ] Performance testing with large datasets
- [ ] Load testing for concurrent users
- [ ] Mobile responsiveness testing
- [ ] Accessibility testing for keyboard navigation

## Documentation
- [ ] Update API documentation with new endpoints
- [ ] Document visit merging business logic
- [ ] Add troubleshooting guide for image loading issues
- [ ] Update database schema documentation
- [ ] Create performance optimization guide

## Performance Optimizations
- [ ] Add database indexes for visit queries
- [ ] Implement Redis caching for frequent queries
- [ ] Optimize image serving with CDN integration
- [ ] Add compression for API responses
- [ ] Implement lazy loading for images
- [ ] Add service worker for offline functionality

---

## Priority Levels
**P0 (Critical)**: Issues 1, 2 core functionality
**P1 (High)**: Issue 3 infinite scroll, basic testing
**P2 (Medium)**: Performance optimizations, advanced UX
**P3 (Low)**: Documentation, offline functionality

## Implementation Order
1. Fix image display (Issue 1) - immediate user value
2. Implement visit merging logic (Issue 2) - core business logic
3. Add infinite pagination (Issue 3) - performance and UX
4. Testing and polish - quality assurance