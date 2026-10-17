import api from "./axios";

// ── AI Engine ──
export const getAIStatus = () => api.get("/ai/status");
export const semanticSearch = (workspaceId, query, k = 10) =>
  api.get(`/ai/search/${workspaceId}`, { params: { q: query, k } });
export const getRAGContext = (workspaceId, query) =>
  api.get(`/ai/rag/${workspaceId}`, { params: { q: query } });
export const debugParse = (workspaceId, query) =>
  api.post(`/ai/parse/${workspaceId}`, null, { params: { q: query } });
export const getWorkspaceMetadata = (workspaceId) =>
  api.get(`/ai/metadata/${workspaceId}`);

// ── ML Engine ──
export const runForecast = (datasetId, dateCol, valueCol, periods = 12, method = "auto") =>
  api.post(`/ml/forecast/${datasetId}`, null, {
    params: { date_col: dateCol, value_col: valueCol, periods, method },
  });

export const detectAnomalies = (datasetId, columns = null, method = "auto", timeCol = null) =>
  api.post(`/ml/anomalies/${datasetId}`, null, {
    params: { columns, method, time_col: timeCol },
  });

export const runSegmentation = (datasetId, features = null, nClusters = null) =>
  api.post(`/ml/segment/${datasetId}`, null, {
    params: { features, n_clusters: nClusters },
  });

export const runRFM = (datasetId, customerCol, dateCol, amountCol) =>
  api.post(`/ml/rfm/${datasetId}`, null, {
    params: { customer_col: customerCol, date_col: dateCol, amount_col: amountCol },
  });

export const getRecommendations = (workspaceId, datasetId = null) =>
  api.get(`/ml/recommendations/${workspaceId}`, { params: { dataset_id: datasetId } });

export const getKnowledgeGraph = (workspaceId) =>
  api.get(`/ml/graph/${workspaceId}`);

export const findJoinPath = (workspaceId, source, target) =>
  api.get(`/ml/graph/${workspaceId}/join-path`, { params: { source, target } });

export const getSemanticLayer = (workspaceId) =>
  api.get(`/ml/semantic/${workspaceId}`);
