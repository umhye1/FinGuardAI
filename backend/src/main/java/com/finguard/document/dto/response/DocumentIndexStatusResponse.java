package com.finguard.document.dto.response;

/** Stored vector coverage only; not evidence approval or RAG answer readiness. */
public record DocumentIndexStatusResponse(
        long documentId, String documentStatus, String embeddingModel, Status status,
        long totalChunks, long currentChunks, long missingChunks, long staleChunks) {
    public enum Status { TEXT_NOT_READY, NO_CHUNKS, NOT_INDEXED, PARTIAL, STALE, INDEXED }
}
