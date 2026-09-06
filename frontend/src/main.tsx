import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
  Link,
} from "react-router-dom";
import { api, getSession, json, setSession } from "./api";
import type { Session, User } from "./types";
import { Notice, Title } from "./ui";
import { Analyze, History, Chat } from "./pages";
import { Admin } from "./admin";
import "./style.css";
function Auth({ onLogin }: { onLogin: (user: User) => void }) {
  const [signup, setSignup] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [done, setDone] = useState("");
  return (
    <div className="auth-layout">
      <section className="auth-intro">
        <Link className="brand" to="/">
          ◈ FinGuard AI
        </Link>
        <div>
          <p className="eyebrow">조금 더 안심할 수 있도록</p>
          <h1>
            의심은 확인으로,
            <br />
            막막함은 다음 행동으로.
          </h1>
          <p>
            의심 문자를 살펴보고
            <br />
            공식 문서에서 대응의 근거를 찾아보세요.
          </p>
        </div>
        <small>금융 소비자 보호 AI 어시스턴트</small>
      </section>
      <section className="auth-form">
        <h2>{signup ? "회원가입" : "다시 만나 반가워요"}</h2>
        <p>
          {signup
            ? "FinGuard AI를 시작해 보세요."
            : "로그인하고 안전한 금융 생활을 시작하세요."}
        </p>
        <Notice error={error} />
        {done && <p role="status">{done}</p>}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            const f = new FormData(e.currentTarget);
            try {
              const credentials = {
                email: f.get("email"),
                password: f.get("password"),
              };
              if (signup) {
                await api(
                  "/auth/signup",
                  json("POST", { ...credentials, name: f.get("name") }),
                  false,
                );
                setSignup(false);
                setDone("가입되었습니다. 로그인해 주세요.");
              } else {
                const s = await api<Session>(
                  "/auth/login",
                  json("POST", credentials),
                  false,
                );
                setSession(s);
                onLogin(s.user);
              }
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {signup && (
            <label>
              이름
              <input name="name" autoComplete="name" required maxLength={100} />
            </label>
          )}
          <label>
            이메일
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              maxLength={255}
            />
          </label>
          <label>
            비밀번호
            <input
              name="password"
              type="password"
              autoComplete={signup ? "new-password" : "current-password"}
              required
              minLength={8}
              maxLength={72}
            />
          </label>
          <button disabled={busy}>
            {busy ? "처리 중…" : signup ? "계정 만들기" : "로그인"}
          </button>
        </form>
        <button
          className="text-button"
          disabled={busy}
          onClick={() => {
            setSignup(!signup);
            setError("");
            setDone("");
          }}
        >
          {signup ? "이미 계정이 있어요 · 로그인" : "처음이신가요? 회원가입"}
        </button>
      </section>
    </div>
  );
}
function App() {
  const [user, setUser] = useState<User | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    const expire = () => {
      setUser(null);
      navigate("/");
    };
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, [navigate]);
  if (!user)
    return (
      <Auth
        onLogin={(u) => {
          setUser(u);
          navigate("/");
        }}
      />
    );
  return (
    <div className="app">
      <aside className="sidebar">
        <Link to="/" className="brand">
          ◈ FinGuard AI
        </Link>
        <p className="nav-caption">내 워크스페이스</p>
        <nav>
          <NavLink to="/" end>
            홈
          </NavLink>
          <NavLink to="/analysis">의심 문자 분석</NavLink>
          <NavLink to="/chat">문서 기반 Q&A</NavLink>
          <NavLink to="/history">내 분석 이력</NavLink>
          {user.role === "ADMIN" && (
            <>
              <p className="nav-caption">관리자</p>
              <NavLink to="/admin">서비스 관리</NavLink>
            </>
          )}
        </nav>
        <div className="sidebar-note">
          작은 의심도
          <br />
          그냥 지나치지 않도록.
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>금융 소비자 보호 어시스턴트</span>
          <div>
            <span>{user.name} 님</span>
            <button
              className="text-button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await api(
                    "/auth/logout",
                    json("POST", { refreshToken: getSession()?.refreshToken }),
                  );
                  setSession(null);
                  setUser(null);
                  navigate("/");
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              로그아웃
            </button>
          </div>
        </header>
        <main>
          <Notice error={error} />
          <Routes>
            <Route
              path="/"
              element={
                <>
                  <Title
                    title={`${user.name} 님, 무엇을 확인할까요?`}
                    description="의심 문자를 분석하고, 필요한 대응 정보를 찾아보세요."
                  />
                  <div className="hero">
                    <span className="badge">문자 속 위험 신호 확인</span>
                    <h2>낯선 문자, 혼자 판단하지 마세요.</h2>
                    <p>
                      요구하는 행동과 위험 키워드를 살펴보고
                      <br />
                      분석 결과를 차근차근 확인하세요.
                    </p>
                    <Link className="button" to="/analysis">
                      의심 문자 분석하기 →
                    </Link>
                  </div>
                  <div className="cards">
                    <Link className="card" to="/chat">
                      <span className="card-icon">↗</span>
                      <h2>공식 문서에 물어보기</h2>
                      <p>근거 문단과 함께 대응 정보를 확인해요.</p>
                      <span>Q&A 시작하기 →</span>
                    </Link>
                    <Link className="card" to="/history">
                      <span className="card-icon">≡</span>
                      <h2>내 분석 이력</h2>
                      <p>이전에 확인한 문자를 다시 살펴보세요.</p>
                      <span>이력 확인하기 →</span>
                    </Link>
                  </div>
                  <p className="footnote">
                    분석 결과는 참고 정보입니다. 위험 신호가 탐지되지 않아도
                    안전을 보장하지 않습니다.
                  </p>
                </>
              }
            />
            <Route path="/analysis" element={<Analyze />} />
            <Route path="/history" element={<History />} />
            <Route path="/chat" element={<Chat />} />
            <Route
              path="/admin/*"
              element={
                user.role === "ADMIN" ? <Admin /> : <Navigate to="/" replace />
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
