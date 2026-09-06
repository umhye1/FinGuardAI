package com.finguard.document.dto.response;

import com.finguard.document.domain.Document;
import com.finguard.document.domain.DocumentStatus;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;


@Getter
@Builder
public class DocumentListResponse {

    private Long documentId;
    private String title;
    private String source;
    private DocumentStatus status;
    private int chunkCount;
    private Long uploadedBy;
    private LocalDateTime createdAt;

    public static DocumentListResponse from(Document document) {
        return DocumentListResponse.builder()
                .documentId(document.getDocumentId())
                .title(document.getTitle())
                .source(document.getSource())
                .status(document.getStatus())
                .chunkCount(document.getChunkCount())
                .uploadedBy(
                        document.getUploadedBy() != null
                                ? document.getUploadedBy().getUserId()
                                : null
                )
                .createdAt(document.getCreatedAt())
                .build();
    }


}
