import { useState } from 'react';
import { Drawer, Empty, Spin } from 'antd';
import { MessageOutlined } from '@ant-design/icons';
import type { ProjectListItem } from '../services/api';
import { formatDateTime } from '../utils/format';
import { getProjectDisplayTitle } from '../utils/project-conversation';
import { loadHistoryProjectList } from '../utils/project-session-actions';

type ProjectHistoryDrawerProps = {
  currentProjectId: string | null;
  onSelectProject: (projectId: string) => void;
  disabled?: boolean;
};

const ProjectHistoryDrawer = ({
  currentProjectId,
  onSelectProject,
  disabled = false,
}: ProjectHistoryDrawerProps) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);

  const handleOpen = () => {
    setOpen(true);
    setLoading(true);
    void loadHistoryProjectList().then((items) => {
      setProjects(items);
      setLoading(false);
    });
  };

  const handleSelect = (projectId: string) => {
    onSelectProject(projectId);
    setOpen(false);
  };

  return (
    <>
      <button
        type="button"
        className="chat-history-trigger flex h-8 w-8 shrink-0 items-center justify-center rounded-sm border border-gold/35 bg-ivory/60 text-gold-dark transition-colors hover:border-gold hover:bg-gold/10 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="历史对话"
        title="历史对话"
        disabled={disabled}
        onClick={handleOpen}
      >
        <MessageOutlined aria-hidden="true" />
      </button>

      <Drawer
        title={
          <span className="font-display text-sm font-semibold tracking-wide text-ink">
            历史对话
          </span>
        }
        placement="right"
        width={360}
        open={open}
        onClose={() => setOpen(false)}
        className="project-history-drawer"
        styles={{
          header: { borderBottom: '1px solid rgba(201, 162, 39, 0.35)' },
          body: { padding: 0, background: 'rgba(250, 243, 232, 0.95)' },
        }}
      >
        {loading ? (
          <div className="flex justify-center py-12">
            <Spin />
          </div>
        ) : projects.length === 0 ? (
          <div className="px-4 py-8">
            <Empty description="暂无历史对话" />
          </div>
        ) : (
          <ul className="divide-y divide-gold/15" role="list">
            {projects.map((project) => {
              const isActive = project.project_id === currentProjectId;
              return (
                <li key={project.project_id}>
                  <button
                    type="button"
                    className={`w-full px-4 py-3 text-left transition-colors ${
                      isActive
                        ? 'border-l-2 border-gold bg-gold/10'
                        : 'border-l-2 border-transparent hover:bg-canvas/80'
                    }`}
                    onClick={() => handleSelect(project.project_id)}
                  >
                    <p className="line-clamp-2 font-body text-sm font-medium text-ink">
                      {getProjectDisplayTitle(project)}
                    </p>
                    <p className="mt-1 font-body text-xs italic text-ink-muted">
                      {project.version_count} 个版本
                      {project.last_accessed_at
                        ? ` · ${formatDateTime(project.last_accessed_at)}`
                        : ''}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Drawer>
    </>
  );
};

export default ProjectHistoryDrawer;
