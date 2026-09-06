import { useState } from "react";
import { api, json } from "./api";
import type { Document, Keyword, Analysis } from "./types";
import { date, Empty, Loading, Notice, Risk, Title, useLoad } from "./ui";
export function Admin() {
  const [tab, setTab] = useState("dashboard");
  const tabs = [
    ["dashboard", "대시보드"],
    ["documents", "공식 문서"],
    ["keywords", "위험 키워드"],
    ["reviews", "피드백 검토"],
    ["analysis-logs", "분석 로그"],
    ["audit-logs", "감사 로그"],
  ];
  return (
    <>
      <Title
        title="서비스 관리"
        description="분석 현황과 서비스의 기준이 되는 문서·키워드를 관리하세요."
      />
      <nav className="tabs" aria-label="관리자 메뉴">
        {tabs.map(([id, title]) => (
          <button
            key={id}
            className={tab === id ? "selected" : ""}
            onClick={() => setTab(id)}
          >
            {title}
          </button>
        ))}
      </nav>
      {tab === "dashboard" ? (
        <Dashboard />
      ) : tab === "documents" ? (
        <Documents />
      ) : tab === "keywords" ? (
        <Keywords />
      ) : tab === "reviews" ? (
        <Reviews />
      ) : (
        <Logs key={tab} kind={tab} />
      )}
    </>
  );
}
function Dashboard() {
  const { data, error, loading } =
    useLoad<Record<string, number>>("/admin/dashboard");
  return (
    <>
      <Notice error={error} />
      {loading ? (
        <Loading />
      ) : (
        data && (
          <div className="cards stats">
            {[
              ["totalAnalysisCount", "전체 분석"],
              ["todayAnalysisCount", "오늘 분석"],
              ["highRiskCount", "높은 위험도"],
              ["documentCount", "공식 문서"],
              ["keywordCount", "위험 키워드"],
            ].map(([key, label]) => (
              <div className="panel" key={key}>
                <p>{label}</p>
                <strong>{data[key]?.toLocaleString() ?? "—"}</strong>
              </div>
            ))}
          </div>
        )
      )}
    </>
  );
}
function Documents() {
  const { data, error, loading, reload } =
      useLoad<Document[]>("/admin/documents"),
    [actionError, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  async function action(path: string, method: string) {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ jobId?: string }>(path, { method });
      setNotice(
        result?.jobId
          ? "처리를 접수했습니다. 새로고침으로 처리 상태를 확인하세요."
          : "문서를 삭제했습니다.",
      );
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Notice error={error || actionError} />
      {notice && <p role="status">{notice}</p>}
      <section className="panel">
        <h2>공식 문서 등록</h2>
        <form
          className="form-grid"
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const body = new FormData(form);
            const file = body.get("file") as File;
            if (file.size > 10 * 1024 * 1024) {
              setError("10MB 이하의 PDF를 선택해 주세요.");
              return;
            }
            setBusy(true);
            setError("");
            try {
              await api("/admin/documents", { method: "POST", body });
              form.reset();
              setNotice(
                "문서를 등록했습니다. 텍스트 추출 상태를 새로고침으로 확인하세요.",
              );
              reload();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            문서명
            <input name="title" required maxLength={255} />
          </label>
          <label>
            출처 기관
            <input name="source" required maxLength={100} />
          </label>
          <label>
            공식 원문 URL
            <input name="sourceUrl" type="url" placeholder="https://" />
          </label>
          <label>
            PDF 파일 · 최대 10MB
            <input
              name="file"
              type="file"
              accept="application/pdf,.pdf"
              required
            />
          </label>
          <button disabled={busy}>문서 업로드</button>
        </form>
      </section>
      <section className="panel table-wrap">
        <div className="row">
          <h2>등록된 문서</h2>
          <button
            className="secondary"
            disabled={busy || loading}
            onClick={reload}
          >
            새로고침
          </button>
        </div>
        <p className="muted">
          완료는 텍스트 추출 상태입니다. RAG 검색에 사용하려면 별도 임베딩
          인덱싱이 필요합니다.
        </p>
        {loading ? (
          <Loading />
        ) : !data?.length ? (
          <Empty />
        ) : (
          <table>
            <thead>
              <tr>
                <th>문서명</th>
                <th>출처</th>
                <th>처리 상태</th>
                <th>문단 수</th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.documentId}>
                  <td>{d.title}</td>
                  <td>{d.source}</td>
                  <td>
                    {(
                      {
                        UPLOADED: "접수",
                        PROCESSING: "처리 중",
                        COMPLETED: "추출 완료",
                        FAILED: "실패",
                      } as Record<string, string>
                    )[d.status] || d.status}
                  </td>
                  <td>{d.chunkCount}</td>
                  <td>
                    {d.status === "FAILED" && (
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() =>
                          action(
                            `/admin/documents/${d.documentId}/processing-jobs`,
                            "POST",
                          )
                        }
                      >
                        재처리
                      </button>
                    )}
                    <button
                      className="text-button danger"
                      disabled={busy}
                      onClick={() => {
                        if (confirm("문서와 연결된 근거 데이터를 삭제할까요?"))
                          void action(
                            `/admin/documents/${d.documentId}`,
                            "DELETE",
                          );
                      }}
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
const categories = [
  "기관사칭",
  "개인정보요구",
  "금융사기",
  "링크유도",
  "협박",
  "가족사칭",
];
function Keywords() {
  const { data, error, loading, reload } =
      useLoad<Keyword[]>("/admin/keywords"),
    [edit, setEdit] = useState<Keyword | null>(null),
    [actionError, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <>
      <Notice error={error || actionError} />
      <section className="panel">
        <h2>{edit ? "키워드 수정" : "위험 키워드 등록"}</h2>
        <form
          key={edit?.keywordId ?? "new"}
          className="form-grid"
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget,
              f = new FormData(form);
            setBusy(true);
            setError("");
            try {
              await api(
                "/admin/keywords" + (edit ? "/" + edit.keywordId : ""),
                json(edit ? "PUT" : "POST", {
                  keyword: f.get("keyword"),
                  riskScore: Number(f.get("riskScore")),
                  category: f.get("category"),
                  description: f.get("description"),
                  active: f.has("active"),
                }),
              );
              setEdit(null);
              form.reset();
              reload();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            키워드
            <input
              name="keyword"
              required
              maxLength={100}
              defaultValue={edit?.keyword}
            />
          </label>
          <label>
            점수
            <input
              name="riskScore"
              type="number"
              required
              min={0}
              max={100}
              defaultValue={edit?.riskScore ?? 20}
            />
          </label>
          <label>
            카테고리
            <select name="category" defaultValue={edit?.category}>
              {categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            설명
            <input name="description" defaultValue={edit?.description ?? ""} />
          </label>
          <label className="check">
            <input
              name="active"
              type="checkbox"
              defaultChecked={edit?.active ?? true}
              disabled={!edit}
            />
            활성화
          </label>
          <div>
            <button disabled={busy}>
              {edit ? "변경 저장" : "키워드 등록"}
            </button>
            {edit && (
              <button
                type="button"
                className="text-button"
                onClick={() => setEdit(null)}
              >
                취소
              </button>
            )}
          </div>
        </form>
      </section>
      <section className="panel table-wrap">
        {loading ? (
          <Loading />
        ) : !data?.length ? (
          <Empty />
        ) : (
          <table>
            <thead>
              <tr>
                <th>키워드</th>
                <th>점수</th>
                <th>카테고리</th>
                <th>상태</th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {data.map((k) => (
                <tr key={k.keywordId}>
                  <td>{k.keyword}</td>
                  <td>{k.riskScore}</td>
                  <td>{k.category}</td>
                  <td>{k.active ? "활성" : "비활성"}</td>
                  <td>
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() => setEdit(k)}
                    >
                      수정
                    </button>
                    {k.active && (
                      <button
                        className="text-button danger"
                        disabled={busy}
                        onClick={async () => {
                          if (!confirm("이 키워드를 비활성화할까요?")) return;
                          setBusy(true);
                          setError("");
                          try {
                            await api(`/admin/keywords/${k.keywordId}`, {
                              method: "DELETE",
                            });
                            reload();
                          } catch (e) {
                            setError((e as Error).message);
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        비활성화
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
type Review = {
  reviewId: number;
  analysisId: number;
  feedbackType: string;
  comment: string;
  version: number;
  status: string;
  label: string;
  reason: string;
};
function Reviews() {
  const [page, setPage] = useState(0),
    [status, setStatus] = useState("PENDING"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const list = useLoad<{ content: Review[]; totalElements: number }>(
    `/admin/reviews?status=${status}&page=${page}&size=10`,
  );
  return (
    <>
      <div className="row">
        <label>
          검토 상태
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
          >
            <option value="PENDING">대기 중</option>
            <option value="REVIEWED">검토 완료</option>
          </select>
        </label>
        <button className="secondary" onClick={list.reload}>
          새로고침
        </button>
      </div>
      <Notice error={error || list.error} />
      {list.loading ? (
        <Loading />
      ) : !list.data?.content.length ? (
        <Empty />
      ) : (
        list.data.content.map((r) => (
          <section className="panel" key={r.reviewId}>
            <h2>
              분석 #{r.analysisId} · 피드백 #{r.reviewId}
            </h2>
            <p>{r.feedbackType}</p>
            <blockquote>{r.comment || "추가 의견 없음"}</blockquote>
            {r.status === "REVIEWED" ? (
              <p>
                {r.label} · {r.reason}
              </p>
            ) : (
              <form
                className="form-grid"
                onSubmit={async (e) => {
                  e.preventDefault();
                  setBusy(true);
                  setError("");
                  const f = new FormData(e.currentTarget);
                  try {
                    await api(
                      `/admin/reviews/${r.reviewId}`,
                      json("PATCH", {
                        version: r.version,
                        label: f.get("label"),
                        reason: f.get("reason"),
                      }),
                    );
                    list.reload();
                  } catch (e) {
                    setError((e as Error).message);
                    list.reload();
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <label>
                  검토 결과
                  <select name="label" defaultValue="UNCERTAIN">
                    <option value="UNCERTAIN">판단 보류</option>
                    <option value="PHISHING">피싱</option>
                    <option value="NORMAL">정상</option>
                  </select>
                </label>
                <label>
                  판단 근거
                  <input name="reason" required maxLength={1000} />
                </label>
                <button disabled={busy}>검토 저장</button>
              </form>
            )}
          </section>
        ))
      )}
      <div className="row">
        <button
          className="secondary"
          disabled={page === 0 || list.loading}
          onClick={() => setPage((p) => p - 1)}
        >
          이전
        </button>
        <span>{page + 1} 페이지</span>
        <button
          className="secondary"
          disabled={
            list.loading || (page + 1) * 10 >= (list.data?.totalElements ?? 0)
          }
          onClick={() => setPage((p) => p + 1)}
        >
          다음
        </button>
      </div>
    </>
  );
}
type Log = Analysis & {
  auditId: number;
  userId: number;
  action: string;
  targetType: string;
  targetId: number;
  detail: unknown;
  userSummary?: { name: string; email: string };
};
function Logs({ kind }: { kind: string }) {
  const { data, error, loading, reload } = useLoad<Log[]>("/admin/" + kind);
  const audit = kind === "audit-logs";
  return (
    <section className="panel table-wrap">
      <div className="row">
        <h2>{audit ? "감사 로그" : "전체 분석 로그"}</h2>
        <button className="secondary" onClick={reload}>
          새로고침
        </button>
      </div>
      <Notice error={error} />
      {loading ? (
        <Loading />
      ) : !data?.length ? (
        <Empty />
      ) : (
        <table>
          <thead>
            <tr>
              <th>일시</th>
              <th>사용자</th>
              <th>{audit ? "행동" : "입력 요약"}</th>
              <th>{audit ? "대상" : "위험도"}</th>
              <th>상세</th>
            </tr>
          </thead>
          <tbody>
            {data.map((l) => (
              <tr key={audit ? l.auditId : l.analysisId}>
                <td>{date(l.createdAt)}</td>
                <td>{audit ? l.userId : l.userSummary?.name || "—"}</td>
                <td>{audit ? l.action : l.inputPreview}</td>
                <td>
                  {audit ? (
                    `${l.targetType} #${l.targetId}`
                  ) : (
                    <Risk level={l.riskLevel} />
                  )}
                </td>
                <td>
                  {audit ? (
                    <details>
                      <summary>상세 보기</summary>
                      <pre>{JSON.stringify(l.detail, null, 2)}</pre>
                    </details>
                  ) : (
                    `${l.riskScore}점`
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
