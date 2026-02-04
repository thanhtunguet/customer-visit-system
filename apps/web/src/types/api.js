export var CameraType;
(function (CameraType) {
  CameraType['RTSP'] = 'rtsp';
  CameraType['WEBCAM'] = 'webcam';
})(CameraType || (CameraType = {}));
// ===============================
// User Management Types
// ===============================
export var UserRole;
(function (UserRole) {
  UserRole['SYSTEM_ADMIN'] = 'system_admin';
  UserRole['TENANT_ADMIN'] = 'tenant_admin';
  UserRole['SITE_MANAGER'] = 'site_manager';
  UserRole['WORKER'] = 'worker';
})(UserRole || (UserRole = {}));
