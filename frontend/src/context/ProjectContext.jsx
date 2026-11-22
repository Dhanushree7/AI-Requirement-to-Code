import React, { createContext, useContext, useState, useEffect } from 'react';
import { projectApi } from '../api';
import { useAuth } from './AuthContext';

const ProjectContext = createContext(null);

export const ProjectProvider = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [activeProject, setActiveProject] = useState(null);
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState(null);
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [testCasesCount, setTestCasesCount] = useState(0);

  // Load all projects
  const refreshProjects = async () => {
    try {
      setBackendError(null);
      const data = await projectApi.list();
      setProjects(data);
      if (data.length > 0 && !activeProjectId) {
        setActiveProjectId(data[0].id);
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
      setBackendError("Backend service is temporarily unreachable or starting up. Please wait a moment and refresh.");
    } finally {
      setLoading(false);
    }
  };

  // Load dashboard data whenever activeProjectId changes
  const refreshDashboard = async () => {
    if (!activeProjectId) return;
    try {
      const data = await projectApi.getDashboard(activeProjectId);
      setDashboardData(data);
      const proj = projects.find(p => p.id === activeProjectId);
      if (proj) {
        setActiveProject({ ...proj, ...data });
      } else {
        setActiveProject({ id: activeProjectId, name: data.project_name, ...data });
      }
      // Check test cases count
      const tcCard = data.artifact_cards?.find(c => c.type === 'testcases');
      setTestCasesCount(tcCard?.count || 0);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    }
  };

  // Derive which artifacts exist for the active project
  const availableArtifacts = React.useMemo(() => {
    const map = {
      srs: false,
      architecture: false,
      schema: false,
      api: false,
      skeleton: false,
      testcases: false,
      graph: false,
    };
    if (dashboardData?.artifact_cards) {
      dashboardData.artifact_cards.forEach((c) => {
        map[c.type] = c.status === 'completed' && (c.count > 0 || c.status === 'completed');
      });
    }
    if (dashboardData?.graph_summary) {
      map.graph = (dashboardData.graph_summary.nodes_count || 0) > 0;
    }
    return map;
  }, [dashboardData]);

  useEffect(() => {
    if (isAuthenticated) {
      refreshProjects();
    } else {
      setProjects([]);
      setActiveProjectId(null);
      setActiveProject(null);
      setDashboardData(null);
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (activeProjectId) {
      refreshDashboard();
      const proj = projects.find(p => p.id === activeProjectId);
      if (proj) setActiveProject(proj);
    }
  }, [activeProjectId]);

  const selectProject = (id) => {
    setActiveProjectId(id);
  };

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProjectId,
        activeProject,
        dashboardData,
        loading,
        backendError,
        testCasesCount,
        availableArtifacts,
        isNewProjectModalOpen,
        setIsNewProjectModalOpen,
        isAssistantOpen,
        setIsAssistantOpen,
        refreshProjects,
        refreshDashboard,
        selectProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
};

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
};
