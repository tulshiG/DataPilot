import api from "./axios";

export const getDashboard = (workspaceId, filters = {}) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.append(key, value);
  });
  return api.get(`/dashboard/${workspaceId}?${params.toString()}`);
};