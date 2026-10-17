import api from "./axios";

export const discoverRelationships = (workspaceId) => api.post(`/relationships/discover/${workspaceId}`);
export const getRelationshipDiagram = (workspaceId) => api.get(`/relationships/diagram/${workspaceId}`);
export const validateRelationship = (relationshipId) => api.post(`/relationships/validate/${relationshipId}`);