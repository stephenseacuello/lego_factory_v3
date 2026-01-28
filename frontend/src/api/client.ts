import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Health & Status
export const fetchHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

// Dashboard KPIs
export const fetchDashboardKPIs = async () => {
  const response = await api.get('/api/analytics/kpis');
  return response.data;
};

export const fetchOEEData = async () => {
  const response = await api.get('/api/analytics/oee');
  return response.data;
};

// SCADA Tags
export const fetchTags = async (params?: { category?: string; page?: number }) => {
  const response = await api.get('/api/scada/tags', { params });
  return response.data;
};

export const fetchTagValue = async (tagId: string) => {
  const response = await api.get(`/api/scada/tags/${tagId}`);
  return response.data;
};

export const writeTagValue = async (tagId: string, value: number | string | boolean) => {
  const response = await api.post('/api/scada/tags/write', { tag_id: tagId, value });
  return response.data;
};

// Alarms
export const fetchAlarmSummary = async () => {
  const response = await api.get('/api/scada/alarms/summary');
  return response.data;
};

export const fetchActiveAlarms = async () => {
  const response = await api.get('/api/scada/alarms/active');
  return response.data;
};

export const acknowledgeAlarm = async (alarmId: string, notes?: string) => {
  const response = await api.post(`/api/scada/alarms/${alarmId}/acknowledge`, {
    acknowledged_by: 'operator',
    notes,
  });
  return response.data;
};

export const shelveAlarm = async (alarmId: string, durationMinutes: number, reason: string) => {
  const response = await api.post(`/api/scada/alarms/${alarmId}/shelve`, {
    duration_minutes: durationMinutes,
    reason,
  });
  return response.data;
};

// Historian
export const fetchTrendData = async (
  tagIds: string[],
  startTime: string,
  endTime: string,
  aggregation?: string
) => {
  const response = await api.get('/api/historian/trend', {
    params: {
      tags: tagIds.join(','),
      start: startTime,
      end: endTime,
      aggregation,
    },
  });
  return response.data;
};

export const fetchRawData = async (
  tagIds: string[],
  startTime: string,
  endTime: string
) => {
  const response = await api.get('/api/historian/raw', {
    params: {
      tags: tagIds.join(','),
      start: startTime,
      end: endTime,
    },
  });
  return response.data;
};

// Production / Work Orders
export const fetchWorkOrders = async (params?: { status?: string; page?: number }) => {
  const response = await api.get('/api/production/work-orders', { params });
  return response.data;
};

export const createWorkOrder = async (data: {
  product_id: string;
  quantity: number;
  priority?: number;
  scheduled_start?: string;
}) => {
  const response = await api.post('/api/production/work-orders', data);
  return response.data;
};

export const getWorkOrder = async (workOrderId: string) => {
  const response = await api.get(`/api/production/work-orders/${workOrderId}`);
  return response.data;
};

export const updateWorkOrderStatus = async (
  workOrderId: string,
  action: 'start' | 'pause' | 'resume' | 'complete' | 'cancel',
  data?: { notes?: string; quantity_completed?: number }
) => {
  const response = await api.post(`/api/production/work-orders/${workOrderId}/${action}`, data);
  return response.data;
};

export const startWorkOrder = async (workOrderId: string) => {
  return updateWorkOrderStatus(workOrderId, 'start');
};

export const pauseWorkOrder = async (workOrderId: string, notes?: string) => {
  return updateWorkOrderStatus(workOrderId, 'pause', { notes });
};

export const completeWorkOrder = async (workOrderId: string, quantity_completed?: number) => {
  return updateWorkOrderStatus(workOrderId, 'complete', { quantity_completed });
};

export const cancelWorkOrder = async (workOrderId: string, notes?: string) => {
  return updateWorkOrderStatus(workOrderId, 'cancel', { notes });
};

// QMS - NCR
export const fetchNCRs = async (params?: { status?: string; severity?: string; page?: number }) => {
  const response = await api.get('/api/qms/ncrs', { params });
  return response.data;
};

export const createNCR = async (data: {
  title: string;
  description: string;
  detected_by: string;
  severity?: string;
}) => {
  const response = await api.post('/api/qms/ncrs', data);
  return response.data;
};

export const fetchNCRMetrics = async (days?: number) => {
  const response = await api.get('/api/qms/ncrs/metrics', { params: { days } });
  return response.data;
};

// QMS - CAPA
export const fetchCAPAs = async (params?: { status?: string; page?: number }) => {
  const response = await api.get('/api/qms/capas', { params });
  return response.data;
};

export const createCAPA = async (data: {
  title: string;
  problem_statement: string;
  owner_id: string;
  ncr_number?: string;
  capa_type?: 'corrective' | 'preventive';
}) => {
  const response = await api.post('/api/qms/capas', data);
  return response.data;
};

// Robotics
export const fetchRobots = async () => {
  const response = await api.get('/api/robotics/robots');
  return response.data;
};

export const fetchRobotState = async (robotId: string) => {
  const response = await api.get(`/api/robotics/robots/${robotId}/state`);
  return response.data;
};

export const sendRobotCommand = async (
  robotId: string,
  command: { x: number; y: number; z: number; speed?: number }
) => {
  const response = await api.post(`/api/robotics/robots/${robotId}/move`, command);
  return response.data;
};

// ML Inference
export const runInference = async (sensorData: number[][], tagId?: string) => {
  const response = await api.post('/api/ml/inference/predict', {
    sensor_data: sensorData,
    tag_id: tagId,
  });
  return response.data;
};

export const fetchInferenceStats = async () => {
  const response = await api.get('/api/ml/inference/stats');
  return response.data;
};

// Analytics
export const fetchSPCData = async (tagId: string, startTime: string, endTime: string) => {
  const response = await api.get('/api/analytics/spc', {
    params: { tag_id: tagId, start: startTime, end: endTime },
  });
  return response.data;
};

export const fetchParetoAnalysis = async () => {
  const response = await api.get('/api/analytics/pareto');
  return response.data;
};

export default api;
