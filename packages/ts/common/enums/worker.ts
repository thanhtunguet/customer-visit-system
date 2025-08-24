export enum WorkerStatus {
  IDLE = 'idle',
  PROCESSING = 'processing',
  ONLINE = 'online',
  OFFLINE = 'offline',
  ERROR = 'error',
  MAINTENANCE = 'maintenance',
}

export class WorkerStatusHelper {
  /**
   * Get list of statuses considered as 'active'
   */
  static getActiveStatuses(): WorkerStatus[] {
    return [WorkerStatus.IDLE, WorkerStatus.PROCESSING, WorkerStatus.ONLINE];
  }

  /**
   * Get list of statuses considered as 'inactive'
   */
  static getInactiveStatuses(): WorkerStatus[] {
    return [WorkerStatus.OFFLINE, WorkerStatus.ERROR, WorkerStatus.MAINTENANCE];
  }

  /**
   * Check if a status is considered active
   */
  static isActive(status: WorkerStatus): boolean {
    return this.getActiveStatuses().includes(status);
  }

  /**
   * Check if a status is considered inactive
   */
  static isInactive(status: WorkerStatus): boolean {
    return this.getInactiveStatuses().includes(status);
  }

  /**
   * Convert string to WorkerStatus enum
   */
  static fromString(status: string): WorkerStatus {
    const normalizedStatus = status.toLowerCase();
    for (const [key, value] of Object.entries(WorkerStatus)) {
      if (value === normalizedStatus) {
        return value as WorkerStatus;
      }
    }
    throw new Error(`Invalid worker status: ${status}`);
  }

  /**
   * Get all available status values
   */
  static getAllStatuses(): WorkerStatus[] {
    return Object.values(WorkerStatus);
  }

  /**
   * Get display label for status
   */
  static getDisplayLabel(status: WorkerStatus): string {
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