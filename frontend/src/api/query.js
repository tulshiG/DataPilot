// import api from "./axios";

// export const askQuery = (workspaceId, query) => api.post(`/query/${workspaceId}`, { query });
// export const getQueryHistory = (workspaceId) => api.get(`/query/history/${workspaceId}`);
import api from "./axios";

export const askQuery = (workspaceId, query, datasetId = null) =>
  api.post(`/query/${workspaceId}`, { query, dataset_id: datasetId });

export const getQueryHistory = (workspaceId) => api.get(`/query/history/${workspaceId}`);