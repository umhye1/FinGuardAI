package com.finguard.document.dto.response;

import com.finguard.document.domain.Document;
import com.finguard.document.domain.DocumentStatus;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;


@Getter
@Builder
public class DocumentCreateResponse {
    private Long documentId;
    private String title;
    private String source;
    private String sourceUrl;
    private String filePath;
    private DocumentStatus documentStatus;
    private Long uploadedBy;
    private LocalDateTime createdAt;
    private int chunkCount;
    private java.util.UUID jobId;

    public static DocumentCreateResponse from(Document document, java.util.UUID jobId) {
        return DocumentCreateResponse.builder()
                .documentId(document.getDocumentId())
                .jobId(jobId)
                .chunkCount(document.getChunkCount())
                .title(document.getTitle())
                .source(document.getSource())
                .sourceUrl(document.getSourceUrl())
                .filePath(document.getFilePath())
                .documentStatus(document.getStatus())
                .uploadedBy(
                        document.getUploadedBy() != null
                        ? document.getUploadedBy().getUserId()
                                : null
                )
                .createdAt(document.getCreatedAt())
                .build();
    }
}
