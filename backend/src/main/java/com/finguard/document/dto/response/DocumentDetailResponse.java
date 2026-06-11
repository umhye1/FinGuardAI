package com.finguard.document.dto.response;

import com.finguard.document.domain.Document;
import com.finguard.document.domain.DocumentStatus;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class DocumentDetailResponse {
    private Long documentId;
    private String title;
    private String source;
    private String sourceUrl;
    private String filePath;
    private DocumentStatus status;
    private int chunkCount;
    private Long uploadedBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public static DocumentDetailResponse from(Document document) {
        return DocumentDetailResponse.builder()
                .documentId(document.getDocumentId())
                .title(document.getTitle())
                .source(document.getSource())
                .sourceUrl(document.getSourceUrl())
                .filePath(document.getFilePath())
                .status(document.getStatus())
                .chunkCount(document.getChunkCount())
                .uploadedBy(
                        document.getUploadedBy() != null
                                ? document.getUploadedBy().getUserId()
                                : null
                )
                .createdAt(document.getCreatedAt())
                .updatedAt(document.getUpdatedAt())
                .build();
    }
}

