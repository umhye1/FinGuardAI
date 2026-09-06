package com.finguard.document.dto.response;

import com.finguard.document.domain.DocumentChunk;
import lombok.Builder;
import lombok.Getter;

@Builder
@Getter
public class DocumentChunkSearchResponse {
    private Long chunkId;
    private Long documentId;
    private String documentTitle;
    private Integer chunkIndex;
    private String contentPreview;


    public static DocumentChunkSearchResponse from (DocumentChunk chunk) {
        String content = chunk.getContent();
        String preview = content.length() > 120
                ?content.substring(0,120) + "..."
                : content;

        return DocumentChunkSearchResponse.builder()
                .chunkId(chunk.getChunkId())
                .documentId(chunk.getDocument().getDocumentId())
                .documentTitle(chunk.getDocument().getTitle())
                .chunkIndex(chunk.getChunkIndex())
                .contentPreview(preview)
                .build();

    }

}
