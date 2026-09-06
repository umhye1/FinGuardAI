import { useState } from "react";
import { api, json } from "./api";
import type { Analysis, ChatSession, Message } from "./types";
import { date, Empty, Loading, Notice, Risk, Title, useLoad } from "./ui";
function Result({ value }: { value: Analysis }) {
  const [error, setError] = useState(""),
    [sent, setSent] = useState(false),
    [busy, setBusy] = useState(false);
  const model = value.modelResult;
  return (
    <section className="panel result">
      <div className="row">
        <h2>분석 결과</h2>
        <Risk level={value.riskLevel} />
      </div>
      <p className="score">
        {value.riskScore}
        <small>점 · 규칙 기반 점수</small>
      </p>
      <p className="muted">점수는 사기일 확률을 의미하지 않습니다.</p>
      {value.inputText && <blockquote>{value.inputText}</blockquote>}
      <h3>탐지한 키워드</h3>
      <div className="chips">
        {value.detectedKeywordRespons?.length ? (
          value.detectedKeywordRespons.map((k, i) => (
            <span className="badge" key={i}>
              {k.keyword} · {k.score}점
            </span>
          ))
        ) : (
          <span className="muted">
            탐지한 키워드가 없습니다. 안전을 보장하지 않습니다.
          </span>
        )}
      </div>
      <h3>AI 분류</h3>
      <p>
        {!model || model.status !== "COMPLETED"
          ? "AI 분석을 완료하지 못했습니다. 규칙 기반 결과만 표시합니다."
          : model.decision === "ABSTAIN"
            ? "판단 보류 · AI가 확실하게 분류하지 못했습니다."
            : model.decision === "FLAG"
              ? "피싱 의심 신호가 있습니다."
              : "AI에서 피싱 신호를 분류하지 않았습니다. 안전 여부는 별도 확인이 필요합니다."}
      </p>
      <h3>규칙 기반 설명</h3>
      <p className="prewrap">{value.ruleReason}</p>
      <h3>대응 안내</h3>
      <p className="prewrap">{value.recommendedAction}</p>
      <details>
        <summary>결과가 실제 상황과 다른가요?</summary>
        <Notice error={error} />
        {sent ? (
          <p role="status">피드백을 접수했습니다.</p>
        ) : (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              const f = new FormData(e.currentTarget);
              try {
                await api(
                  `/analysis/${value.analysisId}/feedback`,
                  json("POST", {
                    type: f.get("type"),
                    comment: f.get("comment"),
                  }),
                );
                setSent(true);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              피드백 유형
              <select name="type">
                <option value="FALSE_POSITIVE">
                  정상 문자를 위험하게 판단했어요
                </option>
                <option value="FALSE_NEGATIVE">위험 문자를 놓쳤어요</option>
                <option value="INCORRECT_GUIDANCE">
                  안내가 정확하지 않아요
                </option>
                <option value="OTHER">기타</option>
              </select>
            </label>
            <label>
              의견
              <textarea name="comment" maxLength={1000} />
            </label>
            <button disabled={busy}>피드백 보내기</button>
          </form>
        )}
      </details>
    </section>
  );
}
export function Analyze() {
  const [text, setText] = useState(""),
    [result, setResult] = useState<Analysis | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <>
      <Title
        title="의심 문자 분석"
        description="문자 내용을 붙여 넣으면 위험 키워드와 AI 분류 결과를 확인할 수 있어요."
      />
      <div className="split">
        <section className="panel">
          <h2>어떤 문자를 받으셨나요?</h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              setResult(null);
              try {
                setResult(
                  await api<Analysis>(
                    "/analysis",
                    json("POST", { text: text.trim() }),
                  ),
                );
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              문자 내용
              <textarea
                className="message-input"
                required
                maxLength={10000}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="받은 문자 내용을 입력해 주세요."
              />
            </label>
            <p className="muted">
              계좌번호·전화번호 등 불필요한 개인정보는 지워 주세요.
            </p>
            <div className="row">
              <span className="muted">
                {text.length.toLocaleString()} / 10,000
              </span>
              <button disabled={busy || !text.trim()}>
                {busy ? "분석 중…" : "분석하기"}
              </button>
            </div>
          </form>
          <Notice error={error} />
        </section>
        {result ? (
          <Result key={result.analysisId} value={result} />
        ) : (
          <section className="panel result-placeholder">
            <span className="large-icon">◎</span>
            <h2>
              {busy
                ? "문자의 위험 신호를 확인하고 있어요"
                : "분석 결과가 여기에 표시돼요"}
            </h2>
            <p>
              규칙 기반 점수와 AI 판단을
              <br />
              함께 확인할 수 있습니다.
            </p>
          </section>
        )}
      </div>
    </>
  );
}
export function History() {
  const { data, error, loading, reload } = useLoad<Analysis[]>("/analysis");
  const [selected, setSelected] = useState<Analysis | null>(null),
    [actionError, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <>
      <Title
        title="내 분석 이력"
        description="이전에 분석한 문자와 결과를 다시 확인하세요."
      />
      <Notice error={error || actionError} />
      {loading ? (
        <Loading />
      ) : !data?.length ? (
        <Empty text="아직 분석한 문자가 없습니다. 의심 문자 분석에서 시작해 보세요." />
      ) : (
        <div className="panel table-wrap">
          <table>
            <thead>
              <tr>
                <th>분석 일시</th>
                <th>문자 요약</th>
                <th>위험도</th>
                <th>규칙 점수</th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.analysisId}>
                  <td>{date(a.createdAt)}</td>
                  <td>{a.inputPreview}</td>
                  <td>
                    <Risk level={a.riskLevel} />
                  </td>
                  <td>{a.riskScore}점</td>
                  <td>
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        setError("");
                        try {
                          setSelected(
                            await api<Analysis>(`/analysis/${a.analysisId}`),
                          );
                        } catch (e) {
                          setError((e as Error).message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      상세보기
                    </button>
                    <button
                      className="text-button danger"
                      disabled={busy}
                      onClick={async () => {
                        if (!confirm("이 분석 이력을 삭제할까요?")) return;
                        setBusy(true);
                        setError("");
                        try {
                          await api(`/analysis/${a.analysisId}`, {
                            method: "DELETE",
                          });
                          if (selected?.analysisId === a.analysisId)
                            setSelected(null);
                          reload();
                        } catch (e) {
                          setError((e as Error).message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selected && <Result key={selected.analysisId} value={selected} />}
    </>
  );
}
export function Chat() {
  const sessions = useLoad<ChatSession[]>("/chat/sessions"),
    [id, setId] = useState<number | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <>
      <Title
        title="문서 기반 Q&A"
        description="공식 문서에서 답변의 근거를 찾아보세요. 근거가 부족하면 답변을 보류합니다."
      />
      <Notice error={error || sessions.error} />
      <div className="chat-layout">
        <section className="panel session-list">
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                const s = await api<ChatSession>(
                  "/chat/sessions",
                  json("POST", { title: "새 질문" }),
                );
                sessions.reload();
                setId(s.sessionId);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            + 새 대화
          </button>
          {sessions.loading ? (
            <Loading />
          ) : (
            sessions.data?.map((s) => (
              <button
                className={"session " + (s.sessionId === id ? "selected" : "")}
                key={s.sessionId}
                onClick={() => setId(s.sessionId)}
              >
                {s.title || "새 질문"}
                <small>{s.lastMessage || "질문을 시작해 보세요"}</small>
              </button>
            ))
          )}
        </section>
        {id ? (
          <Conversation
            key={id}
            id={id}
            changed={sessions.reload}
            deleted={() => {
              setId(null);
              sessions.reload();
            }}
          />
        ) : (
          <section className="panel result-placeholder">
            <span className="large-icon">↗</span>
            <h2>어떤 도움이 필요하신가요?</h2>
            <p>새 대화를 만들거나 이전 대화를 선택하세요.</p>
          </section>
        )}
      </div>
    </>
  );
}
function Conversation({
  id,
  changed,
  deleted,
}: {
  id: number;
  changed: () => void;
  deleted: () => void;
}) {
  const { data, error, loading, reload } = useLoad<Message[]>(
    `/chat/sessions/${id}/messages`,
  );
  const [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [actionError, setError] = useState("");
  return (
    <section className="panel conversation">
      <div className="row">
        <h2>공식 문서에 질문하기</h2>
        <button
          className="text-button danger"
          disabled={busy}
          onClick={async () => {
            if (!confirm("이 대화를 삭제할까요?")) return;
            setBusy(true);
            try {
              await api(`/chat/sessions/${id}`, { method: "DELETE" });
              deleted();
            } catch (e) {
              setError((e as Error).message);
              setBusy(false);
            }
          }}
        >
          대화 삭제
        </button>
      </div>
      <Notice error={error || actionError} />
      <div className="messages" aria-live="polite">
        {loading ? (
          <Loading />
        ) : !data?.length ? (
          <Empty text="피싱과 관련해 궁금한 점을 질문해 주세요." />
        ) : (
          data.map((m) => (
            <article
              className={"message " + (m.sender === "USER" ? "mine" : "")}
              key={m.messageId}
            >
              <strong>{m.sender === "USER" ? "내 질문" : "FinGuard AI"}</strong>
              {m.sender === "AI" &&
                m.generationStatus &&
                m.generationStatus !== "ANSWERED" && (
                  <span className="badge amber">
                    {m.generationStatus === "INSUFFICIENT_EVIDENCE"
                      ? "근거 부족"
                      : "답변 생성 미완료"}
                  </span>
                )}
              <p className="prewrap">{m.message}</p>
              {m.referencedChunks?.map((c) => (
                <details key={c.chunkId}>
                  <summary>{c.documentTitle} · 근거 문단</summary>
                  <p className="prewrap">{c.contentPreview}</p>
                </details>
              ))}
            </article>
          ))
        )}
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await api(
              `/chat/sessions/${id}/messages`,
              json("POST", { question: question.trim() }),
            );
            setQuestion("");
            reload();
            changed();
          } catch (e) {
            setError((e as Error).message);
            reload();
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          질문
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            required
            maxLength={2000}
            placeholder="예: 의심스러운 문자를 받았을 때 무엇을 확인해야 하나요?"
          />
        </label>
        <button disabled={busy || !question.trim()}>
          {busy ? "근거를 찾는 중…" : "질문 보내기"}
        </button>
      </form>
    </section>
  );
}
