// export default App

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./routes/ProtectedRoute";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Workspace from "./pages/Workspace";
import Upload from "./pages/Upload";
import Query from "./pages/Query";
import Reports from "./pages/Reports";
import RelationshipDiagram from "./pages/RelationshipDiagram";
import Settings from "./pages/Settings";
import AIAnalytics from "./pages/AIAnalytics";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/login" />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
       
        <Route path="/workspace" element={<ProtectedRoute> <Workspace /> </ProtectedRoute>}/>
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <Upload />
              </ProtectedRoute>
            }
          />
          <Route path="/query" element={<ProtectedRoute><Query /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/relationships" element={<ProtectedRoute><RelationshipDiagram /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          <Route path="/ai-analytics" element={<ProtectedRoute><AIAnalytics /></ProtectedRoute>} />
           </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
