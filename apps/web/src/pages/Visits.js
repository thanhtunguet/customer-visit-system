import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, Row, Col, Select, DatePicker, Button, Typography, Space, Tag, Avatar, Empty, Spin, Modal, Checkbox, Popconfirm, App, } from 'antd';
import { UserOutlined, CalendarOutlined, ClockCircleOutlined, FilterOutlined, ReloadOutlined, CloseOutlined, DeleteOutlined, } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { CustomerFaceGallery } from '../components/CustomerFaceGallery';
const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
const seedTime = (minutesAgo) => new Date(Date.now() - 1000 * 60 * minutesAgo).toISOString();
// Seed data for visits with image paths
const SEED_VISITS = [
    {
        tenant_id: 't-dev',
        visit_id: 'v-001',
        visit_session_id: 'vs-001',
        person_id: 101,
        person_type: 'customer',
        site_id: 1,
        camera_id: 1,
        timestamp: seedTime(5),
        first_seen: seedTime(5),
        last_seen: seedTime(5),
        detection_count: 1,
        confidence_score: 0.95,
        image_path: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&h=150&fit=crop',
    },
    {
        tenant_id: 't-dev',
        visit_id: 'v-002',
        visit_session_id: 'vs-002',
        person_id: 102,
        person_type: 'customer',
        site_id: 2,
        camera_id: 2,
        timestamp: seedTime(15),
        first_seen: seedTime(15),
        last_seen: seedTime(15),
        detection_count: 1,
        confidence_score: 0.87,
        image_path: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop',
    },
    {
        tenant_id: 't-dev',
        visit_id: 'v-003',
        visit_session_id: 'vs-003',
        person_id: 201,
        person_type: 'staff',
        site_id: 1,
        camera_id: 1,
        timestamp: seedTime(30),
        first_seen: seedTime(30),
        last_seen: seedTime(30),
        detection_count: 1,
        confidence_score: 0.99,
        image_path: 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150&h=150&fit=crop',
    },
    {
        tenant_id: 't-dev',
        visit_id: 'v-004',
        visit_session_id: 'vs-004',
        person_id: 103,
        person_type: 'customer',
        site_id: 3,
        camera_id: 3,
        timestamp: seedTime(60),
        first_seen: seedTime(60),
        last_seen: seedTime(60),
        detection_count: 1,
        confidence_score: 0.92,
        image_path: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&h=150&fit=crop',
    },
    {
        tenant_id: 't-dev',
        visit_id: 'v-005',
        visit_session_id: 'vs-005',
        person_id: 104,
        person_type: 'customer',
        site_id: 1,
        camera_id: 1,
        timestamp: seedTime(120),
        first_seen: seedTime(120),
        last_seen: seedTime(120),
        detection_count: 1,
        confidence_score: 0.88,
        image_path: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=150&h=150&fit=crop',
    },
    {
        tenant_id: 't-dev',
        visit_id: 'v-006',
        visit_session_id: 'vs-006',
        person_id: 105,
        person_type: 'customer',
        site_id: 2,
        camera_id: 2,
        timestamp: seedTime(180),
        first_seen: seedTime(180),
        last_seen: seedTime(180),
        detection_count: 1,
        confidence_score: 0.91,
        image_path: 'https://images.unsplash.com/photo-1504593811423-6dd665756598?w=150&h=150&fit=crop',
    },
    {
        tenant_id: 't-dev',
        visit_id: 'v-007',
        visit_session_id: 'vs-007',
        person_id: 202,
        person_type: 'staff',
        site_id: 3,
        camera_id: 3,
        timestamp: seedTime(240),
        first_seen: seedTime(240),
        last_seen: seedTime(240),
        detection_count: 1,
        confidence_score: 0.97,
        image_path: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop',
    },
    {
        tenant_id: 't-dev',
        visit_id: 'v-008',
        visit_session_id: 'vs-008',
        person_id: 106,
        person_type: 'customer',
        site_id: 1,
        camera_id: 1,
        timestamp: seedTime(300),
        first_seen: seedTime(300),
        last_seen: seedTime(300),
        detection_count: 1,
        confidence_score: 0.85,
        image_path: 'https://images.unsplash.com/photo-1552058544-f2b08422138a?w=150&h=150&fit=crop',
    },
];
// Seed data for sites
const SEED_SITES = [
    {
        tenant_id: 't-dev',
        site_id: 1,
        name: 'Main Branch',
        created_at: new Date().toISOString(),
    },
    {
        tenant_id: 't-dev',
        site_id: 2,
        name: 'North Branch',
        created_at: new Date().toISOString(),
    },
    {
        tenant_id: 't-dev',
        site_id: 3,
        name: 'South Branch',
        created_at: new Date().toISOString(),
    },
    {
        tenant_id: 't-dev',
        site_id: 4,
        name: 'East Branch',
        created_at: new Date().toISOString(),
    },
    {
        tenant_id: 't-dev',
        site_id: 5,
        name: 'West Branch',
        created_at: new Date().toISOString(),
    },
];
export const VisitsPage = () => {
    const { message } = App.useApp();
    const [visits, setVisits] = useState([]);
    const [sites, setSites] = useState([]);
    const [selectedSites, setSelectedSites] = useState([]);
    const [dateRange, setDateRange] = useState([
        null,
        null,
    ]);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [nextCursor, setNextCursor] = useState();
    const [selectedVisit, setSelectedVisit] = useState(null);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [reassignOpen, setReassignOpen] = useState(false);
    const [reassignTarget, setReassignTarget] = useState('');
    const [reassigning, setReassigning] = useState(false);
    const [selectedVisitIds, setSelectedVisitIds] = useState(new Set());
    const [isDeleting, setIsDeleting] = useState(false);
    const [lastSelectedIndex, setLastSelectedIndex] = useState(-1);
    const [mergeOpen, setMergeOpen] = useState(false);
    const [merging, setMerging] = useState(false);
    const [primaryVisitId, setPrimaryVisitId] = useState(undefined);
    // Load initial data from API
    const loadInitialData = useCallback(async () => {
        setLoading(true);
        setVisits([]);
        setNextCursor(undefined);
        setHasMore(true);
        try {
            // Load sites and initial visits
            const [fetchedSites, visitsResponse] = await Promise.all([
                apiClient.getSites(),
                apiClient.getVisits({
                    limit: 50,
                    site_id: selectedSites.length > 0 ? selectedSites.join(',') : undefined,
                    start_time: dateRange[0] || undefined,
                    end_time: dateRange[1] || undefined,
                }),
            ]);
            setSites(fetchedSites);
            setVisits(visitsResponse.visits);
            setHasMore(visitsResponse.has_more);
            setNextCursor(visitsResponse.next_cursor);
        }
        catch (error) {
            console.error('Failed to load data:', error);
            // Fallback to seed data on error for development
            setSites(SEED_SITES);
            setVisits(SEED_VISITS);
            setHasMore(false);
        }
        finally {
            setLoading(false);
        }
    }, [selectedSites, dateRange]);
    useEffect(() => {
        loadInitialData();
    }, [loadInitialData]);
    // Load more visits for infinite scroll
    const loadMoreVisits = useCallback(async () => {
        if (!hasMore || loadingMore || !nextCursor)
            return;
        setLoadingMore(true);
        try {
            const response = await apiClient.getVisits({
                limit: 50,
                cursor: nextCursor,
                site_id: selectedSites.length > 0 ? selectedSites.join(',') : undefined,
                start_time: dateRange[0] || undefined,
                end_time: dateRange[1] || undefined,
            });
            setVisits((prev) => [...prev, ...response.visits]);
            setHasMore(response.has_more);
            setNextCursor(response.next_cursor);
        }
        catch (error) {
            console.error('Failed to load more visits:', error);
        }
        finally {
            setLoadingMore(false);
        }
    }, [hasMore, loadingMore, nextCursor, selectedSites, dateRange]);
    const handleSiteChange = (value) => {
        setSelectedSites(value);
    };
    const handleDateChange = (dates, dateStrings) => {
        setDateRange([dateStrings[0] || null, dateStrings[1] || null]);
    };
    const handleRefresh = async () => {
        await loadInitialData();
    };
    const handleClearFilters = () => {
        setSelectedSites([]);
        setDateRange([null, null]);
    };
    // Handle scroll for infinite loading
    const handleScroll = useCallback(() => {
        if (loading || loadingMore || !hasMore)
            return;
        const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
        const scrollHeight = document.documentElement.scrollHeight || document.body.scrollHeight;
        const clientHeight = document.documentElement.clientHeight || window.innerHeight;
        // Load more when user scrolls to within 200px of bottom
        if (scrollTop + clientHeight >= scrollHeight - 200) {
            loadMoreVisits();
        }
    }, [loading, loadingMore, hasMore, loadMoreVisits]);
    useEffect(() => {
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, [handleScroll]);
    const formatTimeAgo = (timestamp) => {
        const now = new Date();
        const visitTime = new Date(timestamp);
        const diffInMinutes = Math.floor((now.getTime() - visitTime.getTime()) / (1000 * 60));
        if (diffInMinutes < 1)
            return 'Just now';
        if (diffInMinutes < 60)
            return `${diffInMinutes} min ago`;
        if (diffInMinutes < 1440)
            return `${Math.floor(diffInMinutes / 60)} hr ago`;
        return `${Math.floor(diffInMinutes / 1440)} day ago`;
    };
    const getSiteName = (siteId) => {
        const site = sites.find((s) => s.site_id === siteId);
        return site ? site.name : `Site ${siteId}`;
    };
    const getPersonTypeColor = (personType) => {
        return personType === 'staff' ? 'blue' : 'green';
    };
    const handleVisitClick = async (visit) => {
        setSelectedVisit(visit);
        setIsModalVisible(true);
    };
    const handleCloseModal = () => {
        setIsModalVisible(false);
        setSelectedVisit(null);
    };
    const handleSelectVisit = (visitId, checked, event) => {
        const visitIndex = visits.findIndex((v) => v.visit_id === visitId);
        if (event && (event.shiftKey || event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            if (event.shiftKey) {
                // Range selection with Shift key
                let startIndex, endIndex;
                if (lastSelectedIndex >= 0) {
                    // Range from last selected to current
                    startIndex = Math.min(lastSelectedIndex, visitIndex);
                    endIndex = Math.max(lastSelectedIndex, visitIndex);
                }
                else {
                    // No previous selection, select from beginning to current
                    startIndex = 0;
                    endIndex = visitIndex;
                }
                setSelectedVisitIds((prev) => {
                    const newSet = new Set(prev);
                    for (let i = startIndex; i <= endIndex; i++) {
                        if (i < visits.length) {
                            newSet.add(visits[i].visit_id);
                        }
                    }
                    return newSet;
                });
                setLastSelectedIndex(visitIndex); // Update to current item
            }
            else if (event.ctrlKey || event.metaKey) {
                // Multi-selection with Ctrl/Cmd key
                setSelectedVisitIds((prev) => {
                    const newSet = new Set(prev);
                    if (newSet.has(visitId)) {
                        newSet.delete(visitId);
                    }
                    else {
                        newSet.add(visitId);
                    }
                    return newSet;
                });
                setLastSelectedIndex(visitIndex);
            }
        }
        else {
            // Regular selection (checkbox or single click)
            setSelectedVisitIds((prev) => {
                const newSet = new Set(prev);
                if (checked) {
                    newSet.add(visitId);
                }
                else {
                    newSet.delete(visitId);
                }
                return newSet;
            });
            setLastSelectedIndex(visitIndex);
        }
    };
    const handleSelectAll = useCallback((checked) => {
        if (checked) {
            setSelectedVisitIds(new Set(visits.map((v) => v.visit_id)));
            setLastSelectedIndex(visits.length - 1);
        }
        else {
            setSelectedVisitIds(new Set());
            setLastSelectedIndex(-1);
        }
    }, [visits]);
    const handleCardClick = (visit, event) => {
        // Don't trigger selection if clicking on checkbox
        if (event.target.closest('.visit-checkbox')) {
            return;
        }
        // determine index if needed
        const isCurrentlySelected = selectedVisitIds.has(visit.visit_id);
        const isInSelectionMode = selectedVisitIds.size > 0;
        if (event.shiftKey) {
            // Shift+click: Always do range selection
            event.preventDefault();
            handleSelectVisit(visit.visit_id, true, event);
        }
        else if (event.ctrlKey || event.metaKey) {
            // Ctrl/Cmd+click: Always toggle selection
            event.preventDefault();
            handleSelectVisit(visit.visit_id, !isCurrentlySelected, event);
        }
        else if (isInSelectionMode) {
            // In selection mode: Regular click toggles selection
            handleSelectVisit(visit.visit_id, !isCurrentlySelected);
        }
        else {
            // Not in selection mode: Regular click opens modal
            handleVisitClick(visit);
        }
    };
    const handleDeleteSelected = useCallback(async () => {
        if (selectedVisitIds.size === 0)
            return;
        setIsDeleting(true);
        try {
            const visitIdsArray = Array.from(selectedVisitIds);
            await apiClient.deleteVisits(visitIdsArray);
            message.success(`Successfully deleted ${visitIdsArray.length} visit(s)`);
            // Clear selections
            setSelectedVisitIds(new Set());
            // Refresh the data to recalculate pagination
            await loadInitialData();
        }
        catch (error) {
            console.error('Failed to delete visits:', error);
            message.error('Failed to delete visits. Please try again.');
        }
        finally {
            setIsDeleting(false);
        }
    }, [selectedVisitIds, loadInitialData, message]);
    const selectedVisits = useMemo(() => {
        const set = selectedVisitIds;
        return visits.filter((v) => set.has(v.visit_id));
    }, [selectedVisitIds, visits]);
    const bestPrimaryCandidateId = useMemo(() => {
        if (selectedVisits.length === 0)
            return undefined;
        const sorted = [...selectedVisits].sort((a, b) => {
            const ah = (a.highest_confidence ?? a.confidence_score) || 0;
            const bh = (b.highest_confidence ?? b.confidence_score) || 0;
            if (bh !== ah)
                return bh - ah;
            // tie-breaker: earliest first_seen
            return (new Date(a.first_seen).getTime() - new Date(b.first_seen).getTime());
        });
        return sorted[0]?.visit_id;
    }, [selectedVisits]);
    const openMergeModal = () => {
        if (selectedVisitIds.size < 2) {
            message.info('Select at least two visits to merge');
            return;
        }
        setPrimaryVisitId(bestPrimaryCandidateId);
        setMergeOpen(true);
    };
    const handleMerge = async () => {
        if (selectedVisitIds.size < 2)
            return;
        setMerging(true);
        try {
            const ids = Array.from(selectedVisitIds);
            const res = await apiClient.mergeVisits(ids, primaryVisitId);
            message.success(res.message || 'Merged visits');
            setMergeOpen(false);
            setSelectedVisitIds(new Set([res.primary_visit_id]));
            await loadInitialData();
        }
        catch (e) {
            const error = e;
            message.error(error?.response?.data?.detail || 'Failed to merge visits');
        }
        finally {
            setMerging(false);
        }
    };
    // Keyboard shortcuts - moved after handleDeleteSelected is defined
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (visits.length === 0)
                return;
            // Ctrl/Cmd + A - Select all
            if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                e.preventDefault();
                handleSelectAll(true);
            }
            // Escape - Clear selection
            if (e.key === 'Escape') {
                setSelectedVisitIds(new Set());
                setLastSelectedIndex(-1);
            }
            // Delete key - Delete selected items with confirmation
            if (e.key === 'Delete' && selectedVisitIds.size > 0) {
                e.preventDefault();
                Modal.confirm({
                    title: `Delete ${selectedVisitIds.size} visit(s)?`,
                    content: 'This action cannot be undone.',
                    okText: 'Delete',
                    cancelText: 'Cancel',
                    okButtonProps: { danger: true },
                    onOk: handleDeleteSelected,
                });
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [visits, selectedVisitIds, handleDeleteSelected, handleSelectAll]);
    return (_jsxs("div", { className: "p-6", children: [_jsxs("div", { className: "mb-6", children: [_jsx(Title, { level: 3, children: "Visit Gallery" }), _jsx(Text, { type: "secondary", children: "Browse and filter customer/staff visits across all sites" })] }), _jsx(Card, { className: "mb-6", children: _jsxs("div", { className: "flex flex-col md:flex-row md:items-center md:justify-between gap-4", children: [_jsxs(Space, { wrap: true, children: [_jsxs(Space, { children: [_jsx(FilterOutlined, {}), _jsx(Text, { strong: true, children: "Filters:" })] }), _jsx(Select, { mode: "multiple", allowClear: true, style: { minWidth: 200 }, placeholder: "Select sites", value: selectedSites, onChange: handleSiteChange, options: sites.map((site) => ({
                                        label: site.name,
                                        value: site.site_id.toString(),
                                    })) }), _jsx(RangePicker, { onChange: handleDateChange, placeholder: ['Start date', 'End date'] })] }), _jsxs(Space, { children: [_jsx(Button, { icon: _jsx(ReloadOutlined, {}), onClick: handleRefresh, loading: loading, children: "Refresh" }), _jsx(Button, { onClick: handleClearFilters, children: "Clear Filters" })] })] }) }), _jsxs(Card, { className: "mb-6", children: [_jsxs(Row, { gutter: 16, className: "mb-4", children: [_jsxs(Col, { span: 6, children: [_jsx(Text, { strong: true, children: "Loaded Visits: " }), _jsx(Text, { children: visits.length })] }), _jsxs(Col, { span: 6, children: [_jsx(Text, { strong: true, children: "Customers: " }), _jsx(Text, { children: visits.filter((v) => v.person_type === 'customer').length })] }), _jsxs(Col, { span: 6, children: [_jsx(Text, { strong: true, children: "Staff: " }), _jsx(Text, { children: visits.filter((v) => v.person_type === 'staff').length })] }), _jsx(Col, { span: 6, children: _jsx(Text, { type: "secondary", className: "text-sm", children: hasMore ? 'Scroll for more...' : 'All visits loaded' }) })] }), visits.length > 0 && (_jsxs(Row, { gutter: 16, align: "middle", children: [_jsx(Col, { children: _jsxs(Checkbox, { indeterminate: selectedVisitIds.size > 0 &&
                                        selectedVisitIds.size < visits.length, checked: visits.length > 0 && selectedVisitIds.size === visits.length, onChange: (e) => handleSelectAll(e.target.checked), children: ["Select All (", selectedVisitIds.size, " selected)"] }) }), _jsx(Col, { children: selectedVisitIds.size > 0 && (_jsx(Popconfirm, { title: `Delete ${selectedVisitIds.size} visit(s)?`, description: "This action cannot be undone.", onConfirm: handleDeleteSelected, okText: "Delete", cancelText: "Cancel", okButtonProps: { danger: true, loading: isDeleting }, children: _jsxs(Button, { danger: true, icon: _jsx(DeleteOutlined, {}), loading: isDeleting, disabled: isDeleting, children: ["Delete Selected (", selectedVisitIds.size, ")"] }) })) }), _jsx(Col, { children: _jsxs(Button, { type: "primary", disabled: selectedVisitIds.size < 2, onClick: openMergeModal, children: ["Merge Selected (", selectedVisitIds.size || 0, ")"] }) })] }))] }), _jsx("div", { children: loading ? (_jsx("div", { className: "flex justify-center items-center h-64", children: _jsx(Spin, { size: "large" }) })) : visits.length === 0 ? (_jsx(Empty, { description: "No visits found", image: Empty.PRESENTED_IMAGE_SIMPLE, children: _jsx(Button, { type: "primary", onClick: handleClearFilters, children: "Clear Filters" }) })) : (_jsxs(_Fragment, { children: [_jsx(Row, { gutter: [16, 16], children: visits.map((visit) => (_jsx(Col, { xs: 24, sm: 12, md: 8, lg: 6, children: _jsxs(Card, { size: "small", hoverable: true, className: `h-full flex flex-col shadow-sm hover:shadow-md transition-shadow relative ${selectedVisitIds.size > 0
                                        ? 'cursor-crosshair'
                                        : 'cursor-pointer'} ${selectedVisitIds.has(visit.visit_id)
                                        ? 'ring-2 ring-blue-500 bg-blue-50'
                                        : ''}`, onClick: (e) => handleCardClick(visit, e), children: [_jsx("div", { className: "visit-checkbox absolute top-2 right-2 z-10", onClick: (e) => e.stopPropagation(), children: _jsx(Checkbox, { checked: selectedVisitIds.has(visit.visit_id), onChange: (e) => handleSelectVisit(visit.visit_id, e.target.checked) }) }), _jsxs("div", { className: "flex items-center justify-between mb-2 pr-8", children: [_jsx(Tag, { color: getPersonTypeColor(visit.person_type), children: visit.person_type.charAt(0).toUpperCase() +
                                                        visit.person_type.slice(1) }), _jsx(Text, { type: "secondary", className: "text-xs", children: formatTimeAgo(visit.timestamp) })] }), _jsxs("div", { className: "flex flex-col items-center mb-3", children: [visit.image_path ? (_jsx("img", { src: visit.image_path, alt: "Captured face", className: "w-20 h-20 rounded-full object-cover border-2 border-gray-200 mb-2 cursor-pointer", onError: (e) => {
                                                        // Fallback to avatar if image fails to load
                                                        const target = e.target;
                                                        target.onerror = null;
                                                        target.style.display = 'none';
                                                        target.nextElementSibling?.removeAttribute('style');
                                                    } })) : null, _jsx(Avatar, { size: 64, icon: _jsx(UserOutlined, {}), className: "mb-2", style: visit.image_path ? { display: 'none' } : {} }), _jsx("div", { className: "text-center", children: _jsxs(Text, { strong: true, children: [visit.person_type === 'staff' ? 'Staff' : 'Customer', ' ', "#", visit.person_id] }) })] }), _jsxs("div", { className: "mt-auto", children: [_jsxs("div", { className: "flex items-center mb-1", children: [_jsx(CalendarOutlined, { className: "mr-2 text-gray-500" }), _jsx(Text, { type: "secondary", className: "text-xs", children: new Date(visit.timestamp).toLocaleDateString() })] }), _jsxs("div", { className: "flex items-center mb-1", children: [_jsx(ClockCircleOutlined, { className: "mr-2 text-gray-500" }), _jsx(Text, { type: "secondary", className: "text-xs", children: new Date(visit.timestamp).toLocaleTimeString([], {
                                                                hour: '2-digit',
                                                                minute: '2-digit',
                                                            }) })] }), _jsx("div", { className: "flex items-center mb-1", children: _jsx(Text, { type: "secondary", className: "text-xs truncate", children: getSiteName(visit.site_id) }) }), _jsx("div", { className: "mt-1", children: _jsxs(Text, { type: "secondary", className: "text-xs", children: ["Confidence:", ' ', (visit.confidence_score * 100).toFixed(1), "%"] }) }), visit.detection_count > 1 && (_jsx("div", { className: "mt-1", children: _jsxs(Text, { type: "secondary", className: "text-xs", children: [visit.detection_count, " detections"] }) })), visit.visit_duration_seconds &&
                                                    visit.visit_duration_seconds > 0 && (_jsx("div", { className: "mt-1", children: _jsxs(Text, { type: "secondary", className: "text-xs", children: ["Duration:", ' ', Math.floor(visit.visit_duration_seconds / 60), "m", ' ', visit.visit_duration_seconds % 60, "s"] }) }))] })] }) }, visit.visit_id))) }), loadingMore && (_jsxs("div", { className: "flex justify-center items-center mt-8", children: [_jsx(Spin, { size: "large" }), _jsx(Text, { className: "ml-3", children: "Loading more visits..." })] })), hasMore && !loadingMore && (_jsx("div", { className: "flex justify-center mt-8", children: _jsx(Button, { type: "default", size: "large", onClick: loadMoreVisits, icon: _jsx(ReloadOutlined, {}), children: "Load More Visits" }) }))] })) }), _jsx(Modal, { open: isModalVisible, onCancel: handleCloseModal, footer: null, width: selectedVisit?.person_type === 'customer' ? 600 : 400, closeIcon: _jsx(CloseOutlined, {}), centered: true, children: selectedVisit && (_jsxs("div", { className: "flex flex-col items-center", children: [_jsx("div", { className: "mb-4", children: selectedVisit.image_path ? (_jsx("img", { src: selectedVisit.image_path, alt: "Captured face", className: "w-32 h-32 rounded-full object-cover border-2 border-gray-200" })) : (_jsx(Avatar, { size: 128, icon: _jsx(UserOutlined, {}) })) }), _jsxs("div", { className: "w-full", children: [_jsxs("div", { className: "flex justify-between items-center mb-2", children: [_jsx(Tag, { color: getPersonTypeColor(selectedVisit.person_type), children: selectedVisit.person_type.charAt(0).toUpperCase() +
                                                selectedVisit.person_type.slice(1) }), _jsx(Text, { type: "secondary", children: formatTimeAgo(selectedVisit.timestamp) })] }), _jsxs("div", { className: "mb-3 text-center", children: [_jsxs(Text, { strong: true, className: "text-lg", children: [selectedVisit.person_type === 'staff' ? 'Staff' : 'Customer', ' ', "#", selectedVisit.person_id] }), _jsx("br", {}), _jsxs(Text, { type: "secondary", children: ["Visit ID: ", selectedVisit.visit_id] })] }), _jsxs("div", { className: "bg-gray-50 p-4 rounded-lg", children: [_jsxs("div", { className: "flex items-center mb-2", children: [_jsx(CalendarOutlined, { className: "mr-2 text-gray-500" }), _jsxs(Text, { children: [_jsx("strong", { children: "Date:" }), ' ', new Date(selectedVisit.timestamp).toLocaleDateString()] })] }), _jsxs("div", { className: "flex items-center mb-2", children: [_jsx(ClockCircleOutlined, { className: "mr-2 text-gray-500" }), _jsxs(Text, { children: [_jsx("strong", { children: "Time:" }), ' ', new Date(selectedVisit.timestamp).toLocaleTimeString([], {
                                                            hour: '2-digit',
                                                            minute: '2-digit',
                                                        })] })] }), _jsx("div", { className: "flex items-center mb-2", children: _jsxs(Text, { children: [_jsx("strong", { children: "Site:" }), " ", getSiteName(selectedVisit.site_id)] }) }), _jsx("div", { className: "flex items-center mb-2", children: _jsxs(Text, { children: [_jsx("strong", { children: "Confidence:" }), ' ', (selectedVisit.confidence_score * 100).toFixed(1), "%"] }) }), selectedVisit.detection_count > 1 && (_jsx("div", { className: "flex items-center mb-2", children: _jsxs(Text, { children: [_jsx("strong", { children: "Detections:" }), ' ', selectedVisit.detection_count] }) })), selectedVisit.visit_duration_seconds &&
                                            selectedVisit.visit_duration_seconds > 0 && (_jsx("div", { className: "flex items-center mb-2", children: _jsxs(Text, { children: [_jsx("strong", { children: "Duration:" }), ' ', Math.floor(selectedVisit.visit_duration_seconds / 60), "m", ' ', selectedVisit.visit_duration_seconds % 60, "s"] }) })), selectedVisit.highest_confidence &&
                                            selectedVisit.highest_confidence !==
                                                selectedVisit.confidence_score && (_jsx("div", { className: "flex items-center", children: _jsxs(Text, { children: [_jsx("strong", { children: "Peak Confidence:" }), ' ', (selectedVisit.highest_confidence * 100).toFixed(1), "%"] }) }))] })] }), ' ', selectedVisit.person_type === 'customer' &&
                            selectedVisit.person_id && (_jsxs("div", { className: "w-full mt-6", children: [_jsx("div", { className: "flex items-center justify-between mb-3", children: _jsxs(Space, { children: [_jsx(Button, { size: "small", onClick: () => setReassignOpen(true), children: "Reassign Visit\u2026" }), _jsx(Popconfirm, { title: "Remove this visit?", description: "Deletes the visit and associated images.", okText: "Remove", okButtonProps: { danger: true }, onConfirm: async () => {
                                                    try {
                                                        await apiClient.removeVisitFaceDetection(selectedVisit.visit_id);
                                                        message.success('Visit removed');
                                                        setIsModalVisible(false);
                                                        await loadInitialData();
                                                    }
                                                    catch (e) {
                                                        const error = e;
                                                        message.error(error.response?.data?.detail || 'Failed to remove');
                                                    }
                                                }, children: _jsx(Button, { size: "small", danger: true, children: "Remove Visit" }) })] }) }), _jsx(CustomerFaceGallery, { customerId: selectedVisit.person_id, customerName: `Customer #${selectedVisit.person_id}` })] }))] })) }), _jsx(Modal, { open: reassignOpen, onCancel: () => setReassignOpen(false), title: "Reassign Visit", okText: reassigning ? 'Reassigning…' : 'Reassign', onOk: async () => {
                    const cid = parseInt(reassignTarget, 10);
                    if (!selectedVisit || !cid)
                        return;
                    try {
                        setReassigning(true);
                        await apiClient.reassignVisit(selectedVisit.visit_id, cid, true);
                        message.success('Visit reassigned');
                        setReassignOpen(false);
                        setIsModalVisible(false);
                        setReassignTarget('');
                        await loadInitialData();
                    }
                    catch (e) {
                        const error = e;
                        message.error(error.response?.data?.detail || 'Failed to reassign visit');
                    }
                    finally {
                        setReassigning(false);
                    }
                }, children: _jsxs("div", { className: "space-y-2", children: [_jsx("div", { children: "New customer ID" }), _jsx("input", { value: reassignTarget, onChange: (e) => setReassignTarget(e.target.value), className: "w-full border rounded px-2 py-1", placeholder: "Enter customer id" })] }) }), _jsx(Modal, { open: mergeOpen, onCancel: () => setMergeOpen(false), title: `Merge ${selectedVisitIds.size} visits`, okText: merging ? 'Merging…' : 'Merge', onOk: handleMerge, confirmLoading: merging, children: _jsxs("div", { className: "space-y-3", children: [_jsx("div", { children: "Choose primary visit (keeps best image/fields):" }), _jsx(Select, { className: "w-full", value: primaryVisitId, onChange: (v) => setPrimaryVisitId(v), children: selectedVisits.map((v) => (_jsxs(Select.Option, { value: v.visit_id, children: [v.visit_id, " \u2022 ", new Date(v.first_seen).toLocaleString(), " \u2022 conf", ' ', (100 * (v.highest_confidence ?? v.confidence_score)).toFixed(1), "%"] }, v.visit_id))) }), _jsx("div", { className: "text-xs text-gray-500", children: "All visits must belong to the same person and site. The primary visit will absorb the others." })] }) })] }));
};
