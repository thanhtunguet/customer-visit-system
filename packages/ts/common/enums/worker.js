export var WorkerStatus;
(function (WorkerStatus) {
    WorkerStatus["IDLE"] = "idle";
    WorkerStatus["PROCESSING"] = "processing";
    WorkerStatus["ONLINE"] = "online";
    WorkerStatus["OFFLINE"] = "offline";
    WorkerStatus["ERROR"] = "error";
    WorkerStatus["MAINTENANCE"] = "maintenance";
})(WorkerStatus || (WorkerStatus = {}));
export class WorkerStatusHelper {
    /**
     * Get list of statuses considered as 'active'
     */
    static getActiveStatuses() {
        return [WorkerStatus.IDLE, WorkerStatus.PROCESSING, WorkerStatus.ONLINE];
    }
    /**
     * Get list of statuses considered as 'inactive'
     */
    static getInactiveStatuses() {
        return [WorkerStatus.OFFLINE, WorkerStatus.ERROR, WorkerStatus.MAINTENANCE];
    }
    /**
     * Check if a status is considered active
     */
    static isActive(status) {
        return this.getActiveStatuses().includes(status);
    }
    /**
     * Check if a status is considered inactive
     */
    static isInactive(status) {
        return this.getInactiveStatuses().includes(status);
    }
    /**
     * Convert string to WorkerStatus enum
     */
    static fromString(status) {
        const normalizedStatus = status.toLowerCase();
        for (const [key, value] of Object.entries(WorkerStatus)) {
            if (value === normalizedStatus) {
                return value;
            }
        }
        throw new Error(`Invalid worker status: ${status}`);
    }
    /**
     * Get all available status values
     */
    static getAllStatuses() {
        return Object.values(WorkerStatus);
    }
    /**
     * Get display label for status
     */
    static getDisplayLabel(status) {
        switch (status) {
            case WorkerStatus.IDLE:
                return 'Idle';
            case WorkerStatus.PROCESSING:
                return 'Processing';
            case WorkerStatus.ONLINE:
                return 'Online';
            case WorkerStatus.OFFLINE:
                return 'Offline';
            case WorkerStatus.ERROR:
                return 'Error';
            case WorkerStatus.MAINTENANCE:
                return 'Maintenance';
            default:
                return status;
        }
    }
    /**
     * Get status options for select components
     */
    static getStatusOptions() {
        return this.getAllStatuses().map(status => ({
            value: status,
            label: this.getDisplayLabel(status)
        }));
    }
}
