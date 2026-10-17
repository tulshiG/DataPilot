import api from "./axios";

export const uploadFiles = (workspaceId, files) => {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return api.post(`/upload/${workspaceId}`, formData);
};

export const getDatasets = (workspaceId) => api.get(`/upload/${workspaceId}`);
export const deleteDataset = (datasetId) => api.delete(`/upload/${datasetId}`);