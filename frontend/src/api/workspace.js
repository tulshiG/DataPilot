import api from "./axios";

export const createWorkspace = (data) => api.post("/workspaces/", data);
export const getWorkspaces = () => api.get("/workspaces/");
export const getWorkspace = (id) => api.get(`/workspaces/${id}`);
export const deleteWorkspace = (id) => api.delete(`/workspaces/${id}`);