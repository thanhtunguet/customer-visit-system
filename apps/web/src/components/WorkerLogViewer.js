import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useRef, useCallback } from 'react';
import { Modal, Typography, Space, Button, Tag, Alert, Switch, Select, Input, Spin, App, } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, ClearOutlined, DownloadOutlined, ReloadOutlined, BugOutlined, } from '@ant-design/icons';
import { apiClient } from '../services/api';
const { Text } = Typography;
const { Search } = Input;
const WorkerLogViewer = ({ visible, onClose, workerId, workerName, }) => {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [streaming, setStreaming] = useState(false);
    const [autoScroll, setAutoScroll] = useState(true);
    const [levelFilter, setLevelFilter] = useState('all');
    const [searchFilter, setSearchFilter] = useState('');
    const [error, setError] = useState(null);
    const logsContainerRef = useRef(null);
    const eventSourceRef = useRef(null);
    const { notification } = App.useApp();
    // Filter logs based on level and search
    const filteredLogs = logs.filter((log) => {
        const matchesLevel = levelFilter === 'all' ||
            log.level.toLowerCase() === levelFilter.toLowerCase();
        const matchesSearch = !searchFilter ||
            log.message.toLowerCase().includes(searchFilter.toLowerCase()) ||
            log.logger.toLowerCase().includes(searchFilter.toLowerCase());
        return matchesLevel && matchesSearch;
    });
    // Auto-scroll to bottom when new logs arrive
    const scrollToBottom = useCallback(() => {
        if (autoScroll && logsContainerRef.current) {
            logsContainerRef.current.scrollTop =
                logsContainerRef.current.scrollHeight;
        }
    }, [autoScroll]);
    // Load recent logs
    const loadRecentLogs = useCallback(async () => {
        if (!workerId)
            return;
        setLoading(true);
        setError(null);
        try {
            console.log('Loading logs for worker:', workerId);
            console.log('API call URL:', `/worker-management/workers/${workerId}/logs/recent?limit=100`);
            const response = await apiClient.get(`/worker-management/workers/${workerId}/logs/recent?limit=100`);
            console.log('API response:', response);
            console.log('Response type:', typeof response);
            console.log('Response.logs:', response.logs);
            if (response && response.logs) {
                setLogs(response.logs);
            }
            else {
                console.error('Unexpected response structure:', response);
                setLogs([]);
            }
            setTimeout(scrollToBottom, 100); // Allow DOM to update
        }
        catch (err) {
            console.error('Error loading logs:', err);
            const axiosError = err;
            console.error('Error response:', axiosError.response);
            const errorMsg = axiosError.response?.data?.detail || 'Failed to load logs';
            setError(errorMsg);
            notification.error({
                message: 'Log Loading Failed',
                description: errorMsg,
            });
        }
        finally {
            setLoading(false);
        }
    }, [workerId, notification, scrollToBottom]);
    // Start streaming logs
    const startStreaming = () => {
        if (!workerId || eventSourceRef.current)
            return;
        try {
            const token = localStorage.getItem('access_token');
            const streamUrl = `${apiClient.baseURL}/worker-management/workers/${workerId}/logs/stream?access_token=${encodeURIComponent(token || '')}`;
            const eventSource = new EventSource(streamUrl);
            eventSource.onopen = () => {
                setStreaming(true);
                setError(null);
                notification.success({
                    message: 'Log Stream Connected',
                    description: 'Real-time logs are now streaming',
                });
            };
            eventSource.addEventListener('initial_logs', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    setLogs(data.logs || []);
                    setTimeout(scrollToBottom, 100);
                }
                catch (e) {
                    console.error('Error parsing initial logs:', e);
                }
            });
            eventSource.addEventListener('new_logs', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    setLogs((prev) => [...prev, ...data.logs]);
                    setTimeout(scrollToBottom, 100);
                }
                catch (e) {
                    console.error('Error parsing new logs:', e);
                }
            });
            eventSource.addEventListener('error', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    setError(data.message || 'Stream error occurred');
                }
                catch (e) {
                    setError('Connection error occurred');
                }
            });
            eventSource.onerror = (event) => {
                console.error('EventSource error:', event);
                setStreaming(false);
                setError('Stream connection failed');
                eventSource.close();
                eventSourceRef.current = null;
            };
            eventSourceRef.current = eventSource;
        }
        catch (err) {
            console.error('Failed to start log stream:', err);
            setError('Failed to start log stream');
            notification.error({
                message: 'Stream Failed',
                description: 'Failed to start log streaming',
            });
        }
    };
    // Stop streaming logs
    const stopStreaming = () => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
        setStreaming(false);
    };
    // Generate test logs
    const generateTestLogs = async () => {
        try {
            await apiClient.post(`/worker-management/workers/${workerId}/logs/test`);
            notification.success({
                message: 'Test Logs Generated',
                description: 'Test log entries have been generated',
            });
        }
        catch (err) {
            const axiosError = err;
            notification.error({
                message: 'Test Failed',
                description: axiosError.response?.data?.detail || 'Failed to generate test logs',
            });
        }
    };
    // Clear logs
    const clearLogs = () => {
        setLogs([]);
    };
    // Download logs
    const downloadLogs = () => {
        const logText = filteredLogs
            .map((log) => `${log.timestamp} [${log.level}] ${log.logger}: ${log.message}${log.exception ? '\n' + log.exception : ''}`)
            .join('\n');
        const blob = new Blob([logText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `worker-${workerId}-logs-${new Date().toISOString().slice(0, 19).replace(/[:.]/g, '-')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };
    // Get level color
    const getLevelColor = (level) => {
        switch (level.toUpperCase()) {
            case 'ERROR':
                return '#ff4d4f';
            case 'WARNING':
                return '#faad14';
            case 'INFO':
                return '#1890ff';
            case 'DEBUG':
                return '#52c41a';
            default:
                return '#8c8c8c';
        }
    };
    // Format timestamp
    const formatTimestamp = (timestamp) => {
        try {
            return new Date(timestamp).toLocaleTimeString();
        }
        catch {
            return timestamp;
        }
    };
    // Load logs when modal opens
    useEffect(() => {
        if (visible && workerId) {
            loadRecentLogs();
        }
    }, [visible, workerId, loadRecentLogs]);
    // Cleanup on unmount or close
    useEffect(() => {
        return () => {
            stopStreaming();
        };
    }, []);
    return (_jsx(Modal, { title: _jsxs(Space, { children: [_jsx(BugOutlined, {}), _jsxs("span", { children: ["Worker Logs - ", workerName] }), _jsx(Tag, { color: streaming ? 'green' : 'default', children: streaming ? 'Streaming' : 'Offline' })] }), open: visible, onCancel: () => {
            stopStreaming();
            onClose();
        }, width: 1200, footer: null, styles: {
            body: { padding: 0 },
        }, children: _jsxs("div", { className: "flex flex-col h-[600px]", children: [_jsxs("div", { className: "border-b p-4 bg-gray-50", children: [_jsxs("div", { className: "flex justify-between items-center mb-3", children: [_jsxs(Space, { children: [_jsx(Button, { type: streaming ? 'default' : 'primary', icon: streaming ? _jsx(PauseCircleOutlined, {}) : _jsx(PlayCircleOutlined, {}), onClick: streaming ? stopStreaming : startStreaming, loading: loading, children: streaming ? 'Stop Stream' : 'Start Stream' }), _jsx(Button, { icon: _jsx(ReloadOutlined, {}), onClick: loadRecentLogs, loading: loading, children: "Refresh" }), _jsx(Button, { icon: _jsx(BugOutlined, {}), onClick: generateTestLogs, children: "Test Logs" })] }), _jsxs(Space, { children: [_jsx(Button, { icon: _jsx(ClearOutlined, {}), onClick: clearLogs, children: "Clear" }), _jsx(Button, { icon: _jsx(DownloadOutlined, {}), onClick: downloadLogs, children: "Download" })] })] }), _jsxs("div", { className: "flex justify-between items-center", children: [_jsxs(Space, { children: [_jsx("span", { children: "Level:" }), _jsxs(Select, { value: levelFilter, onChange: setLevelFilter, style: { width: 100 }, size: "small", children: [_jsx(Select.Option, { value: "all", children: "All" }), _jsx(Select.Option, { value: "debug", children: "Debug" }), _jsx(Select.Option, { value: "info", children: "Info" }), _jsx(Select.Option, { value: "warning", children: "Warning" }), _jsx(Select.Option, { value: "error", children: "Error" })] }), _jsx(Search, { placeholder: "Search logs...", value: searchFilter, onChange: (e) => setSearchFilter(e.target.value), style: { width: 200 }, size: "small", allowClear: true })] }), _jsxs(Space, { children: [_jsx("span", { children: "Auto-scroll:" }), _jsx(Switch, { checked: autoScroll, onChange: setAutoScroll, size: "small" }), _jsxs(Text, { type: "secondary", children: [filteredLogs.length, " / ", logs.length, " entries"] })] })] })] }), error && (_jsx(Alert, { message: error, type: "error", closable: true, onClose: () => setError(null), className: "my-4" })), _jsx("div", { className: "flex-1 overflow-hidden", children: loading ? (_jsx("div", { className: "flex justify-center items-center h-full", children: _jsx(Spin, { size: "large" }) })) : (_jsx("div", { ref: logsContainerRef, className: "h-full overflow-y-auto bg-black text-white font-mono text-sm", style: { padding: '12px' }, children: filteredLogs.length === 0 ? (_jsxs("div", { className: "text-gray-400 text-center mt-8", children: ["No log entries", ' ', logs.length > 0 ? 'match your filters' : 'available'] })) : (filteredLogs.map((log, index) => (_jsxs("div", { className: "mb-1 leading-relaxed hover:bg-gray-800 px-2 py-1 rounded", children: [_jsx("span", { className: "text-gray-400 mr-2", children: formatTimestamp(log.timestamp) }), _jsxs("span", { className: "mr-2 font-semibold", style: { color: getLevelColor(log.level) }, children: ["[", log.level, "]"] }), _jsxs("span", { className: "text-blue-300 mr-2", children: [log.logger, log.funcName && `:${log.funcName}`, log.lineno && `:${log.lineno}`, ":"] }), _jsx("span", { children: log.message }), log.exception && (_jsx("pre", { className: "text-red-400 mt-1 ml-4 text-xs whitespace-pre-wrap", children: log.exception }))] }, `${log.timestamp}-${index}-${log.message.slice(0, 50)}`)))) })) })] }) }));
};
export default WorkerLogViewer;
