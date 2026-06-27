"use client";
import { useState } from 'react';
import { App, Drawer, Empty, Spin } from 'antd';
import { DeleteOutlined, MessageOutlined } from '@ant-design/icons';
import type { ProjectListItem } from '../../../services/api';
import { formatTimestamp } from '../../../lib/timestamp';
import { getProjectDisplayTitle } from '../lib/project-conversation';
import { loadHistoryProjectList } from '../lib/project-session-actions';

type ProjectHistoryDrawerProps = {
  currentProjectId: string | null;
  userId: string;
  onSelectProject: (projectId: string) => void;
  onDeleteProject: (projectId: string) => Promise<boolean>;
  disabled?: boolean;
};

const ProjectHistoryDrawer = ({
  currentProjectId,
  userId,
  onSelectProject,
  onDeleteProject,
  disabled = false,
}: ProjectHistoryDrawerProps) => {
  const { modal } = App.useApp();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);

  const handleOpen = () => {
    if (!userId) {
      return;
    }
    setOpen(true);
    setLoading(true);
    void loadHistoryProjectList(userId).then((items) => {
      setProjects(items);
      setLoading(false);
    });
  };

  const handleSelect = (projectId: string) => {
    onSelectProject(projectId);
    setOpen(false);
  };

  const handleDelete = (project: ProjectListItem) => {
    modal.confirm({
      title: '删除对话？',
      content: `确定删除「${getProjectDisplayTitle(project)}」吗？此操作不可恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        const deleted = await onDeleteProject(project.project_id);
        if (deleted) {
          setProjects((current) =>
            current.filter((item) => item.project_id !== project.project_id),
          );
        }
      },
    });
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
        size={300}
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
                <li key={project.project_id} className="flex items-stretch">
                  <button
                    type="button"
                    className={`min-w-0 flex-1 px-4 py-3 text-left transition-colors ${
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
                        ? ` · ${formatTimestamp(project.last_accessed_at)}`
                        : ''}
                    </p>
                  </button>
                  <button
                    type="button"
                    className="flex w-10 shrink-0 items-center justify-center text-ink-muted transition-colors hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label={`删除 ${getProjectDisplayTitle(project)}`}
                    title="删除对话"
                    disabled={disabled}
                    onClick={(event) => {
                      event.stopPropagation();
                      handleDelete(project);
                    }}
                  >
                    <DeleteOutlined aria-hidden="true" />
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
