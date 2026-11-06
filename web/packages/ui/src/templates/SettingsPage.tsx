"use client";
/**
 * 설정 템플릿 — 왼쪽 구역 목록 · 오른쪽 그 구역의 슬롯. 화면은 sections(이름 · 설명 · 그리기)만 넘긴다(ui.md §1).
 * - 고른 구역은 주소 `?tab=<id>` 에 남는다 — 새로고침 · 공유해도 같은 구역(UX H6). 모르는 id 면 첫 구역
 * - 저장은 **구역마다** — 각 구역의 render 가 자기 저장 버튼(useAction)을 가진다. 한 번에 전부 저장하면
 *   어느 구역이 실패했는지 흐려지고, 안 고친 구역까지 덮어쓴다
 * - 구역 목록은 탭 목록(WAI-ARIA tabs, 세로) — ↑ ↓ · Home · End 로 옮긴다(UX H7). 900px 아래에서는 위에 가로로
 */
import React, { useRef } from "react";
import { useQueryState } from "../hooks";
import { Content, PageHeader } from "../components/basic";
import { EmptyState } from "../components/feedback";

export interface SettingsSection { id: string; label: string; description?: React.ReactNode; render: () => React.ReactNode }

export interface SettingsPageProps {
  title: string;
  description?: React.ReactNode;
  sections: SettingsSection[];
}

export function SettingsPage({ title, description, sections }: SettingsPageProps) {
  const [tab, setTab] = useQueryState("tab");
  const current = sections.find((s) => s.id === tab) ?? sections[0];
  const tabs = useRef<HTMLDivElement>(null);

  const onKeyDown = (e: React.KeyboardEvent) => {
    const at = sections.findIndex((s) => s.id === current?.id);
    const to = e.key === "ArrowDown" || e.key === "ArrowRight" ? at + 1
      : e.key === "ArrowUp" || e.key === "ArrowLeft" ? at - 1
        : e.key === "Home" ? 0 : e.key === "End" ? sections.length - 1 : null;
    if (to === null || sections.length === 0) return;
    e.preventDefault();
    const n = (to + sections.length) % sections.length;
    setTab(sections[n].id);
    tabs.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[n]?.focus();
  };

  return (
    <Content width="default">
      <PageHeader title={title} description={description} />
      {!current ? <EmptyState title="설정할 구역이 없습니다" /> : (
        <div className="settings">
          <div ref={tabs} className="settings-nav" role="tablist" aria-orientation="vertical" aria-label={`${title} 구역`} onKeyDown={onKeyDown}>
            {sections.map((s) => {
              const on = s.id === current.id;
              return (
                <button key={s.id} id={`set-tab-${s.id}`} type="button" role="tab" aria-selected={on} aria-controls={`set-panel-${s.id}`}
                  tabIndex={on ? 0 : -1} onClick={() => setTab(s.id)}>{s.label}</button>
              );
            })}
          </div>
          <section key={current.id} id={`set-panel-${current.id}`} className="card settings-panel" role="tabpanel" aria-labelledby={`set-tab-${current.id}`}>
            <div className="section-head">
              <h2>{current.label}</h2>
              {current.description && <p className="small muted">{current.description}</p>}
            </div>
            {current.render()}
          </section>
        </div>
      )}
    </Content>
  );
}
