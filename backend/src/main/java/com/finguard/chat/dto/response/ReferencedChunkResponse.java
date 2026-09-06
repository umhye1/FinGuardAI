package com.finguard.chat.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@lombok.NoArgsConstructor
@lombok.AllArgsConstructor
public class ReferencedChunkResponse {

    private Long chunkId;
    private Long documentId;
    private String documentTitle;
    private String contentPreview;
}
