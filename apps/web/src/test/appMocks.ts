import { vi } from 'vitest';

type MessageApi = {
  success: (content: any) => void;
  error: (content: any) => void;
  info: (content: any) => void;
  warning: (content: any) => void;
  loading: (content: any) => void;
};

type NotificationApi = {
  success: (config: any) => void;
  error: (config: any) => void;
  info: (config: any) => void;
  warning: (config: any) => void;
  open: (config: any) => void;
};

type ModalApi = {
  info: (config: any) => void;
  success: (config: any) => void;
  error: (config: any) => void;
  warning: (config: any) => void;
  confirm: (config: any) => void;
};

export const mockMessage: MessageApi = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  loading: vi.fn(),
};

export const mockNotification: NotificationApi = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  open: vi.fn(),
};

export const mockModal: ModalApi = {
  info: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  confirm: vi.fn(),
};

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  const App = actual.App as typeof actual.App & {
    useApp: () => { message: MessageApi; notification: NotificationApi; modal: ModalApi };
  };

  const AppWithUseApp = Object.assign(App, {
    useApp: () => ({
      message: mockMessage,
      notification: mockNotification,
      modal: mockModal,
    }),
  });

  return {
    ...actual,
    App: AppWithUseApp,
  };
});
