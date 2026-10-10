package com.finguard.document.service;

import com.finguard.document.dto.response.DocumentIndexStatusResponse;
import com.finguard.document.dto.response.DocumentIndexStatusResponse.Status;
import com.finguard.global.exception.BadRequestException;
import com.finguard.global.exception.NotFoundException;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class DocumentIndexStatusService {
    private final JdbcTemplate jdbc;

    @Transactional(readOnly = true)
    public DocumentIndexStatusResponse get(long documentId, String model) {
        if (documentId <= 0 || model == null || !model.matches("[a-zA-Z0-9._-]{1,100}")) {
            throw new BadRequestException("문서 ID와 임베딩 모델명을 올바르게 입력해주세요.");
        }
        // One statement gives a consistent snapshot during atomic index publication/deletion.
        // Never trust the cached documents.chunk_count or count another model's vectors.
        var rows = jdbc.query("""
                SELECT d.document_id, d.status,
                       count(c.chunk_id) AS total,
                       count(c.chunk_id) FILTER (WHERE e.chunk_id IS NULL) AS missing,
                       count(e.chunk_id) FILTER (
                           WHERE e.content_hash = encode(sha256(convert_to(c.content, 'UTF8')), 'hex')) AS current
                FROM documents d
                LEFT JOIN document_chunks c ON c.document_id = d.document_id
                LEFT JOIN document_embeddings e ON e.chunk_id = c.chunk_id AND e.embedding_model = ?
                WHERE d.document_id = ?
                GROUP BY d.document_id, d.status
                """, (rs, rowNum) -> {
            long total = rs.getLong("total"), missing = rs.getLong("missing"), current = rs.getLong("current");
            long stale = total - missing - current;
            String documentStatus = rs.getString("status");
            Status status;
            if (!"COMPLETED".equals(documentStatus)) status = Status.TEXT_NOT_READY;
            else if (total == 0) status = Status.NO_CHUNKS;
            else if (stale > 0) status = Status.STALE;
            else if (missing == total) status = Status.NOT_INDEXED;
            else if (missing > 0) status = Status.PARTIAL;
            else status = Status.INDEXED;
            return new DocumentIndexStatusResponse(documentId, documentStatus, model, status,
                    total, current, missing, stale);
        }, model, documentId);
        if (rows.isEmpty()) throw new NotFoundException("문서를 찾을 수 없습니다.");
        return rows.getFirst();
    }
}
