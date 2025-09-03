# Visit Gallery Improvements - Detailed TODO List

## Issue 1: Face Images Not Displayed
**Problem**: Visits are not showing face images in the gallery
**Root Cause Analysis Needed**: 
- [ ] Check if image_path is being properly set in database
- [ ] Verify MinIO presigned URL generation is working
- [ ] Check if frontend is properly handling image URLs
- [ ] Investigate CORS/authentication issues for image loading

**Implementation Tasks**:
- [ ] Debug image_path population in face_service.py
- [ ] Test MinIO presigned URL generation manually
- [ ] Add proper error handling for image loading in frontend
- [ ] Implement fallback mechanism for failed image loads
- [ ] Add image loading states (skeleton/spinner)
- [ ] Verify image formats and compression are compatible

## Issue 2: Visit Deduplication/Merging Logic
**Problem**: Each face detection event creates a separate visit record, need to merge continuous appearances
**Business Rule**: If same person appears within 30 minutes, treat as one visit

**Database Changes**:
- [ ] Add visit_session_id field to visits table
- [ ] Add last_seen timestamp to visits table  
- [ ] Add visit_duration calculated field
- [ ] Create database migration for new schema changes

**Backend Logic Changes**:
- [ ] Modify face_service.py to implement visit merging logic:
  - [ ] Check for existing visits within 30-minute window
  - [ ] If found, update existing visit's last_seen timestamp
  - [ ] If not found, create new visit record
  - [ ] Update visit_duration calculation
- [ ] Add configuration for visit merge time window (30 minutes default)
- [ ] Implement visit session management:
  - [ ] Generate session IDs for continuous appearances
  - [ ] Track first_seen and last_seen for each session
  - [ ] Update confidence scores (use highest confidence in session)

**API Changes**:
- [ ] Update VisitResponse schema to include session information
- [ ] Modify visits endpoint to return merged visit data
- [ ] Add visit duration and session count to response
- [ ] Update filtering logic to work with merged visits

## Issue 3: Infinite Pagination Scroll
**Problem**: Currently loads all visits at once, need efficient pagination
**Goal**: Implement infinite scroll with proper performance

**Backend Pagination**:
- [ ] Optimize visits query with proper indexing
- [ ] Implement cursor-based pagination for better performance
- [ ] Add total count endpoint for progress indicators
- [ ] Optimize database queries with proper JOINs
- [ ] Add caching layer for frequently accessed visits

**Frontend Implementation**:
- [ ] Install react-infinite-scroll-component or similar
- [ ] Implement infinite scroll container in Visits.tsx
- [ ] Add loading states for pagination
- [ ] Implement pull-to-refresh functionality
- [ ] Add proper error handling for failed page loads
- [ ] Optimize rendering with React.memo and virtualization
- [ ] Add scroll-to-top functionality

**UX Improvements**:
- [ ] Add loading skeletons for new items
- [ ] Implement smooth scrolling transitions
- [ ] Add "Load More" button as fallback
- [ ] Show loading progress indicator
- [ ] Handle empty states and error states gracefully

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