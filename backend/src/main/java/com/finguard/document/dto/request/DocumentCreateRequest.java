package com.finguard.document.dto.request;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@NoArgsConstructor
@AllArgsConstructor
@Getter
public class DocumentCreateRequest {
    private String title;
    private String source;
    private String sourceUrl;
}
