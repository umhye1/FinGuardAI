export type User = {
  userId: number;
  name: string;
  email: string;
  role: "USER" | "ADMIN";
};
export type Session = { accessToken: string; refreshToken: string; user: User };
export type Analysis = {
  analysisId: number;
  inputText?: string;
  inputPreview?: string;
  riskLevel: string;
  riskScore: number;
  createdAt: string;
  ruleReason?: string;
  aiSummary?: string;
  recommendedAction?: string;
  detectedKeywordRespons?: {
    keyword: string;
    category: string;
    score: number;
  }[];
  modelResult?: {
    status: string;
    decision: string;
    modelVersion: string;
    errorCode?: string;
  };
};
export type ChatSession = {
  sessionId: number;
  title: string;
  lastMessage?: string;
};
export type Message = {
  messageId: number;
  sender: string;
  message: string;
  generationStatus?: string;
  referencedChunks: {
    chunkId: number;
    documentTitle: string;
    contentPreview: string;
  }[];
};
export type Document = {
  documentId: number;
  title: string;
  source: string;
  status: string;
  chunkCount: number;
  createdAt: string;
};
export type Keyword = {
  keywordId: number;
  keyword: string;
  riskScore: number;
  category: string;
  description: string;
  active: boolean;
};
