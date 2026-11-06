"use client";
/** @screen 디자인 갤러리 — 설정 · @status 완료 */
/**
 * SettingsPage 시연 — 왼쪽 구역 · 오른쪽 그 구역의 설정. 고른 구역은 주소 ?tab= 에 남는다.
 * 저장은 구역마다(각 구역이 자기 저장 버튼 · useAction). 서버 호출 대신 잠깐 기다리는 가짜 저장.
 */
import { useState } from "react";
import { Button, Field, Select, SettingsPage, Switch, TextInput, useAction } from "@nova/ui";

const fakeSave = () => new Promise<void>((r) => setTimeout(r, 300));

function General() {
  const [name, setName] = useState("누리 관제센터");
  const [tz, setTz] = useState("Asia/Seoul");
  const save = useAction(fakeSave, { success: "일반 설정을 저장했습니다" });
  return (
    <div className="stack gap-4">
      <Field label="표시 이름" required help="머리띠와 보고서 첫 장에 보입니다">{(p) => <TextInput {...p} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
      <Field label="시간대">{(p) => <Select {...p} value={tz} onChange={(e) => setTz(e.target.value)} options={[{ value: "Asia/Seoul", label: "서울 (UTC+9)" }, { value: "UTC", label: "협정 세계시 (UTC)" }]} />}</Field>
      <div className="row justify-end"><Button loading={save.running} onClick={() => void save.run()}>저장</Button></div>
    </div>
  );
}

function Notify() {
  const [sms, setSms] = useState(false);
  const [mail, setMail] = useState(true);
  const save = useAction(fakeSave, { success: "알림 설정을 저장했습니다" });
  return (
    <div className="stack gap-4">
      <div className="row between"><span>위험 경보 문자 받기</span><Switch label="위험 경보 문자 받기" checked={sms} onChange={setSms} /></div>
      <div className="row between"><span>하루 요약 메일 받기</span><Switch label="하루 요약 메일 받기" checked={mail} onChange={setMail} /></div>
      <div className="row justify-end"><Button loading={save.running} onClick={() => void save.run()}>저장</Button></div>
    </div>
  );
}

function Security() {
  const [idle, setIdle] = useState("30");
  const save = useAction(fakeSave, { success: "보안 설정을 저장했습니다" });
  return (
    <div className="stack gap-4">
      <Field label="자동 로그아웃" help="이 시간 동안 아무 동작이 없으면 로그아웃합니다">{(p) => (
        <Select {...p} value={idle} onChange={(e) => setIdle(e.target.value)} options={[{ value: "15", label: "15분" }, { value: "30", label: "30분" }, { value: "60", label: "1시간" }]} />
      )}</Field>
      <div className="row justify-end"><Button loading={save.running} onClick={() => void save.run()}>저장</Button></div>
    </div>
  );
}

export default function DesignSettings() {
  return (
    <SettingsPage
      title="설정 — 시연"
      description="SettingsPage — 왼쪽에서 구역을 고르면 오른쪽에 그 구역의 설정. 고른 구역은 주소(?tab)에 남고, 저장은 구역마다 합니다."
      sections={[
        { id: "general", label: "일반", description: "이름 · 시간대", render: () => <General /> },
        { id: "notify", label: "알림", description: "경보를 어디로 받을지", render: () => <Notify /> },
        { id: "security", label: "보안", description: "로그인 유지 시간", render: () => <Security /> },
      ]}
    />
  );
}
