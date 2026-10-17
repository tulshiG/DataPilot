import api from "./axios";

export const getExecutiveSummary = (workspaceId) => api.get(`/reports/summary/${workspaceId}`);
export const generatePdfReport = (workspaceId) => api.post(`/reports/pdf/${workspaceId}`);
export const generateExcelReport = (workspaceId) => api.post(`/reports/excel/${workspaceId}`);
export const listReports = (workspaceId) => api.get(`/reports/?workspace_id=${workspaceId}`);
export const getReportDownloadUrl = (reportId) => `${import.meta.env.VITE_API_BASE_URL}/reports/download/${reportId}`;