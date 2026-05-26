import { useMemo, useState } from "react";
import type { CatalogInstance, PromptVariant } from "../api/types";
import { SKILL_LEVELS, skillLevelRank } from "../config/skillLevel";
import { experimentalPromptVariants, promptDisplayLabel } from "../utils/promptLabels";

export interface PromptTreeProps {
  catalog: CatalogInstance[];
  prompts: PromptVariant[];
  selectedPromptId: string | null;
  selectedCanonicalInstanceId: string | null;
  onSelectPrompt: (promptId: string) => void;
  onSelectCanonical: (instanceId: string) => void;
  onAddVariant: (instanceId: string, skillLevel: string) => void;
}

interface TaskNode {
  taskId: string;
  subjectArea: string;
  instances: CatalogInstance[];
}

export function PromptTree({
  catalog,
  prompts,
  selectedPromptId,
  selectedCanonicalInstanceId,
  onSelectPrompt,
  onSelectCanonical,
  onAddVariant
}: PromptTreeProps) {
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [expandedSkills, setExpandedSkills] = useState<Set<string>>(new Set());

  const promptsByInstance = useMemo(() => {
    const map = new Map<string, PromptVariant[]>();
    for (const prompt of prompts) {
      const list = map.get(prompt.instance_id) ?? [];
      list.push(prompt);
      map.set(prompt.instance_id, list);
    }
    return map;
  }, [prompts]);

  const taskNodes = useMemo(() => {
    const byTask = new Map<string, TaskNode>();
    for (const item of catalog) {
      const existing = byTask.get(item.task_id);
      if (existing) {
        existing.instances.push(item);
      } else {
        byTask.set(item.task_id, {
          taskId: item.task_id,
          subjectArea: item.subject_area,
          instances: [item]
        });
      }
    }
    return [...byTask.values()].sort((a, b) => a.taskId.localeCompare(b.taskId));
  }, [catalog]);

  function toggleTask(taskId: string) {
    setExpandedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  function toggleSkill(key: string) {
    setExpandedSkills((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <nav className="prompt-tree" aria-label="Prompt variants">
      {taskNodes.map((task) => {
        const taskOpen = expandedTasks.has(task.taskId);
        const instancesBySkill = [...task.instances].sort(
          (a, b) => skillLevelRank(a.skill_level) - skillLevelRank(b.skill_level)
        );
        return (
          <div key={task.taskId} className="tree-task">
            <button type="button" className="tree-row tree-task-row" onClick={() => toggleTask(task.taskId)}>
              <span className="tree-chevron">{taskOpen ? "▾" : "▸"}</span>
              <span className="tree-task-labels">
                <span className="tree-label">{task.taskId}</span>
                {task.subjectArea ? <span className="tree-subtitle">{task.subjectArea}</span> : null}
              </span>
            </button>
            {taskOpen ? (
              <div className="tree-children">
                {SKILL_LEVELS.map((skill) => {
                  const skillKey = `${task.taskId}:${skill}`;
                  const skillOpen = expandedSkills.has(skillKey);
                  const skillInstances = instancesBySkill.filter((i) => i.skill_level === skill);
                  if (skillInstances.length === 0) return null;
                  return (
                    <div key={skillKey} className="tree-skill">
                      <div className="tree-row tree-skill-row">
                        <button type="button" className="tree-skill-toggle" onClick={() => toggleSkill(skillKey)}>
                          <span className="tree-chevron">{skillOpen ? "▾" : "▸"}</span>
                          <span className="tree-label">{skill}</span>
                        </button>
                        <button
                          type="button"
                          className="tree-add-btn"
                          title={`New variant for ${skill} level`}
                          onClick={() => onAddVariant(skillInstances[0].instance_id, skill)}
                        >
                          +
                        </button>
                      </div>
                      {skillOpen ? (
                        <ul className="tree-leaves">
                          {skillInstances.flatMap((instance) => {
                            const variants = experimentalPromptVariants(
                              promptsByInstance.get(instance.instance_id) ?? []
                            );
                            const catalogLeaf = (
                              <li key={`${instance.instance_id}:catalog`}>
                                <button
                                  type="button"
                                  className={
                                    selectedCanonicalInstanceId === instance.instance_id &&
                                    !selectedPromptId
                                      ? "tree-leaf tree-leaf-selected"
                                      : "tree-leaf tree-leaf-catalog"
                                  }
                                  onClick={() => onSelectCanonical(instance.instance_id)}
                                  title="On-disk catalog prompt for this skill level"
                                >
                                  {skill}
                                </button>
                              </li>
                            );
                            if (variants.length === 0) {
                              return [catalogLeaf];
                            }
                            return [
                              catalogLeaf,
                              ...variants.map((variant) => (
                                <li key={variant.id}>
                                  <button
                                    type="button"
                                    className={
                                      selectedPromptId === variant.id
                                        ? "tree-leaf tree-leaf-selected"
                                        : "tree-leaf"
                                    }
                                    onClick={() => onSelectPrompt(variant.id)}
                                  >
                                    {promptDisplayLabel(variant)}
                                  </button>
                                </li>
                              ))
                            ];
                          })}
                        </ul>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}
